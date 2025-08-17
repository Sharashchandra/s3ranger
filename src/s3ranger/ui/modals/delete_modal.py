"""Delete modal for S3Ranger."""

import threading

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets import ProgressWidget


class DeleteModal(ModalScreen[bool]):
    """Modal screen for deleting files or folders from S3."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "delete", "Delete"),
    ]

    # Reactive properties
    s3_path: str = reactive("")
    is_folder: bool = reactive(False)
    is_deleting: bool = reactive(False)

    def __init__(self, s3_path: str, is_folder: bool = False) -> None:
        """Initialize the delete modal.

        Args:
            s3_path: The S3 path to delete (e.g., s3://bucket/path/file.txt)
            is_folder: Whether the path represents a folder or file
        """
        super().__init__()
        self.s3_path = s3_path
        self.is_folder = is_folder

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="delete-dialog"):
            # Progress widget (hidden by default)
            yield ProgressWidget(text="Deleting...", id="progress-indicator")

            # Dialog header
            with Container(id="delete-dialog-header"):
                item_type = "Folder" if self.is_folder else "File"
                yield Label(f"Delete {item_type}", classes="dialog-title")
                yield Label("This action cannot be undone", classes="dialog-subtitle")

            # Dialog content
            with Container(id="delete-dialog-content"):
                # Source field (read-only)
                with Vertical(classes="field-group"):
                    yield Label("Source (S3)", classes="field-label")
                    yield Static(
                        self.s3_path, id="source-field", classes="field-value readonly"
                    )
                    item_type = (
                        "folder and all its contents" if self.is_folder else "file"
                    )
                    yield Label(
                        f"This {item_type} will be permanently deleted from S3",
                        classes="field-help",
                    )

            # Dialog footer
            with Container(id="delete-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Tab[/] Navigate", classes="keybinding"
                            )
                            yield Static(
                                "[bold white]Ctrl+Enter[/] Delete", classes="keybinding"
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Esc[/] Cancel", classes="keybinding"
                            )

                    with Vertical(classes="dialog-actions"):
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("Delete", id="delete-btn", classes="delete-button")

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Debug: Check what s3_path we have
        print(f"DEBUG: Delete modal s3_path = '{self.s3_path}'")

        # Update the source field with the actual s3_path
        source_field = self.query_one("#source-field", Static)
        if self.s3_path:
            source_field.update(self.s3_path)
            print(f"DEBUG: Updated source field with: '{self.s3_path}'")
        else:
            source_field.update("No path provided")
            print("DEBUG: No s3_path provided")
        source_field.refresh()

    def watch_is_deleting(self, is_deleting: bool) -> None:
        """React to deleting state changes."""
        try:
            progress_widget = self.query_one("#progress-indicator", ProgressWidget)
            dialog_header = self.query_one("#delete-dialog-header", Container)
            dialog_content = self.query_one("#delete-dialog-content", Container)
            dialog_footer = self.query_one("#delete-dialog-footer", Container)

            if is_deleting:
                # Show progress widget and hide other content
                progress_widget.display = True
                dialog_header.display = False
                dialog_content.display = False
                dialog_footer.display = False
            else:
                # Hide progress widget and show other content
                progress_widget.display = False
                dialog_header.display = True
                dialog_content.display = True
                dialog_footer.display = True
        except Exception:
            # Widgets not ready yet, silently ignore
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "delete-btn":
            self.action_delete()

    def action_cancel(self) -> None:
        """Cancel the delete operation."""
        self.dismiss(False)

    def action_delete(self) -> None:
        """Start the delete operation."""
        if not self.s3_path:
            self.notify("No S3 path specified", severity="error")
            return

        # Start loading and perform delete asynchronously
        self.is_deleting = True

        # Use threading to delete asynchronously
        thread = threading.Thread(target=self._delete_async, daemon=True)
        thread.start()

    def _delete_async(self) -> None:
        """Asynchronously perform the delete operation."""
        try:
            # Perform the delete
            if self.is_folder:
                S3.delete_directory(s3_uri=self.s3_path)
                item_type = "Directory"
            else:
                S3.delete_file(s3_uri=self.s3_path)
                item_type = "File"

            message = f"{item_type} deleted successfully"

            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_delete_success(message))

        except Exception as e:
            # Handle delete errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_delete_error(error))

    def _on_delete_success(self, message: str) -> None:
        """Handle successful delete completion."""
        self.is_deleting = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_delete_error(self, error: Exception) -> None:
        """Handle delete error."""
        self.is_deleting = False
        self.notify(f"Delete failed: {str(error)}", severity="error")
