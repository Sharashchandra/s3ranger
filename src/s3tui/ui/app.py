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
    ]

    def __init__(
        self,
        endpoint_url: str = None,
        region_name: str = None,
        profile_name: str = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        **kwargs,
    ):
        """Initialize the S3TUI app.

        Args:
            endpoint_url: Custom S3 endpoint URL for S3-compatible services.
            region_name: AWS region name for S3 operations.
            profile_name: AWS profile name for authentication.
            aws_access_key_id: AWS access key ID for authentication.
            aws_secret_access_key: AWS secret access key for authentication.
            aws_session_token: AWS session token for temporary credentials.
        """
        super().__init__(**kwargs)
        self.endpoint_url = endpoint_url
        self.region_name = region_name
        self.profile_name = profile_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token
        self.current_theme_index = 0

        # Set the endpoint URL, region, profile, and credentials globally for the S3 class
        S3.set_endpoint_url(endpoint_url)
        S3.set_region_name(region_name)
        S3.set_profile_name(profile_name)
        S3.set_credentials(aws_access_key_id, aws_secret_access_key, aws_session_token)

    def on_mount(self) -> None:
        """Called when app starts."""
        self.push_screen(MainScreen())
