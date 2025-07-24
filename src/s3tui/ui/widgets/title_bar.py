from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from s3tui.ui.utils import get_current_aws_profile


class TitleBar(Static):
    """Title bar widget matching the HTML design"""

    def compose(self) -> ComposeResult:
        with Horizontal(id="title-bar-container"):
            yield Static("S3 Browser", id="title")
            with Horizontal(id="status-container"):
                yield Static("●", id="connected-indicator")
                yield Static(f"aws-profile: {get_current_aws_profile()}", id="aws-info")
