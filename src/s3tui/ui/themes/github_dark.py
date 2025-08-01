"""GitHub Dark theme for S3 TUI.

Professional, widely recognized, excellent contrast theme inspired by GitHub's dark theme.
"""

from textual.theme import Theme

github_dark_theme = Theme(
    name="Github Dark",
    primary="#58a6ff",
    secondary="#f0f6fc",
    accent="#58a6ff",
    foreground="#c9d1d9",
    background="#0d1117",
    success="#3fb950",
    warning="#f0d956",
    error="#da3633",
    surface="#161b22",
    panel="#161b22",
    boost="#1f2937",
    dark=True,
    variables={
        # Text colors
        "text-primary": "#c9d1d9",
        "text-secondary": "#7d8590",
        "text-muted": "#7d8590",
        "text-disabled": "#484f58",
        "text-bright": "#f0f6fc",
        # Border colors
        "border-color": "#30363d",
        "border-focus": "#58a6ff",
        "border-selected": "#0969da",
        # Button styles
        "button-foreground": "#c9d1d9",
        "button-color-foreground": "#ffffff",
        "button-focus-text-style": "bold",
        # Footer styles
        "footer-foreground": "#c9d1d9",
        "footer-background": "#161b22",
        "footer-key-foreground": "#58a6ff",
        "footer-key-background": "transparent",
        # Link styles
        "link-color": "#58a6ff",
        "link-color-hover": "#79c0ff",
        "link-background": "transparent",
        "link-background-hover": "#58a6ff 20%",
        # Scrollbar colors
        "scrollbar-background": "#161b22",
        "scrollbar-color": "#30363d",
        "scrollbar-color-active": "#58a6ff",
        # Input selection
        "input-selection-background": "#58a6ff 35%",
        "input-selection-foreground": "#ffffff",
        # Selection colors for lists and data tables
        "selection-background": "#58a6ff",
        "selection-foreground": "#ffffff",
        # Focus/Active states - override background color used as text
        "focus-text-color": "#ffffff",
        "active-text-color": "#ffffff",
        "highlight-text-color": "#ffffff",
        # Block cursor
        "block-cursor-foreground": "#0d1117",
        "block-cursor-text-style": "none",
    },
)
