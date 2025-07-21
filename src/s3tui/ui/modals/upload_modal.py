"""Upload modal for uploading files/folders to S3."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from s3tui.gateways.s3 import S3


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
        with Vertical(id="upload-modal"):
            yield Static("Upload", id="modal-title")

            with Vertical(id="form-container"):
                yield Label("Source:")
                yield Input(
                    value=self.current_working_dir, placeholder="Enter local file or directory path", id="source-input"
                )

                yield Label("Destination:")
                yield Static(self.s3_destination, id="destination-path")

            with Horizontal(id="button-container"):
                yield Button("Upload", variant="primary", id="upload-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_dismiss()
        elif event.button.id == "upload-btn":
            self._start_upload()

    def _start_upload(self) -> None:
        """Start the upload process."""
        source_input = self.query_one("#source-input", Input)
        source_path = source_input.value.strip()

        if not source_path:
            self.notify("Please enter a source path", severity="error")
            return

        # Validate source path exists
        source_path_obj = Path(source_path)
        if not source_path_obj.exists():
            self.notify("Source path does not exist", severity="error")
            return

        # Start upload in background
        self._upload_item(source_path)

    @work(exclusive=True)
    async def _upload_item(self, source_path: str) -> None:
        """Upload the file or folder in a background thread."""
        try:
            source_path_obj = Path(source_path)

            if source_path_obj.is_dir():
                # Upload directory
                S3.upload_directory(local_dir_path=source_path, s3_uri=self.s3_destination)

                # Extract folder name for success message
                folder_name = source_path_obj.name
                success_msg = f"Successfully uploaded folder '{folder_name}' to {self.s3_destination}"
            else:
                # Upload single file
                S3.upload_file(local_file_path=source_path, s3_uri=self.s3_destination)

                # Extract file name for success message
                file_name = source_path_obj.name
                success_msg = f"Successfully uploaded '{file_name}' to {self.s3_destination}"

            # Show success notification and close modal
            self.notify(success_msg, severity="information")
            self.dismiss(True)  # Return True to indicate successful upload

        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            self.notify(error_msg, severity="error")
