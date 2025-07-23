"""Bucket list widget for displaying S3 buckets."""

from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from s3tui.gateways.s3 import S3
from s3tui.ui.utils import (
    extract_identifier_from_id,
    generate_item_id,
)

# Constants for better maintainability
BUCKET_ID_PREFIX = "bucket-"
DEFAULT_REGION = "Unknown"
ERROR_ITEM_ID = "error"


class BucketList(ListView):
    """Widget for displaying and selecting S3 buckets."""

    class BucketSelected(Message):
        """Message sent when a bucket is selected."""

        def __init__(self, bucket_name: str) -> None:
            self.bucket_name = bucket_name
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.buckets: list[dict] = []

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.load_buckets()

    def load_buckets(self) -> None:
        """Load S3 buckets and populate the list."""
        try:
            # self.buckets = S3.list_buckets()
            self.buckets = S3.list_buckets()
            self._populate_bucket_list()
            self.focus()
        except Exception as e:
            self._show_error(f"Error loading buckets: {str(e)}")

    def _populate_bucket_list(self) -> None:
        """Populate the list with bucket items."""
        self.clear()
        for bucket in self.buckets:
            list_item = self._create_bucket_list_item(bucket)
            self.append(list_item)

    def _create_bucket_list_item(self, bucket: dict) -> ListItem:
        """Create a list item for a bucket.

        Args:
            bucket: Bucket dictionary containing Name and optionally BucketRegion

        Returns:
            ListItem configured with bucket display text and ID
        """
        bucket_name = bucket["Name"]
        bucket_region = bucket.get("BucketRegion", DEFAULT_REGION)
        display_text = self._format_bucket_display_text(bucket_name, bucket_region)
        item_id = self._generate_bucket_item_id(bucket_name)
        return ListItem(Static(display_text), id=item_id)

    def _format_bucket_display_text(self, bucket_name: str, region: str) -> str:
        """Format the display text for a bucket."""
        return f"{bucket_name} ({region})"

    def _generate_bucket_item_id(self, bucket_name: str) -> str:
        """Generate a unique item ID for a bucket."""
        return generate_item_id(BUCKET_ID_PREFIX, bucket_name)

    def _show_error(self, error_message: str) -> None:
        """Display an error message in the list."""
        self.clear()
        error_item = ListItem(Static(error_message), id=ERROR_ITEM_ID)
        self.append(error_item)

    def _extract_bucket_name_from_id(self, item_id: str) -> str | None:
        """Extract bucket name from item ID.

        Args:
            item_id: The item ID (e.g., "bucket-my-bucket-name")

        Returns:
            The bucket name or None if ID doesn't match expected format
        """
        return extract_identifier_from_id(item_id, BUCKET_ID_PREFIX)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle bucket selection."""
        if event.list_view != self:
            return

        item_id = event.item.id
        bucket_name = self._extract_bucket_name_from_id(item_id)

        if bucket_name:
            self.post_message(self.BucketSelected(bucket_name))

    def refresh_buckets(self) -> None:
        """Refresh the bucket list."""
        self.load_buckets()
