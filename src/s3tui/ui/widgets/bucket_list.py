import threading

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, ListItem, ListView, LoadingIndicator, Static

from s3tui.gateways.s3 import S3
from s3tui.ui.widgets.title_bar import TitleBar


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
    is_loading: bool = reactive(False)

    class BucketSelected(Message):
        """Message sent when a bucket is selected"""

        def __init__(self, bucket_name: str) -> None:
            super().__init__()
            self.bucket_name = bucket_name

    def compose(self) -> ComposeResult:
        with Vertical(id="bucket-list-container"):
            yield Static("Buckets", id="bucket-panel-title")
            yield LoadingIndicator(id="bucket-loading")
            yield ListView(id="bucket-list-view")

    def on_mount(self) -> None:
        """Called when the widget is mounted"""
        # Load buckets after UI is ready
        self.call_later(self.load_buckets)

    def watch_buckets(self, buckets: list[dict]) -> None:
        """Called when buckets reactive property changes"""
        self._update_bucket_list()

    def watch_is_loading(self, is_loading: bool) -> None:
        """React to loading state changes."""
        try:
            loading_indicator = self.query_one("#bucket-loading", LoadingIndicator)
            list_view = self.query_one("#bucket-list-view", ListView)

            if is_loading:
                loading_indicator.display = True
                list_view.display = False
            else:
                loading_indicator.display = False
                list_view.display = True
        except Exception:
            # Widgets not ready yet, silently ignore
            pass

    def load_buckets(self) -> None:
        """Load buckets from S3 with loading indicator."""
        # Start loading
        self.is_loading = True

        # Use threading to load buckets asynchronously
        thread = threading.Thread(target=self._load_buckets_async, daemon=True)
        thread.start()

    def _load_buckets_async(self) -> None:
        """Asynchronously load buckets from S3."""
        try:
            raw_buckets = S3.list_buckets()
            buckets = self._transform_buckets_data(raw_buckets)
            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_buckets_loaded(buckets))
        except Exception as e:
            # Handle S3 errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_buckets_error(error))

    def _on_buckets_loaded(self, buckets: list[dict]) -> None:
        """Handle successful buckets loading."""
        self.buckets = buckets
        self.is_loading = False
        
        # Reset connected indicator to normal (green) state
        try:
            title_bar = self.screen.query_one(TitleBar)
            title_bar.connection_error = False
        except Exception:
            # Title bar not found or not ready, ignore
            pass

    def _on_buckets_error(self, error: Exception) -> None:
        """Handle buckets loading error."""
        self.notify(f"Error loading buckets: {error}", severity="error")
        self.buckets = []
        self.is_loading = False
        
        # Change connected indicator to red to show error state
        try:
            title_bar = self.screen.query_one(TitleBar)
            title_bar.connection_error = True
        except Exception:
            # Title bar not found or not ready, ignore
            pass

    def _transform_buckets_data(self, buckets: list[dict]) -> list[dict]:
        """Transform raw bucket data into a more usable format"""
        return [
            {
                "name": bucket["Name"],
                "creation_date": bucket["CreationDate"].strftime("%Y-%m-%d"),
                "region": bucket.get("BucketRegion", "Unknown"),  # Default to us-east-1 if not specified
            }
            for bucket in buckets
        ]

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
                # Post message to parent screen
                self.post_message(self.BucketSelected(event.item.bucket_name))
            except ValueError:
                pass
