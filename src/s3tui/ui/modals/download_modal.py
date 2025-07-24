"""Download modal for S3TUI."""

import os
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual_fspicker import SelectDirectory

from s3tui.gateways.s3 import S3

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
            # Dialog header
            with Container(id="download-dialog-header"):
                yield Label("Download Files", classes="dialog-title")
                yield Label("Specify download destination", classes="dialog-subtitle")

            # Dialog content
            with Container(id="download-dialog-content"):
                # Source field (read-only)
                with Vertical(classes="field-group"):
                    yield Label("Source (S3)", classes="field-label")
                    yield Static(self.s3_path, id="source-field", classes="field-value readonly")
                    yield Label("Files will be downloaded from this S3 location", classes="field-help")

                # Destination field (editable)
                with Vertical(classes="field-group"):
                    yield Label("Destination", classes="field-label")
                    with Horizontal(classes="input-with-button"):
                        yield Input(
                            value="~/Downloads/", placeholder="Enter local destination path...", id="destination-input"
                        )
                        yield Button("📁", id="file-picker-btn", classes="file-picker-button")
                    yield Label(
                        "Local path where files will be saved (~ expands to home directory)", classes="field-help"
                    )

            # Dialog footer
            with Container(id="download-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static("[bold white]Tab[/] Navigate", classes="keybinding")
                            yield Static("[bold white]Ctrl+Enter[/] Download", classes="keybinding")
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static("[bold white]Esc[/] Cancel", classes="keybinding")
                            yield Static("[bold white]Ctrl+O[/] Open File Picker", classes="keybinding")

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

        try:
            # Create destination directory if it doesn't exist
            Path(destination).mkdir(parents=True, exist_ok=True)

            # Perform the download
            if self.is_folder:
                S3.download_directory(s3_uri=self.s3_path, local_dir_path=destination)
                self.notify(f"Directory downloaded to {destination}", severity="success")
            else:
                S3.download_file(s3_uri=self.s3_path, local_dir_path=destination)
                self.notify(f"File downloaded to {destination}", severity="success")

            self.dismiss(True)

        except Exception as e:
            self.notify(f"Download failed: {str(e)}", severity="error")

    @work
    async def action_file_picker(self) -> None:
        if path := await self.app.push_screen_wait(SelectDirectory(location=FILE_PICKER_DEFAULT_PATH)):
            destination_input = self.query_one("#destination-input", Input)
            destination_input.value = str(path)
            destination_input.focus()
