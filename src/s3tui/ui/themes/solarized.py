"""Solarized theme for S3 TUI.

Well-balanced color scheme designed for long coding sessions with reduced eye strain.
"""

from textual.theme import Theme

solarized_theme = Theme(
    name="Solarized",
    primary="#268bd2",
    secondary="#fdf6e3",
    accent="#b58900",
    foreground="#839496",
    background="#002b36",
    success="#859900",
    warning="#cb4b16",
    error="#dc322f",
    surface="#073642",
    panel="#073642",
    boost="#586e75",
    dark=True,
    variables={
        # Text colors
        "text-primary": "#839496",
        "text-secondary": "#93a1a1",
        "text-muted": "#586e75",
        "text-disabled": "#073642",
        "text-bright": "#eee8d5",
        # Border colors
        "border-color": "#073642",
        "border-focus": "#268bd2",
        "border-selected": "#b58900",
        # Button styles
        "button-foreground": "#839496",
        "button-color-foreground": "#002b36",
        "button-focus-text-style": "bold",
        # Footer styles
        "footer-foreground": "#839496",
        "footer-background": "#073642",
        "footer-key-foreground": "#268bd2",
        "footer-key-background": "transparent",
        # Link styles
        "link-color": "#268bd2",
        "link-color-hover": "#6c71c4",
        "link-background": "transparent",
        "link-background-hover": "#268bd2 20%",
        # Scrollbar colors
        "scrollbar-background": "#073642",
        "scrollbar-color": "#586e75",
        "scrollbar-color-active": "#268bd2",
        # Input selection
        "input-selection-background": "#268bd2 35%",
        # Block cursor
        "block-cursor-foreground": "#002b36",
        "block-cursor-text-style": "none",
    },
)
