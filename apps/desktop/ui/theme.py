"""
Design system theme module for iOS Reminders-inspired UI.
Provides color palettes, spacing tokens, typography, and QSS generators for light/dark modes.
"""

from __future__ import annotations

from typing import Dict, Literal

# Design tokens: spacing (8px grid)
SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "24px",
    "2xl": "32px",
}

# Design tokens: typography
TYPOGRAPHY = {
    "font_family": "Segoe UI, -apple-system, BlinkMacSystemFont, sans-serif",
    "font_size_xs": "11px",
    "font_size_sm": "13px",
    "font_size_base": "15px",
    "font_size_lg": "17px",
    "font_size_xl": "22px",
    "font_size_2xl": "28px",
    "font_weight_normal": "400",
    "font_weight_medium": "500",
    "font_weight_semibold": "600",
    "font_weight_bold": "700",
    "line_height_tight": "1.2",
    "line_height_normal": "1.4",
    "line_height_relaxed": "1.6",
}

# Color palette: category accents (iOS-inspired)
COLOR_ACCENTS = {
    "blue": "#007AFF",
    "red": "#FF3B30",
    "orange": "#FF9500",
    "yellow": "#FFCC00",
    "green": "#34C759",
    "purple": "#AF52DE",
    "pink": "#FF2D55",
    "brown": "#A2845E",
    "gray": "#8E8E93",
}

# Priority colors
PRIORITY_COLORS = {
    "high": COLOR_ACCENTS["red"],
    "medium": COLOR_ACCENTS["orange"],
    "low": COLOR_ACCENTS["yellow"],
    "none": COLOR_ACCENTS["gray"],
}

# Light mode colors
LIGHT_COLORS = {
    "background": "#F5F5F7",
    "surface": "#FFFFFF",
    "surface_secondary": "#F9F9F9",
    "text_primary": "#000000",
    "text_secondary": "#6E6E73",
    "text_tertiary": "#8E8E93",
    "border": "#E5E5EA",
    "border_light": "#F2F2F7",
    "separator": "#C6C6C8",
    "card_shadow": "rgba(0, 0, 0, 0.05)",
    "overlay": "rgba(0, 0, 0, 0.4)",
}

# Dark mode colors
DARK_COLORS = {
    "background": "#000000",
    "surface": "#1C1C1E",
    "surface_secondary": "#2C2C2E",
    "text_primary": "#FFFFFF",
    "text_secondary": "#98989D",
    "text_tertiary": "#636366",
    "border": "#38383A",
    "border_light": "#2C2C2E",
    "separator": "#38383A",
    "card_shadow": "rgba(0, 0, 0, 0.3)",
    "overlay": "rgba(0, 0, 0, 0.6)",
}

ThemeMode = Literal["light", "dark"]


