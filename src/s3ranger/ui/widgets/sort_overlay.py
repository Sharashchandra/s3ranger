from textual import events
from textual.screen import ModalScreen

# Constants
SORT_KEYS = ["1", "2", "3", "4"]
COLUMN_NAMES = ["Name", "Type", "Modified", "Size"]


class SortOverlay(ModalScreen[int | None]):
    """Overlay that updates headers with sort numbers."""

    DEFAULT_CSS = """
    SortOverlay {
        background: black 25%;
    }
    """

    def __init__(self, object_list):
        super().__init__()
        self.object_list = object_list

    def compose(self):
        """No visible widgets - this is an invisible overlay."""
        return []

    def on_mount(self):
        """Update headers when the overlay mounts."""
        self._update_headers_with_numbers()

    def _update_headers_with_numbers(self):
        """Update the object list headers to show sort numbers."""
        try:
            header_container = self.object_list.query_one("#object-list-header")
            labels = header_container.query("Label")

            for idx, label in enumerate(labels):
                if idx < len(COLUMN_NAMES):
                    base_name = COLUMN_NAMES[idx]
                    label.update(f"{base_name} [bold $accent]\\[{idx + 1}][/]")
        except Exception:
            pass

    def _restore_headers(self):
        """Restore headers to their original state."""
        self.object_list._update_header_sort_indicators()

    def on_key(self, event: events.Key) -> None:
        """Handle key press events for sorting."""
        event.stop()
        event.prevent_default()

        if event.key in SORT_KEYS:
            col_idx = SORT_KEYS.index(event.key)
            self._restore_headers()
            self.dismiss(col_idx)
        elif event.key == "escape":
            self._restore_headers()
            self.dismiss(None)
