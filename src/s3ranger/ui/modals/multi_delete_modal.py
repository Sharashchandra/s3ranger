"""Multi-file delete modal for S3Ranger."""

import threading

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets import ProgressWidget


class MultiDeleteModal(ModalScreen[bool]):
    """Modal screen for deleting multiple files from S3."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "delete", "Delete"),
    ]

    # Reactive properties
    s3_paths: list[str] = reactive([])
    selected_objects: list[dict] = reactive([])
    is_deleting: bool = reactive(False)
    delete_progress: str = reactive("")

    def __init__(self, s3_paths: list[str], selected_objects: list[dict]) -> None:
        """Initialize the multi-delete modal.

        Args:
            s3_paths: List of S3 paths to delete (e.g., ["s3://bucket/file1.txt", "s3://bucket/file2.txt"])
            selected_objects: List of selected object dictionaries with metadata
        """
        super().__init__()
        self.s3_paths = s3_paths
        self.selected_objects = selected_objects

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="delete-dialog"):
            # Progress widget (hidden by default)
            yield ProgressWidget(text="Deleting...", id="progress-indicator")

            # Dialog header
            with Container(id="delete-dialog-header"):
                yield Label("Delete Multiple Items", classes="dialog-title")
                yield Label(
                    f"{len(self.s3_paths)} items selected • This action cannot be undone",
                    classes="dialog-subtitle",
                )

            # Dialog content
            with Container(id="delete-dialog-content"):
                # Files list (scrollable)
                with Vertical(classes="field-group"):
                    yield Label("Items to Delete", classes="field-label")
                    with VerticalScroll(id="files-list-container", classes="files-list", can_focus=True):
                        for obj in self.selected_objects:
                            file_name = obj.get("key", "Unknown")
                            file_size = obj.get("size", "")
                            is_folder = obj.get("is_folder", False)
                            icon = "📁" if is_folder else "📄"
                            size_text = f" ({file_size})" if file_size else ""
                            yield Static(
                                f"{icon} {file_name}{size_text}",
                                classes="file-list-item",
                            )
                    yield Label(
                        f"{len(self.s3_paths)} items will be permanently deleted from S3",
                        classes="field-help",
                    )

            # Dialog footer
            with Container(id="delete-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static("[bold white]Tab[/] Navigate", classes="keybinding")
                            yield Static(
                                "[bold white]Ctrl+Enter[/] Delete",
                                classes="keybinding",
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static("[bold white]Esc[/] Cancel", classes="keybinding")

                    with Vertical(classes="dialog-actions"):
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("Delete All", id="delete-btn", classes="delete-button")

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Focus the files list so user can scroll through selected files
        files_list = self.query_one("#files-list-container", VerticalScroll)
        files_list.focus()

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

    def watch_delete_progress(self, progress: str) -> None:
        """Update progress widget text."""
        try:
            if progress:
                progress_widget = self.query_one("#progress-indicator", ProgressWidget)
                progress_widget.text = progress
        except Exception:
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
        if not self.s3_paths:
            self.notify("No items to delete", severity="error")
            return

        # Start loading and perform delete asynchronously
        self.is_deleting = True

        # Use threading to delete asynchronously
        thread = threading.Thread(target=self._delete_async, daemon=True)
        thread.start()

    def _delete_async(self) -> None:
        """Asynchronously perform the delete operation for multiple files."""
        total = len(self.s3_paths)
        successful = 0
        failed = 0

        for i, (s3_path, obj) in enumerate(zip(self.s3_paths, self.selected_objects)):
            try:
                # Update progress
                file_name = obj.get("key", "Unknown")
                progress_text = f"Deleting {i + 1}/{total}: {file_name}"
                self.app.call_later(lambda t=progress_text: self._update_progress(t))

                # Perform the delete
                is_folder = obj.get("is_folder", False)
                if is_folder:
                    S3.delete_directory(s3_uri=s3_path)
                else:
                    S3.delete_file(s3_uri=s3_path)

                successful += 1

            except Exception as e:
                failed += 1
                print(f"Failed to delete {s3_path}: {e}")

        # Build completion message
        if failed == 0:
            message = f"Successfully deleted {successful} items"
            self.app.call_later(lambda: self._on_delete_success(message))
        elif successful == 0:
            error = Exception(f"All {failed} deletions failed")
            self.app.call_later(lambda: self._on_delete_error(error))
        else:
            message = f"Deleted {successful} items, {failed} failed"
            self.app.call_later(lambda: self._on_delete_partial(message))

    def _update_progress(self, text: str) -> None:
        """Update progress text on the main thread."""
        self.delete_progress = text

    def _on_delete_success(self, message: str) -> None:
        """Handle successful delete completion."""
        self.is_deleting = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_delete_partial(self, message: str) -> None:
        """Handle partial delete completion (some succeeded, some failed)."""
        self.is_deleting = False
        self.notify(message, severity="warning")
        self.dismiss(True)

    def _on_delete_error(self, error: Exception) -> None:
        """Handle delete error."""
        self.is_deleting = False
        self.notify(f"Delete failed: {str(error)}", severity="error")
