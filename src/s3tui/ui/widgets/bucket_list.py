"""Bucket list widget for displaying S3 buckets."""

from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from s3tui.services.s3_list import S3ListService


class BucketList(ListView):
    """Widget for displaying and selecting S3 buckets."""

    class BucketSelected(Message):
        """Message sent when a bucket is selected."""

        def __init__(self, bucket_name: str) -> None:
            self.bucket_name = bucket_name
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.buckets = []

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        self.load_buckets()

    def load_buckets(self) -> None:
        """Load S3 buckets and populate the list."""
        try:
            self.buckets = S3ListService.list_s3_buckets()
            self.clear()

            for bucket in self.buckets:
                bucket_name = bucket["Name"]
                bucket_region = bucket.get("BucketRegion", "Unknown")
                display_text = f"{bucket_name} ({bucket_region})"
                self.append(ListItem(Static(display_text), id=f"bucket-{bucket_name}"))

            # Focus on the bucket list
            self.focus()

        except Exception as e:
            # Clear and show error
            self.clear()
            self.append(ListItem(Static(f"Error loading buckets: {str(e)}"), id="error"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle bucket selection."""
        if event.list_view == self:
            # Extract bucket name from the item ID
            item_id = event.item.id
            if item_id and item_id.startswith("bucket-"):
                bucket_name = item_id[7:]  # Remove "bucket-" prefix
                # Post a message to the parent screen
                self.post_message(self.BucketSelected(bucket_name))

    def refresh_buckets(self) -> None:
        """Refresh the bucket list."""
        self.load_buckets()
