"""Main S3TUI application."""

from textual.app import App
from textual.binding import Binding

from s3tui.gateways.s3 import S3
from s3tui.ui.screens.main_screen import MainScreen


class S3TUI(App):
    """S3 Terminal UI application."""

    TITLE = "S3 Browser"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("h", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
    def __init__(self, endpoint_url: str = None, region_name: str = None, **kwargs):
        """Initialize the S3TUI app.

        Args:
            endpoint_url: Custom S3 endpoint URL for S3-compatible services.
            region_name: AWS region name for S3 operations.
        """
        super().__init__(**kwargs)
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.current_theme_index = 0

        # Set the endpoint URL and region globally for the S3 class
        S3.set_endpoint_url(endpoint_url)
        S3.set_region_name(region_name)

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
