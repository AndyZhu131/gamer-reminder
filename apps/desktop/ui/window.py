"""
Main window UI with iOS Reminders-inspired design.
Refactored to use theme system and reusable components.
"""

from __future__ import annotations

import logging
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QSpinBox,
    QSizePolicy,
)

from packages.shared.config import AppConfig, ReminderMessage
from packages.shared.store import ConfigStore
from packages.core.monitor.hardware_monitor import HardwareSessionMonitor
from packages.core.monitor.hardware_detector import HardwareUsageDetector
from packages.core.monitor.types import MonitorState
from packages.core.reminders.reminder_engine import build_reminder_payload
from packages.core.reminders.notifier import Notifier, ToastNotifierWin10
from packages.core.reminders.sound import SoundPlayer, WinBeepSound

from .theme import Theme
from .components import (
    Card,
    PrimaryButton,
    SecondaryButton,
    IconButton,
    Chip,
    PriorityIndicator,
    StatusPill,
)

log = logging.getLogger(__name__)


class ReminderListItem(QWidget):
    """Custom list item widget for reminders with priority and tags (visual only)."""

    def __init__(self, reminder: ReminderMessage, parent=None):
        super().__init__(parent)
        # TODO: Add tag and priority persistence to ReminderMessage model
        # For now, these are visual-only placeholders
        self.reminder = reminder
        self._priority = "none"  # "high", "medium", "low", "none"
        self._tags = []  # List of tag names (visual only)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        # Fix: Ensure the widget itself can expand horizontally to prevent clipping
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Priority indicator
        self.priority_indicator = PriorityIndicator(self._priority, self)
        layout.addWidget(self.priority_indicator)

        # Text label
        # Fix: Enable word wrap and set expanding size policy to prevent text truncation
        # Root cause: QLabel without wordWrap truncates long text, and without Expanding
        # size policy it doesn't use available horizontal space in the layout
        self.text_label = QLabel(reminder.text)
        self.text_label.setObjectName("BodyLabel")
        self.text_label.setWordWrap(True)  # Allow text to wrap to multiple lines
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # Expand horizontally
        layout.addWidget(self.text_label, 1)

        # Tags (chips) - visual only
        tags_container = QHBoxLayout()
        tags_container.setSpacing(6)
        if self._tags:
            colors = ["blue", "green", "purple", "orange", "pink"]
            for idx, tag_name in enumerate(self._tags[:3]):  # Show max 3 tags
                # Cycle through accent colors for visual variety
                color = colors[idx % len(colors)]
                chip = Chip(tag_name, color, self)
                tags_container.addWidget(chip)
        layout.addLayout(tags_container)

        layout.addStretch()


