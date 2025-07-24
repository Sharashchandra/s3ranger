"""Main S3TUI application."""

from textual.app import App
from textual.binding import Binding

from s3tui.ui.screens.main_screen import MainScreen


class S3TUI(App):
    """S3 Terminal UI application."""

    TITLE = "S3 Browser"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("h", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
    ]

    def on_mount(self) -> None:
        """Called when app starts."""
        self.push_screen(MainScreen())

    def action_help(self) -> None:
        """Show help information."""
        # Help modal would be implemented here
        pass

    def action_refresh(self) -> None:
        """Refresh current view."""
        # Delegate refresh to the current screen
        if hasattr(self.screen, "action_refresh"):
            self.screen.action_refresh()
