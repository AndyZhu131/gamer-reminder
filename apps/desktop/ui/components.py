"""
Reusable UI components for iOS Reminders-inspired design.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from .theme import COLOR_ACCENTS, PRIORITY_COLORS


class Card(QFrame):
    """Card container with rounded corners and subtle styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(12)


class PrimaryButton(QPushButton):
    """Primary action button with iOS-style appearance."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("PrimaryButton")


class SecondaryButton(QPushButton):
    """Secondary action button with iOS-style appearance."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("SecondaryButton")


class IconButton(QPushButton):
    """Small circular icon button (e.g., for +, - actions)."""

    def __init__(self, text: str = "+", parent=None):
        super().__init__(text, parent)
        self.setObjectName("IconButton")


class Chip(QLabel):
    """Colored tag chip for categories/tags."""

    def __init__(self, text: str, color: str | None = None, parent=None):
        super().__init__(text, parent)
        self.setObjectName("Chip")
        
        # Apply accent color if provided
        if color and color in COLOR_ACCENTS:
            accent_color = COLOR_ACCENTS[color]
            self.setStyleSheet(
                f"""
                QLabel#Chip {{
                    background-color: rgba({self._hex_to_rgb(accent_color)}, 0.15);
                    color: {accent_color};
                    border-radius: 12px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }}
                """
            )

    def _hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex to RGB string for rgba."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"{r}, {g}, {b}"


class PriorityIndicator(QLabel):
    """Visual priority indicator (colored bar)."""

    def __init__(self, priority: str = "none", parent=None):
        super().__init__(parent)
        self.setObjectName("PriorityIndicator")
        self.setFixedWidth(4)
        self.setMinimumHeight(20)
        
        color = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["none"])
        self.setStyleSheet(
            f"""
            QLabel#PriorityIndicator {{
                background-color: {color};
                border-radius: 4px;
            }}
            """
        )


class StatusPill(QLabel):
    """Status indicator pill (e.g., "RUNNING", "STOPPED")."""

    def __init__(self, text: str = "", active: bool = False, parent=None):
        super().__init__(text, parent)
        self.setObjectName("StatusPillActive" if active else "StatusPill")

