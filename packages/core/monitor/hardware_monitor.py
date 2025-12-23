"""
Hardware-based gaming activity monitor using GPU/CPU utilization.

State machine: IDLE -> ACTIVE -> SUSPECT_INACTIVE -> INACTIVE
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Literal, Optional

from .detector import ActivityDetector, HardwareMetrics
from .types import MonitorState

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


ActivityState = Literal["IDLE", "ACTIVE", "PAUSED", "SUSPECT_INACTIVE", "INACTIVE"]


@dataclass
class HardwareMonitorConfig:
    """Configuration for hardware-based monitoring."""
    active_gpu_threshold: int  # 0-100
    inactive_gpu_threshold: int  # 0-100
    inactive_hold_seconds: int  # seconds
    sample_interval_ms: int  # milliseconds
    paused_gpu_threshold: int  # 0-100
    paused_stable_seconds: int  # seconds


@dataclass
class HardwareMonitorState:
    """State for hardware-based monitoring."""
    status: Literal["STOPPED", "RUNNING"] = "STOPPED"
    activity_state: ActivityState = "IDLE"
    current_metrics: Optional[HardwareMetrics] = None
    suspect_inactive_since_ms: Optional[int] = None
    last_event_type: Optional[str] = None  # For debouncing
    paused_stable_since_ms: Optional[int] = None  # When stable GPU usage started


class HardwareSessionMonitor:
    """
    Background monitor that emits GAME_STARTED / GAME_ENDED based on
    hardware utilization (GPU/CPU).
    """

    def __init__(
        self,
        config: dict,
        detector: Optional[ActivityDetector] = None
    ) -> None:
        self._cfg = self._parse_config(config)
        self._detector = detector
        self._state = HardwareMonitorState()
        self._lock = threading.Lock()

        self._event_cb: Optional[Callable[[dict], None]] = None
        self._error_cb: Optional[Callable[[str], None]] = None

        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        
        # Track GPU usage history for variance detection (paused state)
        # Store (timestamp_ms, gpu_utilization) tuples
        self._gpu_history: deque[tuple[int, float]] = deque(maxlen=20)  # Keep last 20 samples

    @staticmethod
    def _parse_config(config: dict) -> HardwareMonitorConfig:
        """Parse config dict into HardwareMonitorConfig."""
        return HardwareMonitorConfig(
            active_gpu_threshold=config.get("active_gpu_threshold", 80),
            inactive_gpu_threshold=config.get("inactive_gpu_threshold", 35),
            inactive_hold_seconds=config.get("inactive_hold_seconds", 10),
            sample_interval_ms=config.get("sample_interval_ms", 1000),
            paused_gpu_threshold=config.get("paused_gpu_threshold", 60),
            paused_stable_seconds=config.get("paused_stable_seconds", 10),
        )

    def on_event(self, cb: Callable[[dict], None]) -> None:
        self._event_cb = cb

    def on_error(self, cb: Callable[[str], None]) -> None:
        self._error_cb = cb

    def update_config(self, config: dict) -> None:
        with self._lock:
            self._cfg = self._parse_config(config)

    def get_state(self) -> MonitorState:
        """Get state in legacy MonitorState format for UI compatibility."""
        with self._lock:
            # Map hardware monitor state to legacy state
            status = self._state.status
            # For legacy compatibility, use activity_state as "active_exe" equivalent
            # Only show as "active" if in ACTIVE state
            active_exe = self._state.activity_state if (status == "RUNNING" and self._state.activity_state == "ACTIVE") else None
            return MonitorState(
                status=status,
                active_exe=active_exe,
                missing_since_ms=self._state.suspect_inactive_since_ms,
            )

    def get_hardware_state(self) -> HardwareMonitorState:
        """Get full hardware monitor state."""
        with self._lock:
            return HardwareMonitorState(
                status=self._state.status,
                activity_state=self._state.activity_state,
                current_metrics=self._state.current_metrics,
                suspect_inactive_since_ms=self._state.suspect_inactive_since_ms,
                last_event_type=self._state.last_event_type,
                paused_stable_since_ms=self._state.paused_stable_since_ms,
            )

    def start(self) -> None:
        with self._lock:
            if self._state.status == "RUNNING":
                return
            self._state.status = "RUNNING"
            self._state.activity_state = "IDLE"
            self._state.current_metrics = None
            self._state.suspect_inactive_since_ms = None
            self._state.paused_stable_since_ms = None
            self._state.last_event_type = None
            self._gpu_history.clear()

        if self._detector is None:
            self._emit_error("No detector provided")
            return

        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, name="HardwareSessionMonitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        with self._lock:
            self._state.status = "STOPPED"
            self._state.activity_state = "IDLE"
            self._state.current_metrics = None
            self._state.suspect_inactive_since_ms = None
            self._state.paused_stable_since_ms = None
            self._gpu_history.clear()

    def _emit(self, evt: dict) -> None:
        if self._event_cb:
            self._event_cb(evt)

    def _emit_error(self, msg: str) -> None:
        if self._error_cb:
            self._error_cb(msg)
    
    def _is_gpu_stable_around_threshold(
        self, 
        threshold: float, 
        stable_window_ms: int,
        variance_threshold: float = 5.0
    ) -> tuple[bool, Optional[int]]:
        """
        Check if GPU usage has been stable (low variance) around threshold for stable_window_ms.
        
        Args:
            threshold: Target GPU utilization threshold
            stable_window_ms: Required duration of stability in milliseconds
            variance_threshold: Maximum allowed variance (default 5%)
        
        Returns:
            (is_stable, stable_since_ms): True if stable, and timestamp when stability started
        """
        if len(self._gpu_history) < 3:
            return False, None
        
        # Filter samples within the stable window
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - stable_window_ms
        
        # Get samples within the window
        window_samples = [
            (ts, util) for ts, util in self._gpu_history
            if ts >= window_start_ms
        ]
        
        if len(window_samples) < 3:
            return False, None
        
        # Extract GPU values
        gpu_values = [util for _, util in window_samples]
        
        # Check if values are around threshold (±variance_threshold)
        threshold_min = threshold - variance_threshold
        threshold_max = threshold + variance_threshold
        
        all_near_threshold = all(
            threshold_min <= val <= threshold_max 
            for val in gpu_values
        )
        
        if not all_near_threshold:
            return False, None
        
        # Check variance (standard deviation)
        import statistics
        if len(gpu_values) >= 2:
            std_dev = statistics.stdev(gpu_values)
            if std_dev > variance_threshold:
                return False, None
        
        # Find when stability started (first sample in window)
        stable_since_ms = window_samples[0][0]
        return True, stable_since_ms

    def _run(self) -> None:
        """Main monitoring loop implementing state machine."""
        while not self._stop_evt.is_set():
            try:
                with self._lock:
                    cfg = self._cfg
                    state = self._state

                # Sample hardware metrics
                metrics = self._detector.sample()
                
                with self._lock:
                    self._state.current_metrics = metrics

                # Determine effective utilization (prefer GPU, fallback to CPU)
                effective_util = metrics.gpu_utilization
                using_cpu_fallback = (effective_util is None)
                if using_cpu_fallback:
                    # Fallback to CPU if GPU unavailable
                    effective_util = metrics.cpu_utilization
                    log.debug("Using CPU utilization (GPU unavailable)")
                
                # Track GPU history for paused detection (only if GPU available)
                now_ms = int(time.time() * 1000)
                if metrics.gpu_utilization is not None:
                    with self._lock:
                        self._gpu_history.append((now_ms, metrics.gpu_utilization))

                # State machine transitions
                current_state = state.activity_state

                if current_state == "IDLE":
                    if effective_util >= cfg.active_gpu_threshold:
                        # Transition to ACTIVE
                        with self._lock:
                            self._state.activity_state = "ACTIVE"
                            self._state.suspect_inactive_since_ms = None
                        util_type = "CPU" if using_cpu_fallback else "GPU"
                        self._emit({
                            "type": "GAME_STARTED",
                            "exe": "Gaming Session",
                            "at": _now_iso(),
                            "reason": f"{util_type} {effective_util:.1f}% >= {cfg.active_gpu_threshold}%",
                            "metrics": {
                                "gpu": metrics.gpu_utilization,
                                "cpu": metrics.cpu_utilization,
                            }
                        })
                        with self._lock:
                            self._state.last_event_type = "GAME_STARTED"

                elif current_state == "ACTIVE":
                    if effective_util <= cfg.inactive_gpu_threshold:
                        # Transition to SUSPECT_INACTIVE
                        with self._lock:
                            self._state.activity_state = "SUSPECT_INACTIVE"
                            self._state.paused_stable_since_ms = None
                            if self._state.suspect_inactive_since_ms is None:
                                self._state.suspect_inactive_since_ms = now_ms
                    # Check for paused condition (stable GPU around paused threshold)
                    elif (not using_cpu_fallback and 
                          metrics.gpu_utilization is not None):
                        # Check if GPU usage is stable around paused threshold
                        stable_window_ms = cfg.paused_stable_seconds * 1000
                        is_stable, stable_since_ms = self._is_gpu_stable_around_threshold(
                            cfg.paused_gpu_threshold,
                            stable_window_ms,
                            variance_threshold=5.0  # ±5% variance allowed
                        )
                        
                        if is_stable and stable_since_ms is not None:
                            # Transition to PAUSED
                            with self._lock:
                                self._state.activity_state = "PAUSED"
                                if self._state.paused_stable_since_ms is None:
                                    self._state.paused_stable_since_ms = stable_since_ms
                                self._state.suspect_inactive_since_ms = None
                            log.info(f"Game paused detected: GPU stable at {metrics.gpu_utilization:.1f}% around {cfg.paused_gpu_threshold}% threshold")
                    # If still active, reset timers
                    elif effective_util >= cfg.active_gpu_threshold:
                        with self._lock:
                            self._state.suspect_inactive_since_ms = None
                            self._state.paused_stable_since_ms = None

                elif current_state == "PAUSED":
                    # From PAUSED, check for recovery or further inactivity
                    if effective_util >= cfg.active_gpu_threshold:
                        # Recovery: back to ACTIVE (game resumed)
                        with self._lock:
                            self._state.activity_state = "ACTIVE"
                            self._state.paused_stable_since_ms = None
                            self._state.suspect_inactive_since_ms = None
                        log.info("Game resumed: GPU utilization increased")
                    elif effective_util <= cfg.inactive_gpu_threshold:
                        # Transition to SUSPECT_INACTIVE (game may have ended)
                        with self._lock:
                            self._state.activity_state = "SUSPECT_INACTIVE"
                            self._state.paused_stable_since_ms = None
                            if self._state.suspect_inactive_since_ms is None:
                                self._state.suspect_inactive_since_ms = now_ms
                    # If still paused, check if stability is broken
                    elif (not using_cpu_fallback and 
                          metrics.gpu_utilization is not None):
                        # Check if GPU usage is no longer stable
                        stable_window_ms = cfg.paused_stable_seconds * 1000
                        is_stable, _ = self._is_gpu_stable_around_threshold(
                            cfg.paused_gpu_threshold,
                            stable_window_ms,
                            variance_threshold=5.0
                        )
                        if not is_stable:
                            # GPU usage changed, return to ACTIVE
                            with self._lock:
                                self._state.activity_state = "ACTIVE"
                                self._state.paused_stable_since_ms = None
                            log.info("Game resumed: GPU usage variance detected")
                
                elif current_state == "SUSPECT_INACTIVE":
                    if effective_util >= cfg.active_gpu_threshold:
                        # Recovery: back to ACTIVE
                        with self._lock:
                            self._state.activity_state = "ACTIVE"
                            self._state.suspect_inactive_since_ms = None
                            self._state.paused_stable_since_ms = None
                    elif effective_util <= cfg.inactive_gpu_threshold:
                        # Check if hold time elapsed
                        if state.suspect_inactive_since_ms is not None:
                            hold_ms = cfg.inactive_hold_seconds * 1000
                            elapsed = now_ms - state.suspect_inactive_since_ms
                            if elapsed >= hold_ms:
                                # Transition to INACTIVE
                                with self._lock:
                                    self._state.activity_state = "INACTIVE"
                                    self._state.suspect_inactive_since_ms = None
                                
                                # Emit GAME_ENDED (debounced: only once per transition)
                                if state.last_event_type != "GAME_ENDED":
                                    util_type = "CPU" if metrics.gpu_utilization is None else "GPU"
                                    util_str = f"{effective_util:.1f}%"
                                    self._emit({
                                        "type": "GAME_ENDED",
                                        "exe": "Gaming Session",
                                        "at": _now_iso(),
                                        "reason": f"{util_type} {util_str} <= {cfg.inactive_gpu_threshold}% for {cfg.inactive_hold_seconds}s",
                                        "metrics": {
                                            "gpu": metrics.gpu_utilization,
                                            "cpu": metrics.cpu_utilization,
                                        }
                                    })
                                    with self._lock:
                                        self._state.last_event_type = "GAME_ENDED"

                elif current_state == "INACTIVE":
                    if effective_util >= cfg.active_gpu_threshold:
                        # Recovery: back to ACTIVE (allows future inactivity events)
                        with self._lock:
                            self._state.activity_state = "ACTIVE"
                            self._state.suspect_inactive_since_ms = None
                            self._state.paused_stable_since_ms = None
                            self._state.last_event_type = None  # Reset debounce
                        util_type = "CPU" if using_cpu_fallback else "GPU"
                        self._emit({
                            "type": "GAME_STARTED",
                            "exe": "Gaming Session",
                            "at": _now_iso(),
                            "reason": f"{util_type} {effective_util:.1f}% >= {cfg.active_gpu_threshold}%",
                            "metrics": {
                                "gpu": metrics.gpu_utilization,
                                "cpu": metrics.cpu_utilization,
                            }
                        })
                        with self._lock:
                            self._state.last_event_type = "GAME_STARTED"

                # Sleep for sample interval
                time.sleep(cfg.sample_interval_ms / 1000.0)

            except Exception as e:
                log.exception("Monitor loop error")
                self._emit_error(str(e))
                time.sleep(1.0)

