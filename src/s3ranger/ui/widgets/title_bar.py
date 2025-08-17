from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from s3ranger.ui.utils import get_current_aws_profile, get_current_endpoint_url


class TitleBar(Static):
    """Title bar widget matching the HTML design"""

    # Reactive property to track connection status
    connection_error: bool = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal(id="title-bar-container"):
            yield Static("S3 Ranger", id="title")
            with Horizontal(id="status-container"):
                yield Static("●", id="connected-indicator")

                # Build the AWS info string with profile and optional endpoint
                profile = get_current_aws_profile()
                endpoint_url = get_current_endpoint_url()

                aws_info = f"aws-profile: {profile}"
                if endpoint_url:
                    aws_info = f"aws-profile: {profile} ({endpoint_url})"

                yield Static(aws_info, id="aws-info")

    def watch_connection_error(self, connection_error: bool) -> None:
        """React to connection error state changes."""
        try:
            status_indicator = self.query_one("#connected-indicator", Static)
            if connection_error:
                status_indicator.add_class("error")
            else:
                status_indicator.remove_class("error")
        except Exception:
            # Indicator not ready yet, silently ignore
            pass
