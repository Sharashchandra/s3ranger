from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class Breadcrumb(Static):
    """Breadcrumb navigation widget for S3 path navigation"""

    bucket_name: str = reactive("")
    prefix: str = reactive("")
    separator: str = reactive(" / ")

    class BreadcrumbClicked(Message):
        """Message sent when a breadcrumb segment is clicked"""

        def __init__(self, target_prefix: str) -> None:
            super().__init__()
            self.target_prefix = target_prefix

    def __init__(self, separator: str = "/", **kwargs) -> None:
        super().__init__("", id="breadcrumb-bar", **kwargs)
        self.separator = separator

    def watch_bucket_name(self, bucket_name: str) -> None:
        """Called when bucket name changes"""
        self._update_breadcrumb()

    def watch_prefix(self, prefix: str) -> None:
        """Called when prefix changes"""
        self._update_breadcrumb()

    def watch_separator(self, separator: str) -> None:
        """Called when separator changes"""
        self._update_breadcrumb()

    def _update_breadcrumb(self) -> None:
        """Update the breadcrumb navigation display"""
        if not self.bucket_name:
            self.update("")
            return

        if not self.prefix:
            # When no prefix, bucket is the active location (white)
            self.update(self.bucket_name)
        else:
            # Split prefix into parts and create breadcrumb
            parts = self.prefix.rstrip("/").split("/")
            breadcrumb_text = f"[dim]{self.bucket_name}[/dim]"

            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Last part is active (white)
                    breadcrumb_text += f"[dim]{self.separator}[/dim]{part}"
                else:
                    # All other parts are grey
                    breadcrumb_text += f"[dim]{self.separator}{part}[/dim]"

            self.update(breadcrumb_text)

    def set_path(self, bucket_name: str, prefix: str = "") -> None:
        """Set both bucket name and prefix at once"""
        self.bucket_name = bucket_name
        self.prefix = prefix

    def clear(self) -> None:
        """Clear the breadcrumb"""
        self.bucket_name = ""
        self.prefix = ""

    def get_path_segments(self) -> list[tuple[str, str]]:
        """Get list of (display_name, target_prefix) tuples for each breadcrumb segment"""
        segments = []

        if not self.bucket_name:
            return segments

        # Add bucket as first segment
        segments.append((self.bucket_name, ""))

        if self.prefix:
            parts = self.prefix.rstrip("/").split("/")
            current_prefix = ""

            for part in parts:
                current_prefix += part + "/"
                segments.append((part, current_prefix))

        return segments

    def set_separator(self, separator: str) -> None:
        """Set the separator between breadcrumb segments"""
        self.separator = separator
