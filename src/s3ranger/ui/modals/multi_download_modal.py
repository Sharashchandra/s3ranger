"""Multi-file download modal for S3Ranger."""

import os
import threading

from textual import work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static
from textual_fspicker import SelectDirectory

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets import ProgressWidget

FILE_PICKER_DEFAULT_PATH = "~/Downloads/"


class MultiDownloadModal(ModalScreen[bool]):
    """Modal screen for downloading multiple files from S3."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "download", "Download"),
        ("ctrl+o", "file_picker", "Open File Picker"),
    ]

    # Reactive properties
    s3_paths: list[str] = reactive([])
    selected_objects: list[dict] = reactive([])
    destination_path: str = reactive("~/Downloads/")
    is_downloading: bool = reactive(False)
    download_progress: str = reactive("")

    def __init__(self, s3_paths: list[str], selected_objects: list[dict]) -> None:
        """Initialize the multi-download modal.

        Args:
            s3_paths: List of S3 paths to download (e.g., ["s3://bucket/file1.txt", "s3://bucket/file2.txt"])
            selected_objects: List of selected object dictionaries with metadata
        """
        super().__init__()
        self.s3_paths = s3_paths
        self.selected_objects = selected_objects

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="download-dialog"):
            # Progress widget (hidden by default)
            yield ProgressWidget(text="Downloading...", id="progress-indicator")

            # Dialog header
            with Container(id="download-dialog-header"):
                yield Label("Download Multiple Files", classes="dialog-title")
                yield Label(f"{len(self.s3_paths)} items selected", classes="dialog-subtitle")

            # Dialog content
            with Container(id="download-dialog-content"):
                # Files list (scrollable)
                with Vertical(classes="field-group"):
                    yield Label("Files to Download", classes="field-label")
                    with VerticalScroll(id="files-list-container", classes="files-list", can_focus=True):
                        for i, obj in enumerate(self.selected_objects):
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
                        f"{len(self.s3_paths)} items will be downloaded",
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
                        yield Button("📁", id="file-picker-btn", classes="file-picker-button")
                    yield Label(
                        "Local folder where files will be saved (~ expands to home directory)",
                        classes="field-help",
                    )

            # Dialog footer
            with Container(id="download-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static("[bold white]Tab[/] Navigate", classes="keybinding")
                            yield Static(
                                "[bold white]Ctrl+Enter[/] Download",
                                classes="keybinding",
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static("[bold white]Esc[/] Cancel", classes="keybinding")
                            yield Static(
                                "[bold white]Ctrl+O[/] Open File Picker",
                                classes="keybinding",
                            )

                    with Vertical(classes="dialog-actions"):
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("Download All", id="download-btn", classes="primary")

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Set the destination input value
        destination_input = self.query_one("#destination-input", Input)
        destination_input.value = FILE_PICKER_DEFAULT_PATH

        # Focus the files list so user can scroll through selected files
        files_list = self.query_one("#files-list-container", VerticalScroll)
        files_list.focus()

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

    def watch_download_progress(self, progress: str) -> None:
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

        # Ensure destination directory exists
        if not os.path.exists(destination):
            try:
                os.makedirs(destination)
            except OSError as e:
                self.notify(f"Failed to create destination directory: {e}", severity="error")
                return

        # Start loading and perform download asynchronously
        self.is_downloading = True

        # Use threading to download asynchronously
        thread = threading.Thread(target=self._download_async, args=(destination,), daemon=True)
        thread.start()

    def _download_async(self, destination: str) -> None:
        """Asynchronously perform the download operation for multiple files."""
        total = len(self.s3_paths)
        successful = 0
        failed = 0

        for i, (s3_path, obj) in enumerate(zip(self.s3_paths, self.selected_objects)):
            try:
                # Update progress
                file_name = obj.get("key", "Unknown")
                progress_text = f"Downloading {i + 1}/{total}: {file_name}"
                self.app.call_later(lambda t=progress_text: self._update_progress(t))

                # Perform the download
                is_folder = obj.get("is_folder", False)
                if is_folder:
                    S3.download_directory(s3_uri=s3_path, local_dir_path=destination)
                else:
                    S3.download_file(s3_uri=s3_path, local_dir_path=destination)

                successful += 1

            except Exception as e:
                failed += 1
                print(f"Failed to download {s3_path}: {e}")

        # Build completion message
        if failed == 0:
            message = f"Successfully downloaded {successful} items to {destination}"
            self.app.call_later(lambda: self._on_download_success(message))
        elif successful == 0:
            error = Exception(f"All {failed} downloads failed")
            self.app.call_later(lambda: self._on_download_error(error))
        else:
            message = f"Downloaded {successful} items, {failed} failed"
            self.app.call_later(lambda: self._on_download_partial(message))

    def _update_progress(self, text: str) -> None:
        """Update progress text on the main thread."""
        self.download_progress = text

    def _on_download_success(self, message: str) -> None:
        """Handle successful download completion."""
        self.is_downloading = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_download_partial(self, message: str) -> None:
        """Handle partial download completion (some succeeded, some failed)."""
        self.is_downloading = False
        self.notify(message, severity="warning")
        self.dismiss(True)

    def _on_download_error(self, error: Exception) -> None:
        """Handle download error."""
        self.is_downloading = False
        self.notify(f"Download failed: {str(error)}", severity="error")

    @work
    async def action_file_picker(self) -> None:
        """Open file picker to select destination directory."""
        picker = SelectDirectory(location=FILE_PICKER_DEFAULT_PATH)

        if path := await self.app.push_screen_wait(picker):
            if path.is_dir():
                path = f"{path}/"
            path = str(path)

            destination_input = self.query_one("#destination-input", Input)
            destination_input.value = path
            destination_input.cursor_position = len(path)
            destination_input.focus()
