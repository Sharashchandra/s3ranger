"""Delete modal for deleting S3 objects."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from s3tui.gateways.s3 import S3


class DeleteModal(ModalScreen):
    """Modal screen for deleting S3 objects."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, s3_path: str) -> None:
        """Initialize the delete modal.

        Args:
            s3_path: The S3 path of the object to delete (e.g., s3://bucket/key)
        """
        super().__init__()
        self.s3_path = s3_path

    def compose(self) -> ComposeResult:
        """Create the layout for the delete modal."""
        with Vertical(id="delete-modal"):
            yield Static("Confirm Deletion", id="modal-title")

            with Vertical(id="form-container"):
                yield Label("Are you sure you want to permanently delete?")
                yield Static(self.s3_path, id="source-path")

            with Horizontal(id="button-container"):
                yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_dismiss()
        elif event.button.id == "delete-btn":
            self._start_delete()

    def _start_delete(self) -> None:
        """Start the delete process."""
        # Disable the delete button and show loading state
        delete_btn = self.query_one("#delete-btn", Button)
        delete_btn.disabled = True
        delete_btn.label = "Deleting..."

        # Start delete in background
        self._delete_item()

    @work(exclusive=True)
    async def _delete_item(self) -> None:
        """Delete the file or folder in a background thread."""
        try:
            # Check if this is a folder (ends with '/') or file
            is_folder = self.s3_path.endswith("/")

            if is_folder:
                # Delete the entire folder
                S3.delete_directory(s3_uri=self.s3_path)

                # Extract folder name for success message
                folder_name = self.s3_path.rstrip("/").split("/")[-1]
                success_msg = f"Successfully deleted folder '{folder_name}'"
            else:
                # Delete a single file
                S3.delete_file(s3_uri=self.s3_path)

                # Extract file name for success message
                file_name = Path(self.s3_path).name
                success_msg = f"Successfully deleted '{file_name}'"

            # Show success notification and close modal
            self.notify(success_msg, severity="information")
            self.dismiss(True)  # Return True to indicate successful deletion

        except Exception as e:
            # Re-enable delete button and show error
            delete_btn = self.query_one("#delete-btn", Button)
            delete_btn.disabled = False
            delete_btn.label = "Delete"

            error_msg = f"Delete failed: {str(e)}"
            self.notify(error_msg, severity="error")
