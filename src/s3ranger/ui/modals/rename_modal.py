"""Rename modal for S3Ranger."""

import os
import threading

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets import ProgressWidget


class RenameModal(ModalScreen[bool]):
    """Modal screen for renaming files or folders in S3."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "rename", "Rename"),
    ]

    # Reactive properties
    s3_path: str = reactive("")
    is_folder: bool = reactive(False)
    is_renaming: bool = reactive(False)
    current_objects: list = reactive([])  # To check for name conflicts

    def __init__(
        self, s3_path: str, is_folder: bool = False, current_objects: list = None
    ) -> None:
        """Initialize the rename modal.

        Args:
            s3_path: The S3 path to rename (e.g., s3://bucket/path/file.txt)
            is_folder: Whether the path represents a folder or file
            current_objects: List of current objects in the same directory to check for conflicts
        """
        super().__init__()
        self.s3_path = s3_path
        self.is_folder = is_folder
        self.current_objects = current_objects or []

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="rename-dialog"):
            # Progress widget (hidden by default)
            yield ProgressWidget(text="Renaming...", id="progress-indicator")

            # Dialog header
            with Container(id="rename-dialog-header"):
                item_type = "Folder" if self.is_folder else "File"
                yield Label(f"Rename {item_type}", classes="dialog-title")
                yield Label("Enter a new name for the item", classes="dialog-subtitle")

                # Warning for folders
                if self.is_folder:
                    yield Label(
                        "⚠️  Warning: Renaming a folder will move all files to the new location and delete the old files",
                        classes="warning-text",
                    )

            # Dialog content
            with Container(id="rename-dialog-content"):
                # Current name field (read-only)
                with Vertical(classes="field-group"):
                    yield Label("Current Name", classes="field-label")
                    yield Static(
                        "", id="current-name-field", classes="field-value readonly"
                    )

                # New name field (editable)
                with Vertical(classes="field-group"):
                    yield Label("New Name", classes="field-label")
                    yield Input(
                        placeholder="Enter new name...",
                        id="new-name-input",
                        classes="rename-input",
                    )
                    yield Label("", id="name-validation", classes="field-help")

            # Dialog footer
            with Container(id="rename-dialog-footer"):
                with Horizontal(classes="footer-content"):
                    with Vertical(classes="keybindings-section"):
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Tab[/] Navigate", classes="keybinding"
                            )
                            yield Static(
                                "[bold white]Ctrl+Enter[/] Rename", classes="keybinding"
                            )
                        with Horizontal(classes="dialog-keybindings-row"):
                            yield Static(
                                "[bold white]Esc[/] Cancel", classes="keybinding"
                            )

                    with Vertical(classes="dialog-actions"):
                        yield Button("Cancel", id="cancel-btn")
                        yield Button("Rename", id="rename-btn", classes="primary")

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Extract the current name from the S3 path
        current_name = self._extract_name_from_s3_path(self.s3_path)

        # Update the current name field
        current_name_field = self.query_one("#current-name-field", Static)
        current_name_field.update(current_name)

        # Set the input field with the current name
        new_name_input = self.query_one("#new-name-input", Input)
        new_name_input.value = current_name

        # Focus the input field
        new_name_input.focus()

    def _extract_name_from_s3_path(self, s3_path: str) -> str:
        """Extract the file/folder name from S3 path."""
        if not s3_path or not s3_path.startswith("s3://"):
            return ""

        # Remove s3://bucket/ part
        path_parts = s3_path.replace("s3://", "").split("/", 1)
        if len(path_parts) < 2:
            return ""

        path = path_parts[1]

        # For folders, remove trailing slash
        if self.is_folder and path.endswith("/"):
            path = path[:-1]

        # Get the last part (filename/foldername)
        return os.path.basename(path)

    def _validate_new_name(self, new_name: str) -> tuple[bool, str]:
        """Validate the new name and return (is_valid, error_message)."""
        if not new_name.strip():
            return False, "Name cannot be empty"

        # Check for name conflicts with existing objects
        for obj in self.current_objects:
            obj_name = obj.get("key", "")
            if obj_name == new_name:
                return False, f"An item with name '{new_name}' already exists"

        return True, ""

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes to validate the name."""
        if event.input.id == "new-name-input":
            new_name = event.value.strip()
            is_valid, error_message = self._validate_new_name(new_name)

            # Update validation message
            validation_label = self.query_one("#name-validation", Label)
            rename_btn = self.query_one("#rename-btn", Button)

            if not new_name:
                validation_label.update("")
                rename_btn.disabled = True
            elif not is_valid:
                validation_label.update(f"❌ {error_message}")
                rename_btn.disabled = True
            else:
                validation_label.update("✅ Valid name")
                rename_btn.disabled = False

    def watch_is_renaming(self, is_renaming: bool) -> None:
        """React to renaming state changes."""
        try:
            progress_widget = self.query_one("#progress-indicator", ProgressWidget)
            dialog_header = self.query_one("#rename-dialog-header", Container)
            dialog_content = self.query_one("#rename-dialog-content", Container)
            dialog_footer = self.query_one("#rename-dialog-footer", Container)

            if is_renaming:
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
        elif event.button.id == "rename-btn":
            self.action_rename()

    def action_cancel(self) -> None:
        """Cancel the rename operation."""
        self.dismiss(False)

    def action_rename(self) -> None:
        """Start the rename operation."""
        if not self.s3_path:
            self.notify("No S3 path specified", severity="error")
            return

        new_name_input = self.query_one("#new-name-input", Input)
        new_name = new_name_input.value.strip()

        if not new_name:
            self.notify("New name cannot be empty", severity="error")
            return

        # Validate the name one more time
        is_valid, error_message = self._validate_new_name(new_name)
        if not is_valid:
            self.notify(f"Invalid name: {error_message}", severity="error")
            return

        # Start loading and perform rename asynchronously
        self.is_renaming = True

        # Use threading to rename asynchronously
        thread = threading.Thread(
            target=self._rename_async, args=(new_name,), daemon=True
        )
        thread.start()

    def _rename_async(self, new_name: str) -> None:
        """Asynchronously perform the rename operation."""
        try:
            # Extract bucket and current path from S3 URI
            s3_parts = self.s3_path.replace("s3://", "").split("/", 1)
            bucket_name = s3_parts[0]
            current_path = s3_parts[1] if len(s3_parts) > 1 else ""

            # Create new path
            if self.is_folder:
                # For folders, replace the folder name in the path
                if current_path.endswith("/"):
                    current_path = current_path[:-1]
                path_parts = current_path.split("/")
                path_parts[-1] = new_name
                new_path = "/".join(path_parts) + "/"

                # Use move_directory for folders
                S3.move_directory(
                    source_s3_bucket=bucket_name,
                    source_s3_prefix=current_path + "/",
                    destination_s3_bucket=bucket_name,
                    destination_s3_prefix=new_path,
                )
                item_type = "Folder"
            else:
                # For files, replace the filename in the path
                path_parts = current_path.split("/")
                path_parts[-1] = new_name
                new_path = "/".join(path_parts)

                # Use move_file for files
                S3.move_file(
                    source_s3_bucket=bucket_name,
                    source_s3_key=current_path,
                    destination_s3_bucket=bucket_name,
                    destination_s3_key=new_path,
                )
                item_type = "File"

            message = f"{item_type} renamed successfully to '{new_name}'"

            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_rename_success(message))

        except Exception as e:
            # Handle rename errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_rename_error(error))

    def _on_rename_success(self, message: str) -> None:
        """Handle successful rename completion."""
        self.is_renaming = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_rename_error(self, error: Exception) -> None:
        """Handle rename error."""
        self.is_renaming = False
        self.notify(f"Rename failed: {str(error)}", severity="error")
