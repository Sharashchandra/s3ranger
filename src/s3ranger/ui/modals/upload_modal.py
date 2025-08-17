"""Upload modal for S3Ranger."""

import os
import threading
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual_fspicker import FileOpen, SelectDirectory

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets import ProgressWidget

FILE_PICKER_DEFAULT_PATH = "~/"


class UploadModal(ModalScreen[bool]):
    """Modal screen for uploading files to S3."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "upload", "Upload"),
        ("ctrl+o", "file_picker", "Open File Picker"),
        ("ctrl+l", "folder_picker", "Open Folder Picker"),
    ]

    # Reactive properties
    s3_path: str = reactive("")
    source_path: str = reactive("~/")
    is_folder: bool = reactive(False)
    is_uploading: bool = reactive(False)

    def __init__(self, s3_path: str, is_folder: bool = False) -> None:
        """Initialize the upload modal.

        Args:
            s3_path: The S3 path to upload to (e.g., s3://bucket/path/)
            is_folder: Whether uploading a folder or file
        """
        super().__init__()
        self.s3_path = s3_path
        self.is_folder = is_folder

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="upload-dialog"):
            # Progress widget (hidden by default)
            yield ProgressWidget(text="Uploading...", id="progress-indicator")

            # Dialog header
            with Container(id="upload-dialog-header"):
                yield Label("Upload Files", classes="dialog-title")
                yield Label("Specify upload source", classes="dialog-subtitle")

            # Dialog content
            with Container(id="upload-dialog-content"):
                # Source field (editable with file picker)
                with Vertical(classes="field-group"):
                    yield Label("Source", classes="field-label")
                    with Horizontal(classes="input-with-button"):
                        yield Input(
                            value="~/",
                            placeholder="Enter local source path...",
                            id="source-input",
                        )
                        yield Button(
                            "📁", id="file-picker-btn", classes="file-picker-button"
                        )
                    yield Label(
                        "Local path to upload from (~ expands to home directory)",
                        classes="field-help",
                    )

                # Destination field (read-only S3 path)
                with Vertical(classes="field-group"):
                    yield Label("Destination (S3)", classes="field-label")
                    yield Static(
                        self.s3_path,
                        id="destination-field",
                        classes="field-value readonly",
                    )
                    yield Label(
                        "Files will be uploaded to this S3 location",
                        classes="field-help",
                    )

            # Dialog footer
            with Container(id="upload-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Tab[/] Navigate", classes="keybinding"
                            )
                            yield Static(
                                "[bold white]Ctrl+Enter[/] Upload", classes="keybinding"
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Esc[/] Cancel", classes="keybinding"
                            )
                            yield Static(
                                "[bold white]Ctrl+O[/] File Picker",
                                classes="keybinding",
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Ctrl+L[/] Folder Picker",
                                classes="keybinding",
                            )

                    with Vertical(classes="dialog-actions"):
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("Upload", id="upload-btn", classes="primary")

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Debug: Check what s3_path we have
        print(f"DEBUG: Modal s3_path = '{self.s3_path}'")

        # Update the destination field with the actual s3_path
        destination_field = self.query_one("#destination-field", Static)
        if self.s3_path:
            destination_field.update(self.s3_path)
            print(f"DEBUG: Updated destination field with: '{self.s3_path}'")
        else:
            destination_field.update("No path provided")
            print("DEBUG: No s3_path provided")
        destination_field.refresh()

        # Focus the source input and set its value
        source_input = self.query_one("#source-input", Input)
        source_input.value = FILE_PICKER_DEFAULT_PATH
        source_input.focus()

    def watch_is_uploading(self, is_uploading: bool) -> None:
        """React to uploading state changes."""
        try:
            progress_widget = self.query_one("#progress-indicator", ProgressWidget)
            dialog_header = self.query_one("#upload-dialog-header", Container)
            dialog_content = self.query_one("#upload-dialog-content", Container)
            dialog_footer = self.query_one("#upload-dialog-footer", Container)

            if is_uploading:
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
        elif event.button.id == "upload-btn":
            self.action_upload()
        elif event.button.id == "file-picker-btn":
            self.action_file_picker()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "source-input":
            # Enable/disable upload button based on input
            upload_btn = self.query_one("#upload-btn", Button)
            upload_btn.disabled = not event.value.strip()

    def action_cancel(self) -> None:
        """Cancel the upload operation."""
        self.dismiss(False)

    def action_upload(self) -> None:
        """Start the upload operation."""
        source_input = self.query_one("#source-input", Input)
        source = source_input.value.strip()

        if not source:
            self.notify("Please enter a source path", severity="error")
            return

        # Expand tilde to home directory
        source = os.path.expanduser(source)

        # Check if source exists
        source_path = Path(source)
        if not source_path.exists():
            self.notify(f"Source path does not exist: {source}", severity="error")
            return

        # Start loading and perform upload asynchronously
        self.is_uploading = True

        # Use threading to upload asynchronously
        thread = threading.Thread(
            target=self._upload_async, args=(source,), daemon=True
        )
        thread.start()

    def _upload_async(self, source: str) -> None:
        """Asynchronously perform the upload operation."""
        try:
            source_path = Path(source)

            # Perform the upload
            if source_path.is_dir():
                S3.upload_directory(local_dir_path=source, s3_uri=self.s3_path)
                message = f"Directory uploaded from {source}"
            else:
                S3.upload_file(local_file_path=source, s3_uri=self.s3_path)
                message = f"File uploaded from {source}"

            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_upload_success(message))

        except Exception as e:
            # Handle upload errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_upload_error(error))

    def _on_upload_success(self, message: str) -> None:
        """Handle successful upload completion."""
        self.is_uploading = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_upload_error(self, error: Exception) -> None:
        """Handle upload error."""
        self.is_uploading = False
        self.notify(f"Upload failed: {str(error)}", severity="error")

    @work
    async def action_file_picker(self) -> None:
        """Open file picker to select individual files."""
        picker = FileOpen(location=FILE_PICKER_DEFAULT_PATH)

        if path := await self.app.push_screen_wait(picker):
            # Convert path to string
            path_str = str(path)

            source_input = self.query_one("#source-input", Input)
            source_input.value = path_str
            source_input.cursor_position = len(path_str)
            source_input.focus()

    @work
    async def action_folder_picker(self) -> None:
        """Open folder picker to select directories."""
        picker = SelectDirectory(location=FILE_PICKER_DEFAULT_PATH)

        if path := await self.app.push_screen_wait(picker):
            # Convert path to string
            path_str = f"{path}/"

            source_input = self.query_one("#source-input", Input)
            source_input.value = path_str
            source_input.cursor_position = len(path_str)
            source_input.focus()
