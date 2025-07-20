"""Path bar widget for displaying current S3 path."""

from textual.widgets import Static


class PathBar(Static):
    """Widget for displaying and managing the current S3 path."""

    def __init__(self, initial_path: str = "s3://", **kwargs):
        super().__init__(f"Path: {initial_path}", **kwargs)
        self._current_path = initial_path

    def update_path(self, path: str) -> None:
        """Update the current path and display."""
        self._current_path = path
        self.update(f"Path: {path}")

    def get_path(self) -> str:
        """Get the current path."""
        return self._current_path

    def reset_path(self) -> None:
        """Reset the path to root."""
        self.update_path("/")

    def navigate_to_bucket(self, bucket_name: str) -> None:
        """Navigate to a specific bucket."""
        self.update_path(f"s3://{bucket_name}/")

    def navigate_to_folder(self, bucket_name: str, folder_path: str) -> None:
        """Navigate to a specific folder within a bucket."""
        # Ensure folder path ends with / if it's not empty
        if folder_path and not folder_path.endswith("/"):
            folder_path += "/"
        self.update_path(f"s3://{bucket_name}/{folder_path}")

    def get_bucket_name(self) -> str | None:
        """Extract bucket name from current path."""
        if self._current_path.startswith("s3://"):
            parts = self._current_path[5:].split("/", 1)
            return parts[0] if parts[0] else None
        return None

    def get_folder_path(self) -> str:
        """Extract folder path from current path."""
        if self._current_path.startswith("s3://"):
            parts = self._current_path[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else ""
        return ""
