"""Object list widget for displaying S3 bucket objects."""

from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from s3tui.services.s3_list import S3ListService


class ObjectList(ListView):
    """Widget for displaying and selecting S3 bucket objects."""

    class ObjectSelected(Message):
        """Message sent when an object is selected."""

        def __init__(self, object_key: str, bucket_name: str) -> None:
            self.object_key = object_key
            self.bucket_name = bucket_name
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.objects = []
        self.current_bucket = None
        self._loading = False
        self._id_to_key_map = {}  # Maps safe IDs to actual object keys

    def show_loading(self, bucket_name: str) -> None:
        """Show loading state for the object list."""
        self.clear()
        self._loading = True
        self.current_bucket = bucket_name
        self._id_to_key_map.clear()  # Clear the mapping when loading
        self.append(ListItem(Static(f"Loading objects from {bucket_name}..."), id="loading"))

    def show_empty_bucket(self, bucket_name: str) -> None:
        """Show empty bucket state."""
        self.clear()
        self._loading = False
        self.current_bucket = bucket_name
        self._id_to_key_map.clear()  # Clear the mapping
        self.append(ListItem(Static(f"Bucket '{bucket_name}' is empty"), id="empty"))

    def show_placeholder(self) -> None:
        """Show placeholder when no bucket is selected."""
        self.clear()
        self._loading = False
        self.current_bucket = None
        self._id_to_key_map.clear()  # Clear the mapping
        self.append(ListItem(Static("Select a bucket to view its contents"), id="placeholder"))

    async def load_objects_for_bucket(self, bucket_name: str, prefix: str = None) -> None:
        """Load objects for the specified bucket."""
        self.show_loading(bucket_name)

        try:
            # Fetch objects in background thread
            objects = S3ListService.list_s3_objects(bucket_name=bucket_name, prefix=prefix)

            # Update UI on main thread
            self.objects = objects
            self.current_bucket = bucket_name
            self.clear()
            self._loading = False
            self._id_to_key_map.clear()  # Clear previous mapping

            if not objects:
                self.show_empty_bucket(bucket_name)
                return

            for index, obj in enumerate(self.objects):
                object_key = obj["Key"]
                size = obj.get("Size", 0)

                # Create a safe ID for Textual (using index to ensure uniqueness)
                safe_id = f"object_{index}"
                # Map the safe ID to the actual object key
                self._id_to_key_map[safe_id] = object_key

                # Format the display text
                if size > 0:
                    # Format size in human-readable format
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    elif size < 1024 * 1024 * 1024:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    else:
                        size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
                else:
                    size_str = "0 B"

                # Format the display text with object name and size
                display_text = f"{object_key} ({size_str})"
                self.append(ListItem(Static(display_text), id=safe_id))

        except Exception as e:
            # Show error and keep focusable
            self.clear()
            self._loading = False
            self.current_bucket = bucket_name
            self.append(ListItem(Static(f"Error loading objects: {str(e)}"), id="error"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle object selection."""
        if event.list_view == self:
            # Don't allow selection while loading
            if self._loading:
                return

            # Extract the safe ID and map it to the actual object key
            item_id = event.item.id
            if item_id and item_id in self._id_to_key_map:
                object_key = self._id_to_key_map[item_id]
                if self.current_bucket:
                    # Post a message to the parent screen with the actual object key
                    self.post_message(self.ObjectSelected(object_key, self.current_bucket))

    def refresh_objects(self) -> None:
        """Refresh the object list for the current bucket."""
        if self.current_bucket:
            self.run_worker(self.load_objects_for_bucket(self.current_bucket))
        else:
            self.show_placeholder()
