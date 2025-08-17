"""Download modal for S3Ranger."""

import os
import threading

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual_fspicker import SelectDirectory

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets import ProgressWidget

FILE_PICKER_DEFAULT_PATH = "~/Downloads/"


class DownloadModal(ModalScreen[bool]):
    """Modal screen for downloading files from S3."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "download", "Download"),
        ("ctrl+o", "file_picker", "Open File Picker"),
    ]

    # Reactive properties
    s3_path: str = reactive("")
    destination_path: str = reactive("~/Downloads/")
    is_folder: bool = reactive(False)
    is_downloading: bool = reactive(False)

    def __init__(self, s3_path: str, is_folder: bool = False) -> None:
        """Initialize the download modal.

        Args:
            s3_path: The S3 path to download (e.g., s3://bucket/path/file.txt)
            is_folder: Whether the path represents a folder or file
        """
        super().__init__()
        self.s3_path = s3_path
        self.is_folder = is_folder

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="download-dialog"):
            # Progress widget (hidden by default)
            yield ProgressWidget(text="Downloading...", id="progress-indicator")

            # Dialog header
            with Container(id="download-dialog-header"):
                yield Label("Download Files", classes="dialog-title")
                yield Label("Specify download destination", classes="dialog-subtitle")

            # Dialog content
            with Container(id="download-dialog-content"):
                # Source field (read-only)
                with Vertical(classes="field-group"):
                    yield Label("Source (S3)", classes="field-label")
                    yield Static(
                        self.s3_path, id="source-field", classes="field-value readonly"
                    )
                    yield Label(
                        "Files will be downloaded from this S3 location",
                        classes="field-help",
                    )

                # Destination field (editable)
                with Vertical(classes="field-group"):
                    yield Label("Destination", classes="field-label")
                    with Horizontal(classes="input-with-button"):
                        yield Input(
                            value="~/Downloads/",
                            placeholder="Enter local destination path...",
                            id="destination-input",
                        )
                        yield Button(
                            "📁", id="file-picker-btn", classes="file-picker-button"
                        )
                    yield Label(
                        "Local path where files will be saved (~ expands to home directory)",
                        classes="field-help",
                    )

            # Dialog footer
            with Container(id="download-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Tab[/] Navigate", classes="keybinding"
                            )
                            yield Static(
                                "[bold white]Ctrl+Enter[/] Download",
                                classes="keybinding",
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Esc[/] Cancel", classes="keybinding"
                            )
                            yield Static(
                                "[bold white]Ctrl+O[/] Open File Picker",
                                classes="keybinding",
                            )

                    with Vertical(classes="dialog-actions"):
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("Download", id="download-btn", classes="primary")

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Debug: Check what s3_path we have
        print(f"DEBUG: Modal s3_path = '{self.s3_path}'")

        # Update the source field with the actual s3_path
        source_field = self.query_one("#source-field", Static)
        if self.s3_path:
            source_field.update(self.s3_path)
            print(f"DEBUG: Updated source field with: '{self.s3_path}'")
        else:
            source_field.update("No path provided")
            print("DEBUG: No s3_path provided")
        source_field.refresh()

        # Focus the destination input and set its value
        destination_input = self.query_one("#destination-input", Input)
        destination_input.value = FILE_PICKER_DEFAULT_PATH
        destination_input.focus()

    def watch_is_downloading(self, is_downloading: bool) -> None:
        """React to downloading state changes."""
        try:
            progress_widget = self.query_one("#progress-indicator", ProgressWidget)
            dialog_header = self.query_one("#download-dialog-header", Container)
            dialog_content = self.query_one("#download-dialog-content", Container)
            dialog_footer = self.query_one("#download-dialog-footer", Container)

            if is_downloading:
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
        elif event.button.id == "download-btn":
            self.action_download()
        elif event.button.id == "file-picker-btn":
            self.action_file_picker()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "destination-input":
            # Enable/disable download button based on input
            download_btn = self.query_one("#download-btn", Button)
            download_btn.disabled = not event.value.strip()

    def action_cancel(self) -> None:
        """Cancel the download operation."""
        self.dismiss(False)

    def action_download(self) -> None:
        """Start the download operation."""
        destination_input = self.query_one("#destination-input", Input)
        destination = destination_input.value.strip()

        if not destination:
            self.notify("Please enter a destination path", severity="error")
            return

        # Expand tilde to home directory
        destination = os.path.expanduser(destination)

        # Start loading and perform download asynchronously
        self.is_downloading = True

        # Use threading to download asynchronously
        thread = threading.Thread(
            target=self._download_async, args=(destination,), daemon=True
        )
        thread.start()

    def _download_async(self, destination: str) -> None:
        """Asynchronously perform the download operation."""
        try:
            # Perform the download
            if self.is_folder:
                S3.download_directory(s3_uri=self.s3_path, local_dir_path=destination)
                message = f"Directory downloaded to {destination}"
            else:
                S3.download_file(s3_uri=self.s3_path, local_dir_path=destination)
                message = f"File downloaded to {destination}"

            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_download_success(message))

        except Exception as e:
            # Handle download errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_download_error(error))

    def _on_download_success(self, message: str) -> None:
        """Handle successful download completion."""
        self.is_downloading = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_download_error(self, error: Exception) -> None:
        """Handle download error."""
        self.is_downloading = False
        self.notify(f"Download failed: {str(error)}", severity="error")

    @work
    async def action_file_picker(self) -> None:
        # Use SelectDirectory for both file and directory selection
        picker = SelectDirectory(location=FILE_PICKER_DEFAULT_PATH)

        if path := await self.app.push_screen_wait(picker):
            if path.is_dir():
                path = f"{path}/"  # Ensure path is a string
            path = str(path)

            destination_input = self.query_one("#destination-input", Input)
            destination_input.value = path
            destination_input.cursor_position = len(path)
            destination_input.focus()
