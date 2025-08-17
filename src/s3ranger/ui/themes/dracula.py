"""Dracula theme for S3 TUI.

Popular dark theme with subtle purple tones and excellent readability.
"""

from textual.theme import Theme

dracula_theme = Theme(
    name="Dracula",
    primary="#bd93f9",
    secondary="#f8f8f2",
    accent="#ff79c6",
    foreground="#f8f8f2",
    background="#282a36",
    success="#50fa7b",
    warning="#f1fa8c",
    error="#ff5555",
    surface="#44475a",
    panel="#44475a",
    boost="#6272a4",
    dark=True,
    variables={
        # Text colors
        "text-primary": "#f8f8f2",
        "text-secondary": "#6272a4",
        "text-muted": "#6272a4",
        "text-disabled": "#44475a",
        "text-bright": "#ffffff",
        # Border colors
        "border-color": "#44475a",
        "border-focus": "#bd93f9",
        "border-selected": "#ff79c6",
        # Button styles
        "button-foreground": "#f8f8f2",
        "button-color-foreground": "#282a36",
        "button-focus-text-style": "bold",
        # Footer styles
        "footer-foreground": "#f8f8f2",
        "footer-background": "#44475a",
        "footer-key-foreground": "#bd93f9",
        "footer-key-background": "transparent",
        # Link styles
        "link-color": "#bd93f9",
        "link-color-hover": "#ff79c6",
        "link-background": "transparent",
        "link-background-hover": "#bd93f9 20%",
        # Scrollbar colors
        "scrollbar-background": "#44475a",
        "scrollbar-color": "#6272a4",
        "scrollbar-color-active": "#bd93f9",
        # Input selection
        "input-selection-background": "#bd93f9 35%",
        # Block cursor
        "block-cursor-foreground": "#282a36",
        "block-cursor-text-style": "none",
    },
)
