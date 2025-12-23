"""
NVIDIA GPU utilization sampler using nvidia-smi CLI.

Uses subprocess to query GPU utilization via nvidia-smi command.
Supports multiple GPUs by aggregating as max(value) across all GPUs.
Handles failures gracefully (returns None) without crashing.
"""

from __future__ import annotations

import logging
import subprocess
import time
from typing import Optional

log = logging.getLogger(__name__)


class NvidiaSmiGpuSampler:
    """
    NVIDIA GPU utilization sampler using nvidia-smi CLI.
    
    Queries GPU core utilization percentage using:
      nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits
    
    Supports multiple GPUs by taking the maximum utilization value.
    All failures are handled gracefully (returns None).
    """

    def __init__(self) -> None:
        """Initialize sampler. No heavy initialization - availability checked at runtime."""
        self._last_sample_time: float = 0.0
        self._min_sample_interval: float = 1.0  # Rate limit: max once per second
        self._nvidia_smi_path: Optional[str] = None
        
        # Try to detect nvidia-smi path once (optional optimization)
        self._detect_nvidia_smi_path()

    def _detect_nvidia_smi_path(self) -> None:
        """Try to detect nvidia-smi executable path (optional optimization)."""
        try:
            # Try common paths on Windows
            import shutil
            nvidia_smi = shutil.which("nvidia-smi")
            if nvidia_smi:
                self._nvidia_smi_path = nvidia_smi
                log.debug(f"Detected nvidia-smi at: {nvidia_smi}")
        except Exception:
            # If detection fails, we'll try "nvidia-smi" directly in subprocess
            pass

    def start(self) -> bool:
        """
        Optional lightweight initialization.
        Returns True if nvidia-smi appears available (doesn't guarantee it will work).
        """
        # Just verify nvidia-smi exists - don't fail if it doesn't
        try:
            result = self._run_nvidia_smi_check()
            if result is not None:
                log.info("NVIDIA GPU sampler initialized (nvidia-smi available)")
                return True
            else:
                log.debug("NVIDIA GPU sampler: nvidia-smi not available (will use CPU fallback)")
                return False
        except Exception as e:
            log.debug(f"NVIDIA GPU sampler initialization check failed: {e} (will use CPU fallback)")
            return False

    def sample(self) -> Optional[float]:
        """
        Sample current GPU utilization percentage (0-100).
        
        Returns:
            GPU utilization percentage (0-100) if successful, None if unavailable.
        
        Handles all failure cases gracefully:
            - nvidia-smi not found
            - Non-zero exit code
            - Empty output
            - Parse errors
            - Timeout
        """
        # Rate limiting: don't call nvidia-smi more than once per second
        now = time.time()
        if now - self._last_sample_time < self._min_sample_interval:
            # Return None if we're rate-limited (caller should use previous value or CPU fallback)
            return None
        
        self._last_sample_time = now
        
        try:
            # Run nvidia-smi query
            result = self._run_nvidia_smi_query()
            return result
        except Exception as e:
            # Log only occasionally to avoid spam
            log.debug(f"nvidia-smi query failed: {e}")
            return None

    def _run_nvidia_smi_check(self) -> Optional[bool]:
        """Check if nvidia-smi is available (lightweight check)."""
        try:
            cmd = self._nvidia_smi_path or "nvidia-smi"
            result = subprocess.run(
                [cmd, "-L"],  # List GPUs (lightweight)
                capture_output=True,
                text=True,
                timeout=1.0,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None
        except Exception:
            return None

    def _run_nvidia_smi_query(self) -> Optional[float]:
        """
        Run nvidia-smi query and parse GPU utilization.
        
        Returns:
            Maximum GPU utilization across all GPUs (0-100), or None on failure.
        """
        cmd = self._nvidia_smi_path or "nvidia-smi"
        args = [
            cmd,
            "--query-gpu=utilization.gpu",
            "--format=csv,noheader,nounits"
        ]
        
        try:
            # Run subprocess with timeout (500ms as specified)
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=0.5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            # Check exit code
            if result.returncode != 0:
                log.debug(f"nvidia-smi returned non-zero exit code: {result.returncode}")
                if result.stderr:
                    log.debug(f"nvidia-smi stderr: {result.stderr[:200]}")
                return None
            
            # Parse output
            output = result.stdout.strip()
            if not output:
                log.debug("nvidia-smi returned empty output")
                return None
            
            # Parse all GPU values (one per line)
            gpu_values: list[float] = []
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    value = float(line)
                    # Validate range (0-100)
                    if 0 <= value <= 100:
                        gpu_values.append(value)
                    else:
                        log.debug(f"nvidia-smi returned out-of-range value: {value}")
                except ValueError:
                    log.debug(f"nvidia-smi returned non-numeric value: {line}")
                    continue
            
            if not gpu_values:
                log.debug("nvidia-smi returned no valid GPU utilization values")
                return None
            
            # Aggregate as max across all GPUs
            max_util = max(gpu_values)
            log.debug(f"nvidia-smi GPU utilization: {max_util:.1f}% (from {len(gpu_values)} GPU(s))")
            return max_util
            
        except subprocess.TimeoutExpired:
            log.debug("nvidia-smi query timed out (>500ms)")
            return None
        except FileNotFoundError:
            log.debug("nvidia-smi executable not found")
            return None
        except OSError as e:
            log.debug(f"nvidia-smi OS error: {e}")
            return None
        except Exception as e:
            log.debug(f"nvidia-smi query error: {e}")
            return None

    def close(self) -> None:
        """Cleanup resources (no-op for subprocess-based sampler)."""
        pass

    def is_available(self) -> bool:
        """
        Check if GPU sampling is currently available.
        This is a runtime check, not init-time.
        """
        # Try a quick check
        try:
            result = self._run_nvidia_smi_check()
            return result is True
        except Exception:
            return False

