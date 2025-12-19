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
from packages.core.monitor.session_monitor import SessionMonitor, MonitorState
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


class GameListItem(QWidget):
    """Custom list item widget for games with BodyLabel font style - matches ReminderListItem structure."""

    def __init__(self, game_name: str, parent=None):
        super().__init__(parent)
        self.game_name = game_name

        layout = QHBoxLayout(self)
        # Match ReminderListItem exactly: same margins and spacing
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        # Fix: Ensure the widget itself can expand horizontally to prevent clipping
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Text label - match ReminderListItem exactly
        # Fix: Enable word wrap and set expanding size policy to prevent text truncation
        # Root cause: QLabel without wordWrap truncates long text, and without Expanding
        # size policy it doesn't use available horizontal space in the layout
        self.text_label = QLabel(game_name)
        self.text_label.setObjectName("BodyLabel")
        self.text_label.setWordWrap(True)  # Allow text to wrap to multiple lines
        self.text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)  # Expand horizontally
        layout.addWidget(self.text_label, 1)

        layout.addStretch()


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

        self.monitor = SessionMonitor(
            config=self.cfg.to_monitor_config(),
            resource_heuristic=None,
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

        # Main content: Games and Reminders cards (responsive: side-by-side when wide)
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
        """Build main content area with Games and Reminders cards."""
        # Container for responsive layout
        main_container = QWidget()
        main_container_layout = QHBoxLayout(main_container)
        main_container_layout.setContentsMargins(0, 0, 0, 0)
        main_container_layout.setSpacing(20)

        # Games card
        games_card = Card()
        games_layout = games_card.layout

        games_label = QLabel("Games")
        games_label.setObjectName("SectionLabel")
        games_layout.addWidget(games_label)

        games_hint = QLabel("Track which games should trigger reminders.")
        games_hint.setObjectName("HintLabel")
        games_layout.addWidget(games_hint)

        # Input row
        games_input_row = QHBoxLayout()
        games_input_row.setSpacing(8)
        self.game_input = QLineEdit()
        self.game_input.setPlaceholderText("Add game exe… e.g. eldenring.exe")
        self.game_input.returnPressed.connect(self._add_game)
        games_input_row.addWidget(self.game_input)

        self.btn_add_game = IconButton("+")
        self.btn_add_game.clicked.connect(self._add_game)
        games_input_row.addWidget(self.btn_add_game)
        games_layout.addLayout(games_input_row)

        # Games list
        self.games_list = QListWidget()
        self.games_list.itemDoubleClicked.connect(self._remove_game_item)
        games_layout.addWidget(self.games_list)

        main_container_layout.addWidget(games_card, 1)

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

        # Thresholds row
        thresholds_row = QHBoxLayout()
        thresholds_row.setSpacing(12)

        poll_label = QLabel("Poll interval (ms):")
        poll_label.setObjectName("BodyLabel")
        thresholds_row.addWidget(poll_label)

        self.spin_poll = QSpinBox()
        self.spin_poll.setRange(250, 60000)
        self.spin_poll.setSingleStep(250)
        thresholds_row.addWidget(self.spin_poll)

        debounce_label = QLabel("End debounce (ms):")
        debounce_label.setObjectName("BodyLabel")
        thresholds_row.addWidget(debounce_label)

        self.spin_debounce = QSpinBox()
        self.spin_debounce.setRange(1000, 120000)
        self.spin_debounce.setSingleStep(500)
        thresholds_row.addWidget(self.spin_debounce)

        thresholds_row.addStretch()
        settings_layout.addLayout(thresholds_row)

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

        hint = QLabel("Tip: Double-click a game or reminder to remove it.")
        hint.setObjectName("HintLabel")
        events_layout.addWidget(hint)

        bottom_layout.addWidget(events_card, 1)

        parent_layout.addWidget(bottom_container, 1)

    def _load_to_ui(self) -> None:
        """Load configuration into UI elements."""
        self.chk_sound.setChecked(self.cfg.sound_enabled)
        self.spin_poll.setValue(self.cfg.poll_interval_ms)
        self.spin_debounce.setValue(self.cfg.end_debounce_ms)
        self._render_games()
        self._render_reminders()
        self._refresh_status()

    def _render_games(self) -> None:
        """Render games list with BodyLabel font style matching reminders."""
        self.games_list.clear()
        for g in self.cfg.games:
            # Create custom widget item - match ReminderListItem rendering exactly
            item_widget = GameListItem(g)
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
            self.games_list.addItem(item)
            self.games_list.setItemWidget(item, item_widget)

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
        """Update status display."""
        state: MonitorState = self.monitor.get_state()
        is_running = state.status == "RUNNING"
        is_active = state.active_exe is not None

        # Update status pill
        status_text = state.status
        self.status_pill.setText(status_text)
        self.status_pill.setObjectName("StatusPillActive" if is_running else "StatusPill")
        self.status_pill.setStyleSheet(self.theme.get_stylesheet())

        # Update active pill
        active_text = state.active_exe or "No active game"
        self.active_pill.setText(active_text)
        self.active_pill.setObjectName("StatusPillActive" if is_active else "StatusPill")
        self.active_pill.setStyleSheet(self.theme.get_stylesheet())

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

    def _add_game(self) -> None:
        """Add game to tracking list."""
        exe = self.game_input.text().strip()
        if not exe:
            return
        if exe.lower() not in [g.lower() for g in self.cfg.games]:
            self.cfg.games.append(exe)
            self._render_games()
        self.game_input.setText("")

    def _remove_game_item(self, item: QListWidgetItem) -> None:
        """Remove game from tracking list."""
        widget = self.games_list.itemWidget(item)
        if widget and hasattr(widget, "game_name"):
            exe = widget.game_name
        else:
            # Fallback for direct text access if widget not found
            exe = item.text()
        self.cfg.games = [g for g in self.cfg.games if g != exe]
        self._render_games()

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
        self.cfg.poll_interval_ms = int(self.spin_poll.value())
        self.cfg.end_debounce_ms = int(self.spin_debounce.value())

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
            exe = evt.get("exe")
            reason = evt.get("reason")
            if t == "GAME_STARTED":
                self._append_event(f"GAME_STARTED: {exe}")
            elif t == "GAME_ENDED":
                self._append_event(f"GAME_ENDED: {exe} ({reason})")
                payload = build_reminder_payload(exe=exe, reminders=self.cfg.reminders)
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
