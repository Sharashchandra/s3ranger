from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen

from s3tui.ui.widgets.title_bar import TitleBar


class MainScreen(Screen):
    """Main screen displaying S3 buckets and objects."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Create the layout for the main screen."""
        with Container(id="main-container"):
            yield TitleBar(id="title-bar")
