"""Upload modal for uploading files/folders to S3."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from s3tui.gateways.s3 import S3


# UI Element IDs
class UploadModalIDs:
    """Constants for UI element IDs."""

    UPLOAD_MODAL = "upload-modal"
    MODAL_TITLE = "modal-title"
    FORM_CONTAINER = "form-container"
    SOURCE_INPUT = "source-input"
    DESTINATION_PATH = "destination-path"
    BUTTON_CONTAINER = "button-container"
    UPLOAD_BUTTON = "upload-btn"
    CANCEL_BUTTON = "cancel-btn"


class UploadModal(ModalScreen):
    """Modal screen for uploading files/folders to S3."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, s3_destination: str) -> None:
        """Initialize the upload modal.

        Args:
            s3_destination: The S3 destination path (e.g., s3://bucket/ or s3://bucket/folder/)
        """
        super().__init__()
        self.s3_destination = s3_destination
        self.current_working_dir = str(Path.cwd())

    def compose(self) -> ComposeResult:
        """Create the layout for the upload modal."""
        with Vertical(id=UploadModalIDs.UPLOAD_MODAL):
            yield Static("Upload", id=UploadModalIDs.MODAL_TITLE)

            with Vertical(id=UploadModalIDs.FORM_CONTAINER):
                yield Label("Source:")
                yield Input(
                    value=self.current_working_dir,
                    placeholder="Enter local file or directory path",
                    id=UploadModalIDs.SOURCE_INPUT,
                )

                yield Label("Destination:")
                yield Static(self.s3_destination, id=UploadModalIDs.DESTINATION_PATH)

            with Horizontal(id=UploadModalIDs.BUTTON_CONTAINER):
                yield Button("Upload", variant="primary", id=UploadModalIDs.UPLOAD_BUTTON)
                yield Button("Cancel", variant="default", id=UploadModalIDs.CANCEL_BUTTON)

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == UploadModalIDs.CANCEL_BUTTON:
            self.action_dismiss()
        elif event.button.id == UploadModalIDs.UPLOAD_BUTTON:
            self._validate_and_upload()

    def _validate_and_upload(self) -> None:
        """Validate input and start upload if valid."""
        source_input = self.query_one(f"#{UploadModalIDs.SOURCE_INPUT}", Input)
        source_path = source_input.value.strip()

        if not source_path:
            self.notify("Please enter a source path", severity="error")
            return

        # Validate source path exists
        source_path_obj = Path(source_path)
        if not source_path_obj.exists():
            self.notify("Source path does not exist", severity="error")
            return

        # Start upload immediately
        self._upload_item(source_path)

    @work(exclusive=True)
    async def _upload_item(self, source_path: str) -> None:
        """Upload the file or folder in a background thread."""
        try:
            source_path_obj = Path(source_path)
            item_name = source_path_obj.name

            if source_path_obj.is_dir():
                S3.upload_directory(local_dir_path=source_path, s3_uri=self.s3_destination)
                success_msg = f"Successfully uploaded folder '{item_name}' to {self.s3_destination}"
            else:
                S3.upload_file(local_file_path=source_path, s3_uri=self.s3_destination)
                success_msg = f"Successfully uploaded '{item_name}' to {self.s3_destination}"

            self._show_success_and_close(success_msg)

        except Exception as e:
            self._show_error(f"Upload failed: {str(e)}")

    def _show_success_and_close(self, message: str) -> None:
        """Show success notification and close modal."""
        self.notify(message, severity="information")
        self.dismiss(True)  # Return True to indicate successful upload

    def _show_error(self, message: str) -> None:
        """Show error notification."""
        self.notify(message, severity="error")
