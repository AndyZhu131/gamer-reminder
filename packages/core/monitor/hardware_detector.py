"""
Windows hardware usage detector using NVIDIA nvidia-smi for GPU
and psutil for CPU.

GPU detection uses nvidia-smi CLI to query GPU utilization.
Falls back to CPU-only if GPU is unavailable (runtime-checked, not init-time).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import psutil

from .detector import ActivityDetector, HardwareMetrics
from .nvidia_smi_sampler import NvidiaSmiGpuSampler

log = logging.getLogger(__name__)


class HardwareUsageDetector(ActivityDetector):
    """
    Windows hardware detector using NVIDIA nvidia-smi for GPU and psutil for CPU.
    
    GPU availability is checked at runtime (not init-time). If nvidia-smi fails,
    the detector automatically falls back to CPU-only mode and retries GPU
    periodically (every 10 seconds) to detect recovery.
    """

    def __init__(self) -> None:
        """Initialize detector. GPU availability is checked at runtime, not here."""
        self._gpu_sampler: Optional[NvidiaSmiGpuSampler] = None
        self._gpu_available = False  # Runtime state (not init-time decision)
        self._last_gpu_retry_time: float = 0.0
        self._gpu_retry_interval: float = 10.0  # Retry GPU every 10 seconds if unavailable
        
        # Initialize NVIDIA GPU sampler (lightweight, doesn't fail if unavailable)
        try:
            self._gpu_sampler = NvidiaSmiGpuSampler()
            # Optional: try to start (doesn't guarantee availability)
            self._gpu_sampler.start()
            log.info("NVIDIA GPU sampler initialized (availability checked at runtime)")
        except Exception as e:
            log.warning(f"GPU sampler initialization failed: {e}, will use CPU-only mode")
            self._gpu_sampler = None

    def sample(self) -> HardwareMetrics:
        """
        Sample current GPU and CPU utilization.
        
        GPU availability is checked at runtime. If GPU sampling fails,
        automatically falls back to CPU and schedules retry.
        """
        gpu_util: Optional[float] = None
        cpu_util: float = psutil.cpu_percent(interval=0.1)
        
        # Runtime GPU availability check
        now = time.time()
        should_try_gpu = (
            self._gpu_sampler is not None and
            (self._gpu_available or (now - self._last_gpu_retry_time >= self._gpu_retry_interval))
        )
        
        if should_try_gpu:
            try:
                gpu_util = self._gpu_sampler.sample()
                
                # Update availability state based on result
                was_available = self._gpu_available
                self._gpu_available = (gpu_util is not None)
                
                # Log state transitions only
                if was_available != self._gpu_available:
                    if self._gpu_available:
                        log.info("GPU telemetry: AVAILABLE (switched from CPU fallback)")
                    else:
                        log.info("GPU telemetry: UNAVAILABLE (switching to CPU fallback)")
                        self._last_gpu_retry_time = now  # Schedule retry
                elif not self._gpu_available:
                    # GPU unavailable, schedule retry
                    self._last_gpu_retry_time = now
                    
            except Exception as e:
                # GPU sampling failed
                was_available = self._gpu_available
                self._gpu_available = False
                self._last_gpu_retry_time = now
                
                if was_available:
                    log.info("GPU telemetry: UNAVAILABLE (switching to CPU fallback)")
                # Don't log every failure to avoid spam
        
        return HardwareMetrics(
            gpu_utilization=gpu_util,
            cpu_utilization=cpu_util,
            timestamp_ms=int(time.time() * 1000)
        )

    def is_available(self) -> bool:
        """
        Check if GPU metrics are currently available (runtime check).
        This reflects the current state, not init-time availability.
        """
        return self._gpu_available
    
    def get_telemetry_source(self) -> str:
        """
        Get the current telemetry source string.
        Returns "NVIDIA_SMI" if GPU is available, "CPU_FALLBACK" otherwise.
        """
        return "NVIDIA_SMI" if self._gpu_available else "CPU_FALLBACK"

    def __del__(self) -> None:
        """Cleanup resources."""
        if self._gpu_sampler:
            try:
                self._gpu_sampler.close()
            except Exception:
                pass

