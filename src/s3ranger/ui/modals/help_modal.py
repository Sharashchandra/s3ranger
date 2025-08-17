"""Help modal for S3Ranger."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class HelpModal(ModalScreen[bool]):
    """Modal screen displaying help information and keybindings for S3Ranger."""

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("enter", "cancel", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="help-dialog"):
            # Dialog header
            with Container(id="help-dialog-header"):
                yield Label("S3Ranger Help", classes="dialog-title")
                yield Label(
                    "Navigation, keybindings, and usage information | ESC to exit",
                    classes="dialog-subtitle",
                )

            # Dialog content
            with ScrollableContainer(id="help-dialog-content"):
                # Overview section
                with Vertical(classes="help-section"):
                    yield Label("Overview", classes="help-section-title")
                    yield Static(
                        "S3Ranger is a terminal-based file manager for Amazon S3 and S3-compatible services.\n"
                        "Navigate between buckets and objects using the keyboard or mouse.",
                        classes="help-text",
                    )

                # Navigation section
                with Vertical(classes="help-section"):
                    yield Label("Navigation", classes="help-section-title")
                    with Container(classes="help-keybindings"):
                        yield self._create_keybinding_row(
                            "Tab", "Switch between bucket list and object list"
                        )
                        yield self._create_keybinding_row(
                            "↑/↓", "Navigate up/down in lists"
                        )
                        yield self._create_keybinding_row(
                            "Enter", "Select bucket or enter folder"
                        )
                        yield self._create_keybinding_row(
                            "..", "Go back to parent folder"
                        )

                # File operations section
                with Vertical(classes="help-section"):
                    yield Label("File Operations", classes="help-section-title")
                    with Container(classes="help-keybindings"):
                        yield self._create_keybinding_row(
                            "d", "Download selected file/folder"
                        )
                        yield self._create_keybinding_row(
                            "u", "Upload file to current location"
                        )
                        yield self._create_keybinding_row(
                            "Delete", "Delete selected file/folder"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+k", "Rename selected file/folder"
                        )

                # General controls section
                with Vertical(classes="help-section"):
                    yield Label("General Controls", classes="help-section-title")
                    with Container(classes="help-keybindings"):
                        yield self._create_keybinding_row(
                            "Ctrl+r", "Refresh current view"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+f", "Focus filter input (bucket list)"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+h", "Show this help dialog"
                        )
                        yield self._create_keybinding_row("Ctrl+q", "Quit application")

                # Modal controls section
                with Vertical(classes="help-section"):
                    yield Label("Modal Controls", classes="help-section-title")
                    with Container(classes="help-keybindings"):
                        yield self._create_keybinding_row(
                            "Escape", "Cancel/close modal"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+Enter", "Confirm action in modals"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+o", "Open folder picker (download modal)"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+o", "Open file picker (upload modal)"
                        )
                        yield self._create_keybinding_row(
                            "Ctrl+l", "Open folder picker (upload modal)"
                        )

                # Tips section
                with Vertical(classes="help-section"):
                    yield Label("Tips", classes="help-section-title")
                    yield Static(
                        "• Use ~ in paths to refer to your home directory\n"
                        "• Folders are indicated with a trailing slash (/)\n"
                        "• The status bar shows connection info and current path\n"
                        "• On Mac: Use fn+Delete to delete a file (instead of just Delete)",
                        classes="help-text",
                    )

    def on_mount(self) -> None:
        """Called when the modal is mounted. Set focus to content for scrolling."""
        content = self.query_one("#help-dialog-content")
        content.focus()

    def _create_keybinding_row(self, key: str, description: str) -> Horizontal:
        """Create a keybinding row with key and description.

        Args:
            key: The keyboard shortcut
            description: Description of what the key does

        Returns:
            Horizontal container with the keybinding information
        """
        return Horizontal(
            Label(key, classes="help-keybinding-key"),
            Label(description, classes="help-keybinding-desc"),
            classes="help-keybinding-row",
        )

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(False)
