"""
Windows hardware usage detector using PDH (Performance Data Helper) for GPU
and psutil for CPU.

GPU detection uses Windows Performance Counters via PDH API.
Falls back to CPU-only if GPU counters are unavailable.

TODO: GPU telemetry via PDH is limited and may not work on all systems.
If GPU detection fails, the detector falls back to CPU-only mode which
still functions but may be less accurate for gaming detection.
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from typing import Optional

import psutil

from .detector import ActivityDetector, HardwareMetrics

log = logging.getLogger(__name__)

# Windows PDH constants
PDH_FMT_DOUBLE = 0x00002000

# Load Windows DLLs
try:
    pdh_dll = ctypes.windll.pdh
    _PDH_AVAILABLE = True
except OSError:
    _PDH_AVAILABLE = False
    log.warning("PDH DLL not available, GPU detection disabled")


class HardwareUsageDetector(ActivityDetector):
    """
    Windows hardware detector using PDH for GPU and psutil for CPU.
    
    GPU detection attempts to use Windows Performance Counters.
    If GPU counters are unavailable, falls back to CPU-only mode.
    
    Note: GPU detection via PDH may not work on all systems. The detector
    will automatically fall back to CPU-only mode if GPU counters are unavailable.
    """

    def __init__(self) -> None:
        self._gpu_query: Optional[int] = None
        self._gpu_counter: Optional[int] = None
        self._gpu_available = False
        self._gpu_counter_path: Optional[str] = None
        
        if _PDH_AVAILABLE:
            self._init_gpu_detection()
        else:
            log.info("PDH not available, using CPU-only mode")

    def _init_gpu_detection(self) -> None:
        """Initialize GPU detection via PDH. Falls back silently if unavailable."""
        try:
            # Try common GPU utilization counter paths
            # These paths vary by GPU vendor and Windows version
            potential_paths = [
                "\\GPU Engine(*engtype_3D*)\\Utilization Percentage",
                "\\GPU Engine(*)\\Utilization Percentage",
            ]
            
            query_handle = wintypes.HANDLE()
            counter_handle = wintypes.HANDLE()
            
            # Open a query
            result = pdh_dll.PdhOpenQueryW(None, 0, ctypes.byref(query_handle))
            if result != 0:
                log.debug("PDH query open failed, GPU detection unavailable")
                return
            
            # Try to find a working GPU counter
            for path in potential_paths:
                result = pdh_dll.PdhAddCounterW(
                    query_handle,
                    path,
                    0,
                    ctypes.byref(counter_handle)
                )
                if result == 0:
                    # Try to collect data to verify it works
                    pdh_dll.PdhCollectQueryData(query_handle)
                    time.sleep(0.1)  # Brief wait for data
                    pdh_dll.PdhCollectQueryData(query_handle)
                    
                    # Check if we got valid data
                    value = wintypes.DOUBLE()
                    result = pdh_dll.PdhGetFormattedCounterValue(
                        counter_handle,
                        PDH_FMT_DOUBLE,
                        None,
                        ctypes.byref(value)
                    )
                    
                    if result == 0:
                        self._gpu_query = query_handle.value
                        self._gpu_counter = counter_handle.value
                        self._gpu_counter_path = path
                        self._gpu_available = True
                        log.info(f"GPU detection initialized using: {path}")
                        return
            
            # If we got here, no GPU counter worked
            pdh_dll.PdhCloseQuery(query_handle)
            log.info("GPU counters not available, using CPU-only mode")
            
        except Exception as e:
            log.warning(f"GPU detection initialization failed: {e}, using CPU-only mode")
            self._gpu_available = False

    def sample(self) -> HardwareMetrics:
        """Sample current GPU and CPU utilization."""
        gpu_util: Optional[float] = None
        cpu_util: float = psutil.cpu_percent(interval=0.1)
        
        if self._gpu_available and self._gpu_query and self._gpu_counter:
            try:
                # Collect query data
                pdh_dll.PdhCollectQueryData(self._gpu_query)
                
                # Get formatted value
                value = wintypes.DOUBLE()
                result = pdh_dll.PdhGetFormattedCounterValue(
                    self._gpu_counter,
                    PDH_FMT_DOUBLE,
                    None,
                    ctypes.byref(value)
                )
                
                if result == 0:
                    gpu_util = float(value.value)
                    # Clamp to 0-100
                    gpu_util = max(0.0, min(100.0, gpu_util))
                else:
                    log.debug(f"PDH GetFormattedCounterValue failed: {result}")
                    
            except Exception as e:
                log.debug(f"GPU sampling error: {e}")
        
        return HardwareMetrics(
            gpu_utilization=gpu_util,
            cpu_utilization=cpu_util,
            timestamp_ms=int(time.time() * 1000)
        )

    def is_available(self) -> bool:
        """Check if GPU metrics are available."""
        return self._gpu_available

    def __del__(self) -> None:
        """Cleanup PDH resources."""
        if self._gpu_query:
            try:
                pdh_dll.PdhCloseQuery(self._gpu_query)
            except Exception:
                pass

