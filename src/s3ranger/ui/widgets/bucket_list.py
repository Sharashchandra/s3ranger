import threading
from threading import Timer

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator, Static

from s3ranger.gateways.s3 import S3
from s3ranger.ui.constants import (
    BUCKET_LIST_PAGE_SIZE,
    FILTER_DEBOUNCE_MS,
    SCROLL_THRESHOLD_ITEMS,
)
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
    buckets: list[dict] = reactive([])  # Currently displayed buckets
    filter_text: str = reactive("")
    is_loading: bool = reactive(False)  # Initial loading state
    is_loading_more: bool = reactive(False)  # Loading more (pagination) state
    has_more_buckets: bool = reactive(False)  # Whether more buckets are available

    # Internal state
    _prevent_next_selection: bool = False
    _on_load_complete_callback: callable = None
    _continuation_token: str | None = None  # Token for next page
    _all_loaded_buckets: list[dict] = []  # All buckets loaded so far (for local filtering)
    _loaded_bucket_names: set = set()  # Set of loaded bucket names (for deduplication)
    _filter_debounce_timer: Timer | None = None  # Debounce timer for server-side filter
    _is_fetching: bool = False  # Prevent duplicate fetch requests
    _preserve_position_on_update: bool = False  # Preserve scroll position on next list update
    _saved_scroll_position: int | None = None  # Saved position for restoration after loading more

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
            yield Static("Loading more...", id="bucket-loading-more")

    def on_mount(self) -> None:
        """Initialize the widget after mounting"""
        # Initialize internal state
        self._all_loaded_buckets = []
        self._loaded_bucket_names = set()
        self._continuation_token = None
        self._is_fetching = False
        self._preserve_position_on_update = False
        self._saved_scroll_position = None

        # Hide the loading more indicator initially
        try:
            loading_more = self.query_one("#bucket-loading-more", Static)
            loading_more.display = False
        except Exception:
            pass

        self.call_later(self.load_buckets)

    # Event handlers
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes"""
        if event.input.id == "bucket-filter":
            self.filter_text = event.value
            # Debounce server-side filter request
            self._schedule_server_filter()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle list item highlight for infinite scroll detection"""
        if event.item is None:
            return

        # Check if we're near the bottom of the list
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            current_index = list_view.index
            total_items = len(list_view.children)

            # If within threshold of the bottom and there are more buckets to load
            if (
                total_items - current_index <= SCROLL_THRESHOLD_ITEMS
                and self.has_more_buckets
                and not self._is_fetching
                and not self.filter_text
            ):  # Don't auto-load while filtering
                self._load_more_buckets()
        except Exception:
            pass

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
        preserve = self._preserve_position_on_update
        self._preserve_position_on_update = False  # Reset flag
        self._update_list_display(preserve_position=preserve)

    def watch_filter_text(self, filter_text: str) -> None:
        """React to filter text changes"""
        self._update_list_display()

    def watch_is_loading(self, is_loading: bool) -> None:
        """React to loading state changes"""
        self._update_loading_state(is_loading)

    def watch_is_loading_more(self, is_loading_more: bool) -> None:
        """React to loading more state changes"""
        self._update_loading_more_state(is_loading_more)

    # Public methods
    def load_buckets(self, on_complete: callable = None) -> None:
        """Load buckets from S3 asynchronously (initial load)

        Args:
            on_complete: Optional callback to call when loading is complete
        """
        # Reset pagination state for fresh load
        self._all_loaded_buckets = []
        self._loaded_bucket_names = set()
        self._continuation_token = None
        self.has_more_buckets = False

        self._on_load_complete_callback = on_complete
        self.is_loading = True
        self._is_fetching = True
        thread = threading.Thread(
            target=self._fetch_buckets,
            args=(None, False),  # No continuation token, not loading more
            daemon=True,
        )
        thread.start()

    def _load_more_buckets(self) -> None:
        """Load more buckets (pagination) - triggered by infinite scroll"""
        if self._is_fetching or not self.has_more_buckets or not self._continuation_token:
            return

        # Save current scroll position BEFORE starting async operation
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            self._saved_scroll_position = list_view.index
        except Exception:
            self._saved_scroll_position = None

        self.is_loading_more = True
        self._is_fetching = True
        thread = threading.Thread(
            target=self._fetch_buckets,
            args=(self._continuation_token, True),  # With token, loading more
            daemon=True,
        )
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
    def _fetch_buckets(self, continuation_token: str | None = None, is_loading_more: bool = False) -> None:
        """Fetch buckets from S3 in background thread

        Args:
            continuation_token: Token for fetching next page of results
            is_loading_more: Whether this is a pagination load (vs initial load)
        """
        try:
            response = S3.list_buckets(
                max_buckets=BUCKET_LIST_PAGE_SIZE,
                continuation_token=continuation_token,
            )
            raw_buckets = response["buckets"]
            next_token = response["continuation_token"]
            buckets = self._transform_bucket_data(raw_buckets)

            # Capture values for closure
            self.app.call_later(lambda: self._on_buckets_loaded(buckets, next_token, is_loading_more))
        except Exception as error:
            # Capture exception in closure for thread safety
            captured_error = error
            captured_is_loading_more = is_loading_more
            self.app.call_later(lambda: self._on_buckets_error(captured_error, captured_is_loading_more))

    def _on_buckets_loaded(
        self, buckets: list[dict], next_token: str | None = None, is_loading_more: bool = False
    ) -> None:
        """Handle successful bucket loading

        Args:
            buckets: List of bucket data
            next_token: Continuation token for next page
            is_loading_more: Whether this was a pagination load
        """
        self._is_fetching = False

        # Add new buckets to loaded set (for deduplication)
        for bucket in buckets:
            if bucket["name"] not in self._loaded_bucket_names:
                self._loaded_bucket_names.add(bucket["name"])
                self._all_loaded_buckets.append(bucket)

        # Update pagination state
        self._continuation_token = next_token
        self.has_more_buckets = next_token is not None

        # Update displayed buckets (apply filter if active)
        # Set flag to preserve position when loading more (pagination)
        self._preserve_position_on_update = is_loading_more
        self.buckets = self._get_filtered_buckets()

        # Update loading states
        if is_loading_more:
            self.is_loading_more = False
        else:
            self.is_loading = False

        self._update_connection_status(error=False)

        # Call the completion callback if one was provided
        if self._on_load_complete_callback:
            callback = self._on_load_complete_callback
            self._on_load_complete_callback = None  # Clear the callback
            callback()

    def _on_buckets_error(self, error: Exception, is_loading_more: bool = False) -> None:
        """Handle bucket loading error

        Args:
            error: The exception that occurred
            is_loading_more: Whether this was a pagination load
        """
        self._is_fetching = False
        self.notify(f"Error loading buckets: {error}", severity="error")

        # For pagination errors, keep existing buckets
        if is_loading_more:
            self.is_loading_more = False
        else:
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
        """Get buckets filtered by current filter text (local filtering)"""
        if not self.filter_text:
            return self._all_loaded_buckets.copy()

        filter_lower = self.filter_text.lower()
        return [bucket for bucket in self._all_loaded_buckets if filter_lower in bucket["name"].lower()]

    def _update_list_display(self, preserve_position: bool = False) -> None:
        """Update the bucket list display

        Args:
            preserve_position: If True, maintain the current highlighted index after update
        """
        filtered_buckets = self._get_filtered_buckets()
        self._update_title(len(filtered_buckets), len(self._all_loaded_buckets))
        self._populate_list_view(filtered_buckets, preserve_position=preserve_position)
        if not preserve_position:
            self._focus_first_item_if_needed()

    def _update_title(self, filtered_count: int, total_count: int) -> None:
        """Update the panel title with bucket counts"""
        try:
            title = self.query_one("#bucket-panel-title", Static)
            if self.filter_text:
                # Show filtered count vs total loaded
                title.update(f"Buckets ({filtered_count}/{total_count})")
            elif self.has_more_buckets:
                # Show count with indicator that more are available
                title.update(f"Buckets ({total_count}+)")
            else:
                title.update(f"Buckets ({total_count})")
        except Exception:
            pass

    def _populate_list_view(self, buckets: list[dict], preserve_position: bool = False) -> None:
        """Populate the ListView with bucket items

        Args:
            buckets: List of bucket data to display
            preserve_position: If True, only append new items instead of rebuilding
        """
        try:
            list_view = self.query_one("#bucket-list-view", ListView)

            if preserve_position:
                # When preserving position (loading more), only append new items
                # This keeps existing items and their highlight state intact
                existing_names = {child.bucket_name for child in list_view.children if isinstance(child, BucketItem)}
                for bucket in buckets:
                    if bucket["name"] not in existing_names:
                        bucket_item = BucketItem(bucket["name"], bucket["region"])
                        list_view.append(bucket_item)
            else:
                # Full rebuild for initial load or filter changes
                list_view.clear()
                for bucket in buckets:
                    bucket_item = BucketItem(bucket["name"], bucket["region"])
                    list_view.append(bucket_item)

            # Clear saved position after use
            self._saved_scroll_position = None
        except Exception:
            self._saved_scroll_position = None

    def _restore_list_position(self, index: int) -> None:
        """Restore the list view position after a refresh

        Args:
            index: The index to restore to
        """
        try:
            list_view = self.query_one("#bucket-list-view", ListView)
            if len(list_view.children) > 0:
                restored_index = min(index, len(list_view.children) - 1)
                # Set the index and force the ListView to update highlighting
                list_view.index = restored_index
                # Trigger a refresh of the ListView to update visual state
                list_view.refresh()
                # Scroll to make sure the highlighted item is visible
                if restored_index < len(list_view.children):
                    list_view.children[restored_index].scroll_visible()
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

    def _update_loading_more_state(self, is_loading_more: bool) -> None:
        """Update UI elements based on loading more state"""
        try:
            loading_more = self.query_one("#bucket-loading-more", Static)
            loading_more.display = is_loading_more
        except Exception:
            pass

    def _update_connection_status(self, error: bool) -> None:
        """Update the connection status in title bar"""
        try:
            title_bar = self.screen.query_one(TitleBar)
            title_bar.connection_error = error
        except Exception:
            pass

    # Server-side filtering methods
    def _schedule_server_filter(self) -> None:
        """Schedule a debounced server-side filter request"""
        # Cancel any pending filter request
        if self._filter_debounce_timer is not None:
            self._filter_debounce_timer.cancel()
            self._filter_debounce_timer = None

        # If filter is empty, just show local results
        if not self.filter_text:
            return

        # Only trigger server-side load if there are more buckets to load
        # (we need all buckets to do a proper "contains" search)
        if not self.has_more_buckets:
            return

        # Schedule new filter request after debounce delay
        self._filter_debounce_timer = Timer(
            FILTER_DEBOUNCE_MS / 1000.0,  # Convert ms to seconds
            self._trigger_server_filter,
        )
        self._filter_debounce_timer.start()

    def _trigger_server_filter(self) -> None:
        """Trigger the server-side filter request (called after debounce)

        Since S3 only supports prefix filtering (startswith) but we want contains filtering,
        we need to load ALL remaining buckets to do a proper local search.
        """
        if not self.filter_text or self._is_fetching or not self.has_more_buckets:
            return

        self._is_fetching = True
        # Load all remaining buckets so we can do a proper "contains" search
        thread = threading.Thread(target=self._fetch_all_remaining_buckets, args=(self.filter_text,), daemon=True)
        thread.start()

    def _fetch_all_remaining_buckets(self, original_filter: str) -> None:
        """Fetch ALL remaining buckets from server for filtering

        Since S3 only supports prefix filtering, we need to load all buckets
        to properly support "contains" filtering.

        Args:
            original_filter: The filter text when this request was initiated
        """
        try:
            continuation_token = self._continuation_token
            all_new_buckets = []

            # Keep fetching until we have all buckets
            while continuation_token:
                response = S3.list_buckets(
                    max_buckets=BUCKET_LIST_PAGE_SIZE,
                    continuation_token=continuation_token,
                )
                raw_buckets = response["buckets"]
                buckets = self._transform_bucket_data(raw_buckets)
                all_new_buckets.extend(buckets)
                continuation_token = response.get("continuation_token")

                # Check if filter changed - abort if so
                if self.filter_text != original_filter:
                    self.app.call_later(lambda: self._on_filter_fetch_aborted())
                    return

            # Capture values for closure
            captured_filter = original_filter
            self.app.call_later(lambda: self._on_all_buckets_loaded_for_filter(all_new_buckets, captured_filter))
        except Exception as error:
            captured_error = error
            self.app.call_later(lambda: self._on_filtered_buckets_error(captured_error))

    def _on_filter_fetch_aborted(self) -> None:
        """Handle aborted filter fetch (filter changed during fetch)"""
        self._is_fetching = False

    def _on_all_buckets_loaded_for_filter(self, buckets: list[dict], original_filter: str) -> None:
        """Handle successful loading of all buckets for filtering

        Args:
            buckets: List of all newly loaded bucket data
            original_filter: The filter that triggered this load
        """
        self._is_fetching = False

        # Check if filter has changed since request was made
        if self.filter_text != original_filter:
            return  # Ignore stale results

        # Add all new buckets to our loaded set (deduplicated)
        for bucket in buckets:
            if bucket["name"] not in self._loaded_bucket_names:
                self._loaded_bucket_names.add(bucket["name"])
                self._all_loaded_buckets.append(bucket)

        # Update pagination state - we now have all buckets
        self._continuation_token = None
        self.has_more_buckets = False

        # Re-filter and update display
        self.buckets = self._get_filtered_buckets()
        self._update_list_display()

    def _on_filtered_buckets_error(self, error: Exception) -> None:
        """Handle server-side filter error"""
        self._is_fetching = False
        # Don't show error notification for filter failures - just use local results
        # The user can still see locally filtered buckets
