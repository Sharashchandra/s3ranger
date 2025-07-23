"""Delete modal for deleting S3 objects."""

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from s3tui.gateways.s3 import S3


# UI Element IDs
class DeleteModalIDs:
    """Constants for UI element IDs."""

    DELETE_MODAL = "delete-modal"
    MODAL_TITLE = "modal-title"
    FORM_CONTAINER = "form-container"
    SOURCE_PATH = "source-path"
    BUTTON_CONTAINER = "button-container"
    DELETE_BUTTON = "delete-btn"
    CANCEL_BUTTON = "cancel-btn"


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
        with Vertical(id=DeleteModalIDs.DELETE_MODAL):
            yield Static("Confirm Deletion", id=DeleteModalIDs.MODAL_TITLE)

            with Vertical(id=DeleteModalIDs.FORM_CONTAINER):
                yield Label("Are you sure you want to permanently delete?")
                yield Static(self.s3_path, id=DeleteModalIDs.SOURCE_PATH)

            with Horizontal(id=DeleteModalIDs.BUTTON_CONTAINER):
                yield Button("Delete", variant="error", id=DeleteModalIDs.DELETE_BUTTON)
                yield Button("Cancel", variant="default", id=DeleteModalIDs.CANCEL_BUTTON)

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == DeleteModalIDs.CANCEL_BUTTON:
            self.action_dismiss()
        elif event.button.id == DeleteModalIDs.DELETE_BUTTON:
            self._delete_item()

    @work(exclusive=True)
    async def _delete_item(self) -> None:
        """Delete the file or folder in a background thread."""
        try:
            # item_name = extract_item_name_from_s3_path(self.s3_path)
            item_name = Path(self.s3_path).name

            if self.s3_path.endswith("/"):
                S3.delete_directory(s3_uri=self.s3_path)
                success_msg = f"Successfully deleted folder '{item_name}'"
            else:
                S3.delete_file(s3_uri=self.s3_path)
                success_msg = f"Successfully deleted '{item_name}'"

            self._show_success_and_close(success_msg)

        except Exception as e:
            self._show_error(f"Delete failed: {str(e)}")

    def _show_success_and_close(self, message: str) -> None:
        """Show success notification and close modal."""
        self.notify(message, severity="information")
        self.dismiss(True)  # Return True to indicate successful deletion

    def _show_error(self, message: str) -> None:
        """Show error notification."""
        self.notify(message, severity="error")
