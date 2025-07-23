from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, ListItem, ListView, Static


class BucketItem(ListItem):
    """Individual bucket item widget"""

    def __init__(self, bucket_name: str, aws_region: str = "us-east-1"):
        super().__init__()
        self._bucket_name = bucket_name
        self._aws_region = aws_region

    def compose(self) -> ComposeResult:
        yield Label(self._bucket_name, classes="bucket-name")
        yield Label(f"Region: {self._aws_region}", classes="bucket-meta")

    @property
    def bucket_name(self) -> str:
        return self._bucket_name


class BucketList(Static):
    """Left panel widget displaying S3 buckets"""

    buckets: list[dict] = reactive([])
    selected_bucket = reactive(0)

    class BucketSelected(Message):
        """Message sent when a bucket is selected"""

        def __init__(self, bucket_name: str) -> None:
            super().__init__()
            self.bucket_name = bucket_name

    def compose(self) -> ComposeResult:
        with Vertical(id="bucket-list-container"):
            yield Static("Buckets", id="bucket-panel-title")
            yield ListView(id="bucket-list-view")

    def on_mount(self) -> None:
        """Called when the widget is mounted - load dummy buckets"""
        self._load_dummy_buckets()

    def watch_buckets(self, buckets: list[dict]) -> None:
        """Called when buckets reactive property changes"""
        self._update_bucket_list()

    def _load_dummy_buckets(self) -> None:
        """Load dummy bucket data for testing"""
        dummy_buckets = [
            {"name": "d-galesandbox-prod", "creation_date": "2024-01-15", "region": "us-east-1"},
            {"name": "d-galesandbox-staging", "creation_date": "2024-01-10", "region": "us-west-2"},
            {"name": "d-galesandbox-dev", "creation_date": "2024-01-05", "region": "eu-west-1"},
            {"name": "d-galesandbox-backup", "creation_date": "2024-01-01", "region": "us-east-1"},
            {"name": "d-galesandbox-logs", "creation_date": "2023-12-20", "region": "us-west-1"},
        ]
        self.buckets = dummy_buckets

    def _update_bucket_list(self) -> None:
        """Update the bucket list UI (called from main thread)"""
        # Update title
        title = self.query_one("#bucket-panel-title", Static)
        title.update(f"Buckets ({len(self.buckets)})")

        # Clear and repopulate ListView
        list_view = self.query_one("#bucket-list-view", ListView)
        list_view.clear()

        for bucket in self.buckets:
            bucket_item = BucketItem(bucket["name"], bucket["region"])
            list_view.append(bucket_item)

        # Focus the first item after populating the list
        self._focus_first_item()

    def _focus_first_item(self) -> None:
        """Focus on the first item in the bucket list."""
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            if len(list_view.children) > 0:
                list_view.focus()
                list_view.index = 0
        except Exception:
            # List view not ready yet, ignore
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle bucket selection from ListView"""
        if isinstance(event.item, BucketItem):
            # Update the selected bucket index
            bucket_items = list(self.query(BucketItem))
            try:
                self.selected_bucket = bucket_items.index(event.item)
                self.notify(f"Selected bucket: {event.item.bucket_name}")
                # Post message to parent screen
                self.post_message(self.BucketSelected(event.item.bucket_name))
            except ValueError:
                pass