class MainWindow(QMainWindow):
    """Main application window with iOS Reminders-inspired UI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Gamer Reminder")
        self.resize(1100, 800)
        self.setMinimumSize(800, 600)

        # Initialize theme (default: dark mode)
        self.theme = Theme("dark")
        self._dark_mode_enabled = True

        self.store = ConfigStore()
        self.cfg: AppConfig = self.store.load()

        self.notifier: Notifier = ToastNotifierWin10()
        self.sound: SoundPlayer = WinBeepSound()

        # Initialize hardware detector and monitor
        self.detector = HardwareUsageDetector()
        self.monitor = HardwareSessionMonitor(
            config=self.cfg.to_monitor_config(),
            detector=self.detector,
        )
        self.monitor.on_event(self._on_monitor_event)
        self.monitor.on_error(self._on_monitor_error)

        self._build_ui()
        self._apply_theme()
        self._load_to_ui()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start(800)

    def _apply_theme(self) -> None:
        """Apply current theme stylesheet to the window."""
        self.setStyleSheet(self.theme.get_stylesheet())

    def _toggle_dark_mode(self, checked: bool) -> None:
        """Toggle between light and dark mode based on checkbox state."""
        if checked != self._dark_mode_enabled:
            self.theme.toggle_mode()
            self._dark_mode_enabled = checked
            self._apply_theme()

    def _build_ui(self) -> None:
        """Build the complete UI layout with card-based design."""
        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Header section
        self._build_header(main_layout)

        # Status bar with controls
        self._build_status_bar(main_layout)

        # Main content: Metrics and Reminders cards (responsive: side-by-side when wide)
        self._build_main_content(main_layout)

        # Bottom section: Settings and Activity cards
        self._build_bottom_section(main_layout)

    def _build_header(self, parent_layout: QVBoxLayout) -> None:
        """Build header with title and subtitle."""
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        self.title_label = QLabel("Gamer Reminder")
        self.title_label.setObjectName("TitleLabel")
        header_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Gently nudge yourself when a game session ends.")
        self.subtitle_label.setObjectName("SubtitleLabel")
        header_layout.addWidget(self.subtitle_label)

        parent_layout.addLayout(header_layout)

    def _build_status_bar(self, parent_layout: QVBoxLayout) -> None:
        """Build status bar with status pills and control buttons."""
        status_row = QHBoxLayout()
        status_row.setSpacing(12)

        # Status pills
        self.status_pill = StatusPill("STOPPED", active=False)
        status_row.addWidget(self.status_pill)

        self.active_pill = StatusPill("No active game", active=False)
        status_row.addWidget(self.active_pill)

        status_row.addStretch()

        # Control buttons
        self.btn_start = PrimaryButton("Start Monitoring")
        self.btn_start.clicked.connect(self._start_monitoring)
        status_row.addWidget(self.btn_start)

        self.btn_stop = SecondaryButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_monitoring)
        status_row.addWidget(self.btn_stop)

        parent_layout.addLayout(status_row)

    def _build_main_content(self, parent_layout: QVBoxLayout) -> None:
        """Build main content area with Metrics and Reminders cards."""
        # Container for responsive layout
        main_container = QWidget()
        main_container_layout = QHBoxLayout(main_container)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.setSpacing(20)

        # Metrics card
        metrics_card = Card()
        metrics_layout = metrics_card.layout

        metrics_label = QLabel("Hardware Metrics")
        metrics_label.setObjectName("SectionLabel")
        metrics_layout.addWidget(metrics_label)

        metrics_hint = QLabel("Current GPU and CPU utilization while monitoring.")
        metrics_hint.setObjectName("HintLabel")
        metrics_layout.addWidget(metrics_hint)

        # GPU metric
        gpu_row = QHBoxLayout()
        gpu_row.setSpacing(12)
        gpu_label = QLabel("GPU:")
        gpu_label.setObjectName("BodyLabel")
        gpu_row.addWidget(gpu_label)
        self.gpu_value_label = QLabel("N/A")
        self.gpu_value_label.setObjectName("BodyLabel")
        gpu_row.addWidget(self.gpu_value_label)
        gpu_row.addStretch()
        metrics_layout.addLayout(gpu_row)

        # CPU metric
        cpu_row = QHBoxLayout()
        cpu_row.setSpacing(12)
        cpu_label = QLabel("CPU:")
        cpu_label.setObjectName("BodyLabel")
        cpu_row.addWidget(cpu_label)
        self.cpu_value_label = QLabel("N/A")
        self.cpu_value_label.setObjectName("BodyLabel")
        cpu_row.addWidget(self.cpu_value_label)
        cpu_row.addStretch()
        metrics_layout.addLayout(cpu_row)

        # Activity state
        state_row = QHBoxLayout()
        state_row.setSpacing(12)
        state_label = QLabel("State:")
        state_label.setObjectName("BodyLabel")
        state_row.addWidget(state_label)
        self.activity_state_label = QLabel("IDLE")
        self.activity_state_label.setObjectName("BodyLabel")
        state_row.addWidget(self.activity_state_label)
        state_row.addStretch()
        metrics_layout.addLayout(state_row)

        metrics_layout.addStretch()
        main_container_layout.addWidget(metrics_card, 1)

        # Reminders card
        rem_card = Card()
        rem_layout = rem_card.layout

        rem_label = QLabel("Reminders")
        rem_label.setObjectName("SectionLabel")
        rem_layout.addWidget(rem_label)

        rem_hint = QLabel("What should you see when a session ends?")
        rem_hint.setObjectName("HintLabel")
        rem_layout.addWidget(rem_hint)

        # Input row
        rem_input_row = QHBoxLayout()
        rem_input_row.setSpacing(8)
        self.rem_input = QLineEdit()
        self.rem_input.setPlaceholderText("New reminder… e.g. Drink water")
        self.rem_input.returnPressed.connect(self._add_reminder)
        rem_input_row.addWidget(self.rem_input)

        self.btn_add_rem = IconButton("+")
        self.btn_add_rem.clicked.connect(self._add_reminder)
        rem_input_row.addWidget(self.btn_add_rem)
        rem_layout.addLayout(rem_input_row)

        # Reminders list (will use custom items)
        self.rem_list = QListWidget()
        self.rem_list.itemDoubleClicked.connect(self._remove_rem_item)
        rem_layout.addWidget(self.rem_list)

        main_container_layout.addWidget(rem_card, 1)

        parent_layout.addWidget(main_container, 1)

    def _build_bottom_section(self, parent_layout: QVBoxLayout) -> None:
        """Build bottom section with Settings and Activity cards."""
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(20)

        # Settings card
        settings_card = Card()
        settings_layout = settings_card.layout

        settings_label = QLabel("Settings")
        settings_label.setObjectName("SectionLabel")
        settings_layout.addWidget(settings_label)

        # Dark mode toggle
        self.chk_dark_mode = QCheckBox("Dark mode")
        self.chk_dark_mode.setChecked(self._dark_mode_enabled)
        self.chk_dark_mode.toggled.connect(lambda checked: self._toggle_dark_mode(checked))
        settings_layout.addWidget(self.chk_dark_mode)

        # Sound toggle
        self.chk_sound = QCheckBox("Play sound when a game session ends")
        settings_layout.addWidget(self.chk_sound)

        # GPU thresholds
        gpu_thresholds_row = QHBoxLayout()
        gpu_thresholds_row.setSpacing(12)

        active_gpu_label = QLabel("Active GPU threshold (%):")
        active_gpu_label.setObjectName("BodyLabel")
        gpu_thresholds_row.addWidget(active_gpu_label)

        self.spin_active_gpu = QSpinBox()
        self.spin_active_gpu.setRange(0, 100)
        self.spin_active_gpu.setSingleStep(5)
        gpu_thresholds_row.addWidget(self.spin_active_gpu)

        inactive_gpu_label = QLabel("Inactive GPU threshold (%):")
        inactive_gpu_label.setObjectName("BodyLabel")
        gpu_thresholds_row.addWidget(inactive_gpu_label)

        self.spin_inactive_gpu = QSpinBox()
        self.spin_inactive_gpu.setRange(0, 100)
        self.spin_inactive_gpu.setSingleStep(5)
        gpu_thresholds_row.addWidget(self.spin_inactive_gpu)

        gpu_thresholds_row.addStretch()
        settings_layout.addLayout(gpu_thresholds_row)

        # Timing settings
        timing_row = QHBoxLayout()
        timing_row.setSpacing(12)

        hold_label = QLabel("Inactive hold (seconds):")
        hold_label.setObjectName("BodyLabel")
        timing_row.addWidget(hold_label)

        self.spin_hold_seconds = QSpinBox()
        self.spin_hold_seconds.setRange(1, 120)
        self.spin_hold_seconds.setSingleStep(1)
        timing_row.addWidget(self.spin_hold_seconds)

        sample_label = QLabel("Sample interval (ms):")
        sample_label.setObjectName("BodyLabel")
        timing_row.addWidget(sample_label)

        self.spin_sample_interval = QSpinBox()
        self.spin_sample_interval.setRange(250, 10000)
        self.spin_sample_interval.setSingleStep(250)
        timing_row.addWidget(self.spin_sample_interval)

        timing_row.addStretch()
        settings_layout.addLayout(timing_row)

        # Save button
        self.btn_save = SecondaryButton("Save Settings")
        self.btn_save.clicked.connect(self._save_config)
        settings_layout.addWidget(self.btn_save)

        bottom_layout.addWidget(settings_card, 1)

        # Activity card
        events_card = Card()
        events_layout = events_card.layout

        events_label = QLabel("Activity")
        events_label.setObjectName("SectionLabel")
        events_layout.addWidget(events_label)

        self.events = QListWidget()
        events_layout.addWidget(self.events, 1)

        hint = QLabel("Tip: Double-click a reminder to remove it.")
        hint.setObjectName("HintLabel")
        events_layout.addWidget(hint)

        bottom_layout.addWidget(events_card, 1)

        parent_layout.addWidget(bottom_container, 1)

    def _load_to_ui(self) -> None:
        """Load configuration into UI elements."""
        self.chk_sound.setChecked(self.cfg.sound_enabled)
        self.spin_active_gpu.setValue(self.cfg.active_gpu_threshold)
        self.spin_inactive_gpu.setValue(self.cfg.inactive_gpu_threshold)
        self.spin_hold_seconds.setValue(self.cfg.inactive_hold_seconds)
        self.spin_sample_interval.setValue(self.cfg.sample_interval_ms)
        self._render_reminders()
        self._refresh_status()


    def _render_reminders(self) -> None:
        """Render reminders list with custom items (priority + tags visual only)."""
        self.rem_list.clear()
        for r in self.cfg.reminders:
            # Create custom widget item
            item_widget = ReminderListItem(r)
            item = QListWidgetItem()
            # Fix: When using setItemWidget, the widget automatically sizes to list width.
            # We just need a reasonable height hint. The width will be handled by the
            # QListWidget itself, and our QLabel with wordWrap and Expanding policy will
            # properly fill the available space.
            hint = item_widget.sizeHint()
            # Ensure minimum height but don't constrain width (let it expand naturally)
            # Increased height for better readability and spacing
            hint.setHeight(max(hint.height(), 56))  # Increased from 44px to 56px
            item.setSizeHint(hint)
            self.rem_list.addItem(item)
            self.rem_list.setItemWidget(item, item_widget)

    def _refresh_status(self) -> None:
        """Update status display and metrics."""
        state: MonitorState = self.monitor.get_state()
        hw_state = self.monitor.get_hardware_state()
        is_running = state.status == "RUNNING"

        # Update status pill
        status_text = state.status
        self.status_pill.setText(status_text)
        self.status_pill.setObjectName("StatusPillActive" if is_running else "StatusPill")
        self.status_pill.setStyleSheet(self.theme.get_stylesheet())

        # Update activity state pill
        activity_text = hw_state.activity_state if is_running else "IDLE"
        self.active_pill.setText(activity_text)
        self.active_pill.setObjectName("StatusPillActive" if hw_state.activity_state == "ACTIVE" else "StatusPill")
        self.active_pill.setStyleSheet(self.theme.get_stylesheet())

        # Update metrics display
        if hw_state.current_metrics:
            metrics = hw_state.current_metrics
            if metrics.gpu_utilization is not None:
                self.gpu_value_label.setText(f"{metrics.gpu_utilization:.1f}%")
            else:
                self.gpu_value_label.setText("N/A (using CPU)")
            self.cpu_value_label.setText(f"{metrics.cpu_utilization:.1f}%")
            self.activity_state_label.setText(hw_state.activity_state)
        else:
            self.gpu_value_label.setText("N/A")
            self.cpu_value_label.setText("N/A")
            self.activity_state_label.setText("IDLE")

    def _append_event(self, line: str) -> None:
        """Append event to activity log."""
        self.events.insertItem(0, QListWidgetItem(line))

    def _start_monitoring(self) -> None:
        """Start monitoring."""
        self.monitor.update_config(self.cfg.to_monitor_config())
        self.monitor.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._append_event("Monitoring started.")

    def _stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.monitor.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._append_event("Monitoring stopped.")


    def _add_reminder(self) -> None:
        """Add reminder message."""
        text = self.rem_input.text().strip()
        if not text:
            return
        self.cfg.reminders.append(ReminderMessage(text=text))
        self._render_reminders()
        self.rem_input.setText("")

    def _remove_rem_item(self, item: QListWidgetItem) -> None:
        """Remove reminder from list."""
        widget = self.rem_list.itemWidget(item)
        if widget and hasattr(widget, "reminder"):
            reminder = widget.reminder
            self.cfg.reminders = [r for r in self.cfg.reminders if r.id != reminder.id]
            self._render_reminders()

    def _save_config(self) -> None:
        """Save configuration."""
        self.cfg.sound_enabled = self.chk_sound.isChecked()
        self.cfg.active_gpu_threshold = int(self.spin_active_gpu.value())
        self.cfg.inactive_gpu_threshold = int(self.spin_inactive_gpu.value())
        self.cfg.inactive_hold_seconds = int(self.spin_hold_seconds.value())
        self.cfg.sample_interval_ms = int(self.spin_sample_interval.value())

        self.store.save(self.cfg)
        self._append_event("Config saved.")

        if self.monitor.get_state().status == "RUNNING":
            self.monitor.stop()
            self.monitor.update_config(self.cfg.to_monitor_config())
            self.monitor.start()
            self._append_event("Monitoring restarted to apply config.")

    def _on_monitor_event(self, evt: dict) -> None:
        """Handle monitor events."""
        def handle() -> None:
            t = evt.get("type")
            exe = evt.get("exe", "Gaming Session")
            reason = evt.get("reason", "")
            metrics = evt.get("metrics", {})
            
            if t == "GAME_STARTED":
                gpu_str = f"GPU {metrics.get('gpu', 'N/A')}%" if metrics.get('gpu') else "CPU fallback"
                self._append_event(f"GAME_STARTED: {exe} ({reason})")
            elif t == "GAME_ENDED":
                # Format metrics for log
                gpu_val = metrics.get("gpu")
                cpu_val = metrics.get("cpu", 0)
                if gpu_val is not None:
                    metrics_str = f"GPU {gpu_val:.1f}%, CPU {cpu_val:.1f}%"
                else:
                    metrics_str = f"CPU {cpu_val:.1f}% (GPU N/A)"
                self._append_event(f"GAME_ENDED: {exe} - {reason} [{metrics_str}]")
                payload = build_reminder_payload(reminders=self.cfg.reminders, session_name=exe)
                self.notifier.notify(payload["title"], payload["body"])
                if self.cfg.sound_enabled:
                    self.sound.play()

        QTimer.singleShot(0, handle)

    def _on_monitor_error(self, msg: str) -> None:
        """Handle monitor errors."""
        def handle() -> None:
            self._append_event(f"ERROR: {msg}")
            log.error("Monitor error: %s", msg)
        QTimer.singleShot(0, handle)
