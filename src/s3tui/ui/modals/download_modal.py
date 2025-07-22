"""Download modal for downloading S3 objects."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from s3tui.gateways.s3 import S3


# UI Element IDs
class DownloadModalIDs:
    """Constants for UI element IDs."""

    DOWNLOAD_MODAL = "download-modal"
    MODAL_TITLE = "modal-title"
    FORM_CONTAINER = "form-container"
    SOURCE_PATH = "source-path"
    DESTINATION_INPUT = "destination-input"
    BUTTON_CONTAINER = "button-container"
    DOWNLOAD_BUTTON = "download-btn"
    CANCEL_BUTTON = "cancel-btn"


class DownloadModal(ModalScreen):
    """Modal screen for downloading S3 objects."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, s3_path: str) -> None:
        """Initialize the download modal.

        Args:
            s3_path: The S3 path of the object to download (e.g., s3://bucket/key)
        """
        super().__init__()
        self.s3_path = s3_path
        self.current_working_dir = str(Path.cwd())

    def compose(self) -> ComposeResult:
        """Create the layout for the download modal."""
        with Vertical(id=DownloadModalIDs.DOWNLOAD_MODAL):
            yield Static("Download", id=DownloadModalIDs.MODAL_TITLE)

            with Vertical(id=DownloadModalIDs.FORM_CONTAINER):
                yield Label("Source:")
                yield Static(self.s3_path, id=DownloadModalIDs.SOURCE_PATH)

                yield Label("Destination:")
                yield Input(
                    value=self.current_working_dir,
                    placeholder="Enter local directory path",
                    id=DownloadModalIDs.DESTINATION_INPUT,
                )

            with Horizontal(id=DownloadModalIDs.BUTTON_CONTAINER):
                yield Button("Download", variant="primary", id=DownloadModalIDs.DOWNLOAD_BUTTON)
                yield Button("Cancel", variant="default", id=DownloadModalIDs.CANCEL_BUTTON)

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == DownloadModalIDs.CANCEL_BUTTON:
            self.action_dismiss()
        elif event.button.id == DownloadModalIDs.DOWNLOAD_BUTTON:
            self._validate_and_download()

    def _validate_and_download(self) -> None:
        """Validate input and start download if valid."""
        destination_input = self.query_one(f"#{DownloadModalIDs.DESTINATION_INPUT}", Input)
        destination_path = destination_input.value.strip()

        if not destination_path:
            self.notify("Please enter a destination path", severity="error")
            return

        # Start download immediately without loading state
        self._download_item(destination_path)

    @work(exclusive=True)
    async def _download_item(self, destination_path: str) -> None:
        """Download the file or folder in a background thread."""
        try:
            item_name = Path(self.s3_path).name

            if self.s3_path.endswith("/"):
                S3.download_directory(s3_uri=self.s3_path, local_dir_path=destination_path)
                success_msg = f"Successfully downloaded folder '{item_name}' to {destination_path}"
            else:
                S3.download_file(s3_uri=self.s3_path, local_dir_path=destination_path)
                destination_file_path = Path(destination_path) / Path(self.s3_path).name
                success_msg = f"Successfully downloaded '{item_name}' to {destination_file_path}"

            self._show_success_and_close(success_msg)

        except Exception as e:
            self._show_error(f"Download failed: {str(e)}")

    def _show_success_and_close(self, message: str) -> None:
        """Show success notification and close modal."""
        self.notify(message, severity="information")
        self.dismiss(True)  # Return True to indicate successful download

    def _show_error(self, message: str) -> None:
        """Show error notification."""
        self.notify(message, severity="error")
