import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator, Static

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets.title_bar import TitleBar


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
    """Left panel widget displaying S3 buckets with filtering capability"""

    BINDINGS = [Binding("ctrl+f", "focus_filter", "Filter")]

    # Reactive properties
    buckets: list[dict] = reactive([])
    filter_text: str = reactive("")
    is_loading: bool = reactive(False)

    # Internal state
    _prevent_next_selection: bool = False
    _on_load_complete_callback: callable = None

    class BucketSelected(Message):
        """Message sent when a bucket is selected"""

        def __init__(self, bucket_name: str) -> None:
            super().__init__()
            self.bucket_name = bucket_name

    def compose(self) -> ComposeResult:
        with Vertical(id="bucket-list-container"):
            yield Static("Buckets", id="bucket-panel-title")
            yield Input(placeholder="Filter buckets...", id="bucket-filter")
            yield LoadingIndicator(id="bucket-loading")
            yield ListView(id="bucket-list-view")

    def on_mount(self) -> None:
        """Initialize the widget after mounting"""
        self.call_later(self.load_buckets)

    # Event handlers
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes"""
        if event.input.id == "bucket-filter":
            self.filter_text = event.value

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle bucket selection"""
        if self._prevent_next_selection:
            self._prevent_next_selection = False
            return

        if isinstance(event.item, BucketItem):
            self.post_message(self.BucketSelected(event.item.bucket_name))

    def on_key(self, event: Key) -> None:
        """Handle keyboard shortcuts"""
        if event.key == "escape" and self.filter_text:
            self.clear_filter()
            event.prevent_default()
        elif event.key == "ctrl+f":
            self.focus_filter()
            event.prevent_default()
        elif event.key == "enter":
            filter_input = self.query_one("#bucket-filter", Input)
            if filter_input.has_focus:
                self._move_to_first_item()
                event.prevent_default()

    # Reactive watchers
    def watch_buckets(self, buckets: list[dict]) -> None:
        """React to buckets data changes"""
        self._update_list_display()

    def watch_filter_text(self, filter_text: str) -> None:
        """React to filter text changes"""
        self._update_list_display()

    def watch_is_loading(self, is_loading: bool) -> None:
        """React to loading state changes"""
        self._update_loading_state(is_loading)

    # Public methods
    def load_buckets(self, on_complete: callable = None) -> None:
        """Load buckets from S3 asynchronously

        Args:
            on_complete: Optional callback to call when loading is complete
        """
        self._on_load_complete_callback = on_complete
        self.is_loading = True
        thread = threading.Thread(target=self._fetch_buckets, daemon=True)
        thread.start()

    def clear_filter(self) -> None:
        """Clear the current filter"""
        try:
            filter_input = self.query_one("#bucket-filter", Input)
            filter_input.value = ""
            self.filter_text = ""
        except Exception:
            pass

    def focus_filter(self) -> None:
        """Focus the filter input"""
        try:
            filter_input = self.query_one("#bucket-filter", Input)
            filter_input.focus()
        except Exception:
            pass

    def focus_list_view(self) -> None:
        """Focus the bucket list view and select first item"""
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            if len(list_view.children) > 0:
                list_view.focus()
                list_view.index = 0
        except Exception:
            pass

    # Private methods
    def _fetch_buckets(self) -> None:
        """Fetch buckets from S3 in background thread"""
        try:
            raw_buckets = S3.list_buckets()
            buckets = self._transform_bucket_data(raw_buckets)
            self.app.call_later(lambda: self._on_buckets_loaded(buckets))
        except Exception as error:
            # Capture exception in closure for thread safety
            captured_error = error
            self.app.call_later(lambda: self._on_buckets_error(captured_error))

    def _on_buckets_loaded(self, buckets: list[dict]) -> None:
        """Handle successful bucket loading"""
        self.buckets = buckets
        self.is_loading = False
        self._update_connection_status(error=False)

        # Call the completion callback if one was provided
        if self._on_load_complete_callback:
            callback = self._on_load_complete_callback
            self._on_load_complete_callback = None  # Clear the callback
            callback()

    def _on_buckets_error(self, error: Exception) -> None:
        """Handle bucket loading error"""
        self.notify(f"Error loading buckets: {error}", severity="error")
        self.buckets = []
        self.is_loading = False
        self._update_connection_status(error=True)

        # Call the completion callback even on error
        if self._on_load_complete_callback:
            callback = self._on_load_complete_callback
            self._on_load_complete_callback = None  # Clear the callback
            callback()

    def _transform_bucket_data(self, raw_buckets: list[dict]) -> list[dict]:
        """Transform raw S3 bucket data"""
        return [
            {
                "name": bucket["Name"],
                "creation_date": bucket["CreationDate"].strftime("%Y-%m-%d"),
                "region": bucket.get("BucketRegion", "Unknown"),
            }
            for bucket in raw_buckets
        ]

    def _get_filtered_buckets(self) -> list[dict]:
        """Get buckets filtered by current filter text"""
        if not self.filter_text:
            return self.buckets

        filter_lower = self.filter_text.lower()
        return [
            bucket for bucket in self.buckets if filter_lower in bucket["name"].lower()
        ]

    def _update_list_display(self) -> None:
        """Update the bucket list display"""
        filtered_buckets = self._get_filtered_buckets()
        self._update_title(len(filtered_buckets), len(self.buckets))
        self._populate_list_view(filtered_buckets)
        self._focus_first_item_if_needed()

    def _update_title(self, filtered_count: int, total_count: int) -> None:
        """Update the panel title with bucket counts"""
        try:
            title = self.query_one("#bucket-panel-title", Static)
            if self.filter_text:
                title.update(f"Buckets ({filtered_count}/{total_count})")
            else:
                title.update(f"Buckets ({total_count})")
        except Exception:
            pass

    def _populate_list_view(self, buckets: list[dict]) -> None:
        """Populate the ListView with bucket items"""
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            list_view.clear()
            for bucket in buckets:
                bucket_item = BucketItem(bucket["name"], bucket["region"])
                list_view.append(bucket_item)
        except Exception:
            pass

    def _focus_first_item_if_needed(self) -> None:
        """Focus first item only if filter input doesn't have focus"""
        try:
            filter_input = self.query_one("#bucket-filter", Input)

            # If the filter input doesn't have focus, ensure the list view gets proper focus
            if not filter_input.has_focus:
                self._focus_first_item()
        except Exception:
            pass

    def _focus_first_item(self) -> None:
        """Focus the first item in the list"""
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            if len(list_view.children) > 0:
                # First, focus the list view itself
                list_view.focus()
                # Then set the index to ensure proper navigation
                list_view.index = 0
        except Exception:
            pass

    def _move_to_first_item(self) -> None:
        """Move focus to first filtered item without selecting"""
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            if len(list_view.children) > 0:
                self._prevent_next_selection = True
                list_view.focus()
                list_view.index = 0
        except Exception:
            pass

    def _update_loading_state(self, is_loading: bool) -> None:
        """Update UI elements based on loading state"""
        try:
            loading_indicator = self.query_one("#bucket-loading", LoadingIndicator)
            list_view = self.query_one("#bucket-list-view", ListView)
            filter_input = self.query_one("#bucket-filter", Input)

            if is_loading:
                loading_indicator.display = True
                list_view.display = False
                filter_input.disabled = True
            else:
                loading_indicator.display = False
                list_view.display = True
                filter_input.disabled = False
        except Exception:
            pass

    def _update_connection_status(self, error: bool) -> None:
        """Update the connection status in title bar"""
        try:
            title_bar = self.screen.query_one(TitleBar)
            title_bar.connection_error = error
        except Exception:
            pass