class Theme:
    """Theme manager providing QSS stylesheets for light and dark modes."""

    def __init__(self, mode: ThemeMode = "light"):
        self.mode = mode
        self.colors = LIGHT_COLORS if mode == "light" else DARK_COLORS

    def get_stylesheet(self) -> str:
        """Generate complete QSS stylesheet for current theme mode."""
        colors = self.colors
        font_family = TYPOGRAPHY["font_family"]

        return f"""
        /* Main window */
        QMainWindow {{
            background-color: {colors["background"]};
            color: {colors["text_primary"]};
        }}

        /* Typography: Title */
        QLabel#TitleLabel {{
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_2xl"]};
            font-weight: {TYPOGRAPHY["font_weight_bold"]};
            color: {colors["text_primary"]};
            line-height: {TYPOGRAPHY["line_height_tight"]};
        }}

        /* Typography: Subtitle */
        QLabel#SubtitleLabel {{
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_sm"]};
            font-weight: {TYPOGRAPHY["font_weight_normal"]};
            color: {colors["text_secondary"]};
            line-height: {TYPOGRAPHY["line_height_normal"]};
        }}

        /* Typography: Section Header */
        QLabel#SectionLabel {{
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_lg"]};
            font-weight: {TYPOGRAPHY["font_weight_semibold"]};
            color: {colors["text_primary"]};
            line-height: {TYPOGRAPHY["line_height_normal"]};
        }}

        /* Typography: Body */
        QLabel#BodyLabel {{
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            font-weight: {TYPOGRAPHY["font_weight_normal"]};
            color: {colors["text_primary"]};
            line-height: {TYPOGRAPHY["line_height_relaxed"]};
        }}

        /* Typography: Hint */
        QLabel#HintLabel {{
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_sm"]};
            font-weight: {TYPOGRAPHY["font_weight_normal"]};
            color: {colors["text_secondary"]};
            line-height: {TYPOGRAPHY["line_height_normal"]};
        }}

        /* Card container */
        QFrame#Card {{
            background-color: {colors["surface"]};
            border-radius: 16px;
            border: 1px solid {colors["border"]};
        }}

        /* Primary button */
        QPushButton#PrimaryButton {{
            background-color: {COLOR_ACCENTS["blue"]};
            color: #FFFFFF;
            border: none;
            border-radius: 20px;
            padding: {SPACING["sm"]} {SPACING["xl"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            font-weight: {TYPOGRAPHY["font_weight_semibold"]};
            min-height: 36px;
        }}

        QPushButton#PrimaryButton:hover {{
            background-color: {self._adjust_brightness(COLOR_ACCENTS["blue"], -10)};
        }}

        QPushButton#PrimaryButton:pressed {{
            background-color: {self._adjust_brightness(COLOR_ACCENTS["blue"], -20)};
        }}

        QPushButton#PrimaryButton:disabled {{
            background-color: {colors["border"]};
            color: {colors["text_tertiary"]};
        }}

        /* Secondary button */
        QPushButton#SecondaryButton {{
            background-color: {colors["surface_secondary"]};
            color: {COLOR_ACCENTS["blue"]};
            border: 1px solid {colors["border"]};
            border-radius: 20px;
            padding: {SPACING["sm"]} {SPACING["xl"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            font-weight: {TYPOGRAPHY["font_weight_medium"]};
            min-height: 36px;
        }}

        QPushButton#SecondaryButton:hover {{
            background-color: {colors["border_light"]};
        }}

        QPushButton#SecondaryButton:pressed {{
            background-color: {colors["border"]};
        }}

        QPushButton#SecondaryButton:disabled {{
            background-color: {colors["surface_secondary"]};
            color: {colors["text_tertiary"]};
            border-color: {colors["border"]};
        }}

        /* Icon button (small circular) */
        QPushButton#IconButton {{
            background-color: {colors["surface_secondary"]};
            color: {colors["text_primary"]};
            border: none;
            border-radius: 18px;
            padding: {SPACING["xs"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_lg"]};
            font-weight: {TYPOGRAPHY["font_weight_medium"]};
            min-width: 36px;
            min-height: 36px;
            max-width: 36px;
            max-height: 36px;
        }}

        QPushButton#IconButton:hover {{
            background-color: {colors["border_light"]};
        }}

        QPushButton#IconButton:pressed {{
            background-color: {colors["border"]};
        }}

        /* Text input */
        QLineEdit {{
            background-color: {colors["surface"]};
            color: {colors["text_primary"]};
            border: 1px solid {colors["border"]};
            border-radius: 10px;
            padding: {SPACING["sm"]} {SPACING["md"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            min-height: 36px;
        }}

        QLineEdit:focus {{
            border-color: {COLOR_ACCENTS["blue"]};
            background-color: {colors["surface"]};
        }}

        QLineEdit::placeholder {{
            color: {colors["text_tertiary"]};
        }}

        /* List widget */
        QListWidget {{
            background-color: transparent;
            border: none;
            padding: {SPACING["xs"]} 0;
            outline: none;
        }}

        QListWidget::item {{
            background-color: transparent;
            color: {colors["text_primary"]};
            padding: {SPACING["sm"]} {SPACING["md"]};
            border-radius: 8px;
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            min-height: 44px;
        }}

        QListWidget::item:hover {{
            background-color: {colors["surface_secondary"]};
        }}

        QListWidget::item:selected {{
            background-color: {self._rgba(COLOR_ACCENTS["blue"], 0.1)};
            color: {colors["text_primary"]};
        }}

        /* Checkbox */
        QCheckBox {{
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            color: {colors["text_primary"]};
            spacing: {SPACING["sm"]};
        }}

        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border-radius: 6px;
            border: 2px solid {colors["border"]};
            background-color: {colors["surface"]};
        }}

        QCheckBox::indicator:hover {{
            border-color: {COLOR_ACCENTS["blue"]};
        }}

        QCheckBox::indicator:checked {{
            background-color: {COLOR_ACCENTS["blue"]};
            border-color: {COLOR_ACCENTS["blue"]};
            image: none;
        }}

        QCheckBox::indicator:checked:after {{
            content: "✓";
            color: white;
            font-weight: bold;
        }}

        /* Spinbox */
        QSpinBox {{
            background-color: {colors["surface"]};
            color: {colors["text_primary"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: {SPACING["xs"]} {SPACING["sm"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_base"]};
            min-height: 32px;
        }}

        QSpinBox:focus {{
            border-color: {COLOR_ACCENTS["blue"]};
        }}

        QSpinBox::up-button, QSpinBox::down-button {{
            background-color: {colors["surface_secondary"]};
            border: none;
            border-radius: 4px;
            width: 20px;
        }}

        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {colors["border_light"]};
        }}

        /* Status pill */
        QLabel#StatusPill {{
            background-color: {colors["surface_secondary"]};
            color: {colors["text_secondary"]};
            border-radius: 12px;
            padding: {SPACING["xs"]} {SPACING["md"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_sm"]};
            font-weight: {TYPOGRAPHY["font_weight_medium"]};
        }}

        QLabel#StatusPillActive {{
            background-color: {self._rgba(COLOR_ACCENTS["green"], 0.15)};
            color: {COLOR_ACCENTS["green"]};
        }}

        QLabel#StatusPillPaused {{
            background-color: {self._rgba(COLOR_ACCENTS["orange"], 0.15)};
            color: {COLOR_ACCENTS["orange"]};
        }}

        QLabel#StatusPillStopped {{
            background-color: {self._rgba(COLOR_ACCENTS["gray"], 0.15)};
            color: {colors["text_secondary"]};
        }}

        /* Chip (tag) */
        QLabel#Chip {{
            background-color: {colors["surface_secondary"]};
            color: {colors["text_primary"]};
            border-radius: 12px;
            padding: {SPACING["xs"]} {SPACING["sm"]};
            font-family: {font_family};
            font-size: {TYPOGRAPHY["font_size_xs"]};
            font-weight: {TYPOGRAPHY["font_weight_medium"]};
        }}

        /* Priority indicator */
        QLabel#PriorityIndicator {{
            border-radius: 4px;
            min-width: 4px;
            max-width: 4px;
            min-height: 20px;
        }}
        """

    def _adjust_brightness(self, hex_color: str, percent: int) -> str:
        """Adjust color brightness (simple approximation)."""
        # Convert hex to RGB
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        
        # Adjust brightness
        factor = 1 + (percent / 100)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        
        return f"#{r:02x}{g:02x}{b:02x}"

    def _rgba(self, hex_color: str, alpha: float) -> str:
        """Convert hex color to rgba string."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"

    def toggle_mode(self) -> None:
        """Switch between light and dark mode."""
        self.mode = "dark" if self.mode == "light" else "light"
        self.colors = LIGHT_COLORS if self.mode == "light" else DARK_COLORS


