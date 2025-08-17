"""Sepia theme for S3 TUI.

Vintage-inspired warm sepia tones for a nostalgic, easy-on-the-eyes experience.
"""

from textual.theme import Theme

sepia_theme = Theme(
    name="Sepia",
    primary="#8b4513",
    secondary="#2f1b14",
    accent="#cd853f",
    foreground="#2f1b14",
    background="#f5deb3",
    success="#6b8e23",
    warning="#ff8c00",
    error="#8b0000",
    surface="#deb887",
    panel="#d2b48c",
    boost="#bc9a6a",
    dark=False,
    variables={
        # Text colors
        "text-primary": "#2f1b14",
        "text-secondary": "#5d4e37",
        "text-muted": "#8b7355",
        "text-disabled": "#a0826d",
        "text-bright": "#000000",
        # Border colors
        "border-color": "#bc9a6a",
        "border-focus": "#8b4513",
        "border-selected": "#cd853f",
        # Button styles
        "button-foreground": "#2f1b14",
        "button-color-foreground": "#f5deb3",
        "button-focus-text-style": "bold",
        # Footer styles
        "footer-foreground": "#2f1b14",
        "footer-background": "#deb887",
        "footer-key-foreground": "#8b4513",
        "footer-key-background": "transparent",
        # Link styles
        "link-color": "#8b4513",
        "link-color-hover": "#cd853f",
        "link-background": "transparent",
        "link-background-hover": "#8b4513 20%",
        # Scrollbar colors
        "scrollbar-background": "#deb887",
        "scrollbar-color": "#bc9a6a",
        "scrollbar-color-active": "#8b4513",
        # Input selection
        "input-selection-background": "#8b4513 35%",
        # Block cursor
        "block-cursor-foreground": "#f5deb3",
        "block-cursor-text-style": "none",
    },
)
