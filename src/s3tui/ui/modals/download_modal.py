"""Download modal for downloading S3 objects."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from s3tui.gateways.s3 import S3


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
        with Vertical(id="download-modal"):
            yield Static("Download", id="modal-title")

            with Vertical(id="form-container"):
                yield Label("Source:")
                yield Static(self.s3_path, id="source-path")

                yield Label("Destination:")
                yield Input(
                    value=self.current_working_dir, placeholder="Enter local directory path", id="destination-input"
                )

            with Horizontal(id="button-container"):
                yield Button("Download", variant="primary", id="download-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_dismiss()
        elif event.button.id == "download-btn":
            self._start_download()

    def _start_download(self) -> None:
        """Start the download process."""
        destination_input = self.query_one("#destination-input", Input)
        destination_path = destination_input.value.strip()

        if not destination_path:
            self.notify("Please enter a destination path", severity="error")
            return

        # Disable the download button and show loading state
        download_btn = self.query_one("#download-btn", Button)
        download_btn.disabled = True
        download_btn.label = "Downloading..."

        # Start download in background
        self._download_item(destination_path)

    @work(exclusive=True)
    async def _download_item(self, destination_path: str) -> None:
        """Download the file or folder in a background thread."""
        try:
            # Check if this is a folder (ends with '/') or file
            is_folder = self.s3_path.endswith("/")

            if is_folder:
                # Download the entire folder
                S3.download_directory(s3_uri=self.s3_path, local_dir_path=destination_path)

                # Extract folder name for success message
                folder_name = self.s3_path.rstrip("/").split("/")[-1]
                success_msg = f"Successfully downloaded folder '{folder_name}' to {destination_path}"
            else:
                # Download a single file
                S3.download_file(s3_uri=self.s3_path, local_dir_path=destination_path)

                # Extract file name for success message
                file_name = Path(self.s3_path).name
                destination_file_path = Path(destination_path) / file_name
                success_msg = f"Successfully downloaded '{file_name}' to {destination_file_path}"

            # Show success notification and close modal
            self.notify(success_msg, severity="information")
            self.dismiss(True)

        except Exception as e:
            # Re-enable download button and show error
            download_btn = self.query_one("#download-btn", Button)
            download_btn.disabled = False
            download_btn.label = "Download"

            error_msg = f"Download failed: {str(e)}"
            self.notify(error_msg, severity="error")
