import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, ListItem, ListView, LoadingIndicator, Static

from s3ranger.gateways.s3 import S3
from s3ranger.ui.utils import format_file_size, format_folder_display_text
from s3ranger.ui.widgets.breadcrumb import Breadcrumb
from s3ranger.ui.widgets.sort_overlay import SortOverlay

# Constants
PARENT_DIR_KEY = ".."
FILE_ICON = "📄"
COLUMN_NAMES = ["Name", "Type", "Modified", "Size"]


class ObjectItem(ListItem):
    """Individual item in the object list representing a file or folder."""

    def __init__(self, object_info: dict):
        super().__init__()
        # Extract only the fields we need
        self.object_info = {
            "key": object_info.get("key", ""),
            "is_folder": object_info.get("is_folder", False),
            "type": object_info.get("type", ""),
            "modified": object_info.get("modified", ""),
            "size": object_info.get("size", ""),
        }

    def _format_object_name(self, name: str, is_folder: bool) -> str:
        """Format object name with appropriate icon."""
        if is_folder:
            return format_folder_display_text(name)
        return f"{FILE_ICON} {name}"

    def compose(self) -> ComposeResult:
        """Render the object item with its properties in columns."""
        name_with_icon = self._format_object_name(
            self.object_info["key"], self.object_info["is_folder"]
        )
        with Horizontal():
            yield Label(name_with_icon, classes="object-key")
            yield Label(self.object_info["type"], classes="object-extension")
            yield Label(self.object_info["modified"], classes="object-modified")
            yield Label(self.object_info["size"], classes="object-size")

    @property
    def object_key(self) -> str:
        """The key (name) of this object."""
        return self.object_info["key"]

    @property
    def is_folder(self) -> bool:
        """Whether this object is a folder."""
        return self.object_info["is_folder"]


class ObjectList(Static):
    """Right panel widget displaying the contents of the selected S3 bucket."""

    BINDINGS = [
        Binding("d", "download", "Download"),
        Binding("u", "upload", "Upload"),
        Binding("delete", "delete_item", "Delete"),
        Binding("ctrl+k", "rename_item", "Rename"),
        Binding("ctrl+s", "show_sort_overlay", "Sort"),
    ]

    # Reactive properties
    objects: list[dict] = reactive([])
    current_bucket: str = reactive("")
    current_prefix: str = reactive("")
    is_loading: bool = reactive(False)
    sort_column: int | None = reactive(None)
    sort_ascending: bool = reactive(True)

    # Private cache for current level objects
    _all_objects: dict = {}
    _on_load_complete_callback: callable = None
    _unsorted_objects: list[dict] = []  # Cache of unsorted objects

    class ObjectSelected(Message):
        """Message sent when an object is selected."""

        def __init__(self, object_key: str, is_folder: bool) -> None:
            super().__init__()
            self.object_key = object_key
            self.is_folder = is_folder

    def compose(self) -> ComposeResult:
        with Vertical(id="object-list-container"):
            yield Breadcrumb()
            with Horizontal(id="object-list-header"):
                yield Label("Name", classes="object-name-header")
                yield Label("Type", classes="object-type-header")
                yield Label("Modified", classes="object-modified-header")
                yield Label("Size", classes="object-size-header")
            yield LoadingIndicator(id="object-loading")
            yield ListView(id="object-list")

    def on_mount(self) -> None:
        """Initialize the widget when mounted."""
        pass

    # Event handlers
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle object selection"""
        if isinstance(event.item, ObjectItem):
            if event.item.is_folder:
                self._handle_folder_selection(event.item.object_key)
            else:
                self._handle_file_selection(event.item.object_key)

    # Reactive watchers
    def watch_current_bucket(self, bucket_name: str) -> None:
        """React to bucket changes."""
        if bucket_name:
            self._clear_selection()
            self.is_loading = True
            self.current_prefix = ""
            self._update_breadcrumb()
            self._load_bucket_objects()

    def watch_current_prefix(self, prefix: str) -> None:
        """React to prefix changes."""
        self._update_breadcrumb()
        # Objects will be loaded by navigation methods

    def watch_objects(self, objects: list[dict]) -> None:
        """React to objects list changes."""
        self._update_list_display()
        # Focus is handled in _on_objects_loaded

    def watch_is_loading(self, is_loading: bool) -> None:
        """React to loading state changes."""
        self._update_loading_state(is_loading)

    # Public methods
    def set_bucket(self, bucket_name: str) -> None:
        """Set the current bucket and load its objects."""
        self.current_bucket = bucket_name

    # Private methods
    def _update_breadcrumb(self) -> None:
        """Update the breadcrumb navigation display."""
        try:
            breadcrumb = self.query_one(Breadcrumb)
            breadcrumb.set_path(self.current_bucket, self.current_prefix)
        except Exception:
            # Breadcrumb not ready yet, silently ignore
            pass

    def _focus_first_item(self) -> None:
        """Focus the first item in the list."""
        try:
            # First just make sure the list view is visible
            list_view = self.query_one("#object-list", ListView)
            list_view.display = True

            # Use a slightly longer delay for the actual focus operation
            # This gives the UI time to fully render, especially with many objects
            self.set_timer(0.1, self._apply_focus)
        except Exception:
            # Fall back to focusing the widget itself
            self.focus()

    def _apply_focus(self) -> None:
        """Apply focus to the list view after it's fully rendered."""
        try:
            list_view = self.query_one("#object-list", ListView)
            list_view.focus()
            if len(list_view.children) > 0:
                list_view.index = 0
                # Schedule another follow-up focus with additional delay
                self.set_timer(0.2, self._ensure_focus)
        except Exception:
            pass

    def _ensure_focus(self) -> None:
        """Final focus check to ensure the list view maintains focus."""
        try:
            list_view = self.query_one("#object-list", ListView)
            if list_view.display and len(list_view.children) > 0:
                # Check if we're already the focused widget
                app_focus = self.app.focused
                if app_focus != list_view:
                    # If not, explicitly set focus again
                    list_view.focus()

                # Always ensure an item is selected
                if list_view.index is None:
                    list_view.index = 0
        except Exception:
            pass

    def _update_loading_state(self, is_loading: bool) -> None:
        """Toggle loading indicator and list view visibility based on loading state."""
        try:
            loading_indicator = self.query_one("#object-loading", LoadingIndicator)
            list_view = self.query_one("#object-list", ListView)

            if is_loading:
                # When starting to load, immediately hide the list and show the loader
                list_view.display = False
                loading_indicator.display = True
            else:
                # When finishing loading, first hide the loader
                loading_indicator.display = False
                # Then show the list view (the actual focus will be handled separately)
                list_view.display = True
        except Exception:
            pass

    def _update_list_display(self) -> None:
        """Populate the list view with object items."""
        try:
            list_view = self.query_one("#object-list", ListView)
            list_view.clear()

            # Add all objects to the list view
            for obj in self.objects:
                list_view.append(ObjectItem(obj))
        except Exception:
            # Silent failure if list view isn't ready yet
            pass

    def _load_bucket_objects(self) -> None:
        """Load objects from the current S3 bucket prefix."""
        if not self.current_bucket:
            self._clear_objects()
            return

        # Start asynchronous loading
        thread = threading.Thread(target=self._load_objects_async, daemon=True)
        thread.start()

    def _load_objects_async(self) -> None:
        """Asynchronously load objects from S3."""
        try:
            objects = S3.list_objects_for_prefix(
                bucket_name=self.current_bucket, prefix=self.current_prefix
            )
            self.app.call_later(lambda: self._on_objects_loaded(objects))
        except Exception as error:
            # Capture the error explicitly in the closure
            def report_error(err=error):
                self._on_objects_error(err)

            self.app.call_later(report_error)

    def _on_objects_loaded(self, objects: dict) -> None:
        """Handle successful objects loading."""
        self._all_objects = objects
        self._filter_objects_by_prefix()

        # Calculate delay based on number of objects (more objects = longer delay)
        obj_count = len(self.objects)
        focus_delay = min(0.2, 0.05 + (obj_count * 0.002))  # Scale up to max 0.2s

        # First stop loading
        self.is_loading = False

        # Then schedule focus with a calculated delay based on object count
        self.set_timer(focus_delay, self._focus_first_item)

        self._execute_completion_callback()

    def _on_objects_error(self, error: Exception) -> None:
        """Handle objects loading error."""
        self._clear_objects()
        self.is_loading = False
        self.notify(f"Error loading bucket objects: {error}", severity="error")

        self._execute_completion_callback()

    def _execute_completion_callback(self) -> None:
        """Execute and clear the completion callback if one exists."""
        if self._on_load_complete_callback:
            callback = self._on_load_complete_callback
            self._on_load_complete_callback = None
            callback()

    def _clear_objects(self) -> None:
        """Reset object state when no data is available."""
        self._all_objects = {}
        self.objects = []
        self.is_loading = False

    def _clear_selection(self) -> None:
        """Clear list selection and hide the list view during navigation."""
        try:
            list_view = self.query_one("#object-list", ListView)
            list_view.index = None
            list_view.display = False
        except Exception:
            # ListView might not be available yet, silently ignore
            pass

    def _filter_objects_by_prefix(self) -> None:
        """Filter cached objects to show only those matching the current prefix."""
        if not self._all_objects:
            self.objects = []
            self._unsorted_objects = []
            return

        unsorted_objects = self._build_ui_objects(self._all_objects)
        self._unsorted_objects = unsorted_objects

        # Apply current sorting if any
        if self.sort_column is not None:
            self.objects = self._sort_objects(
                unsorted_objects, self.sort_column, self.sort_ascending
            )
        else:
            self.objects = unsorted_objects

    def _build_ui_objects(self, s3_response: dict) -> list[dict]:
        """Transform S3 response into UI-friendly format."""
        ui_objects = []

        # Add parent directory navigation if in a subfolder
        if self.current_prefix:
            ui_objects.append(self._create_parent_dir_object())

        # Add folders from the response
        folders = s3_response.get("folders", [])
        for folder in folders:
            prefix = folder["Prefix"]
            # Extract folder name by removing the current prefix and trailing slash
            folder_name = prefix[len(self.current_prefix) :].rstrip("/")
            if folder_name:  # Only add if we get a valid folder name
                ui_objects.append(self._create_folder_object(folder_name))

        # Add files from the response
        files = s3_response.get("files", [])
        for s3_object in files:
            key = s3_object["Key"]
            # Extract filename by removing the current prefix
            filename = key[len(self.current_prefix) :]
            if filename:  # Only add if we get a valid filename
                ui_objects.append(self._create_file_object(filename, s3_object))

        return ui_objects

    def _create_parent_dir_object(self) -> dict:
        """Create the parent directory (..) object."""
        return {
            "key": PARENT_DIR_KEY,
            "is_folder": True,
            "size": "",
            "modified": "",
            "type": "dir",
        }

    def _create_folder_object(self, folder_name: str) -> dict:
        """Create a folder object for the UI."""
        return {
            "key": folder_name,
            "is_folder": True,
            "size": "",  # No size for folders since we don't fetch all files
            "modified": "",  # No modified date since we don't fetch folder metadata
            "type": "dir",
        }

    def _create_file_object(self, filename: str, s3_object: dict) -> dict:
        """Create a file object for the UI."""
        return {
            "key": filename,
            "is_folder": False,
            "size": format_file_size(s3_object["Size"]),
            "modified": s3_object["LastModified"].strftime("%Y-%m-%d %H:%M"),
            "type": self._get_file_extension(filename),
        }

    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if not filename or "." not in filename:
            return ""
        return filename.split(".")[-1].lower()

    def _handle_folder_selection(self, folder_key: str) -> None:
        """Handle folder selection and navigation."""
        if folder_key == PARENT_DIR_KEY:
            self._navigate_up()
        else:
            self._navigate_into_folder(folder_key)

    def _handle_file_selection(self, file_key: str) -> None:
        """Handle file selection."""
        self.post_message(self.ObjectSelected(file_key, False))

    def _navigate_up(self) -> None:
        """Navigate to the parent directory."""
        if not self.current_prefix:
            return

        self._prepare_for_navigation()

        # Calculate parent directory path
        path_parts = self.current_prefix.rstrip("/").split("/")
        if len(path_parts) > 1:
            self.current_prefix = "/".join(path_parts[:-1]) + "/"
        else:
            self.current_prefix = ""

        self._load_bucket_objects()

    def _navigate_into_folder(self, folder_name: str) -> None:
        """Navigate into the specified folder."""
        self._prepare_for_navigation()
        self.current_prefix = f"{self.current_prefix}{folder_name}/"
        self._load_bucket_objects()

    def _prepare_for_navigation(self) -> None:
        """Prepare UI for folder navigation."""
        self._clear_selection()
        self.is_loading = True

    # Utility methods
    def get_focused_object(self) -> dict | None:
        """Get the currently focused object in the list."""
        try:
            list_view = self.query_one("#object-list", ListView)
            if list_view.index is None or not self.objects:
                return None

            focused_index = list_view.index
            if 0 <= focused_index < len(self.objects):
                return self.objects[focused_index]
            return None
        except Exception:
            return None

    def get_s3_uri_for_focused_object(self) -> str | None:
        """Get the S3 URI for the currently focused object."""
        focused_obj = self.get_focused_object()
        if not focused_obj or not self.current_bucket:
            return None

        # Handle parent directory case
        if focused_obj["key"] == "..":
            return None

        # Construct the full S3 path from breadcrumb (current prefix) + object key
        if focused_obj["is_folder"]:
            # For folders, combine current prefix with folder name
            full_path = f"{self.current_prefix}{focused_obj['key']}/"
        else:
            # For files, combine current prefix with file name
            full_path = f"{self.current_prefix}{focused_obj['key']}"

        return f"s3://{self.current_bucket}/{full_path}"

    def get_current_s3_location(self) -> str | None:
        """Get the S3 URI for the current location (bucket + prefix)."""
        if not self.current_bucket:
            return None

        # Construct S3 URI for current location
        if self.current_prefix:
            return f"s3://{self.current_bucket}/{self.current_prefix}"
        else:
            return f"s3://{self.current_bucket}/"

    def refresh_objects(self, on_complete: callable = None) -> None:
        """Refresh the object list for the current bucket.

        Args:
            on_complete: Optional callback to call when loading is complete
        """
        self._on_load_complete_callback = on_complete
        self._prepare_for_navigation()  # Reuse navigation preparation logic
        self._load_bucket_objects()

    def focus_list(self) -> None:
        """Focus the object list view."""
        self._focus_first_item()  # Reuse focus logic

    # Action methods
    def action_download(self) -> None:
        """Download selected items"""
        # Get the currently focused object
        s3_uri = self.get_s3_uri_for_focused_object()
        focused_obj = self.get_focused_object()

        if not s3_uri or not focused_obj:
            self.notify("No object selected for download", severity="error")
            return

        # Determine if it's a folder or file
        is_folder = focused_obj.get("is_folder", False)

        # Import here to avoid circular imports
        from s3ranger.ui.modals.download_modal import DownloadModal

        # Show the download modal
        def on_download_result(result: bool) -> None:
            if result:
                # Download was successful, refresh the view if needed
                self.refresh_objects()
            # Always restore focus to the object list after modal closes
            self.call_later(self.focus_list)

        self.app.push_screen(DownloadModal(s3_uri, is_folder), on_download_result)

    def action_upload(self) -> None:
        """Upload files to current location"""
        # Get the current S3 location (bucket + prefix)
        current_location = self.get_current_s3_location()

        if not current_location:
            self.notify("No bucket selected for upload", severity="error")
            return

        # Always upload to current location (bucket root or current prefix)
        # This ensures we upload to the current directory, not to a focused folder
        upload_destination = current_location

        # Import here to avoid circular imports
        from s3ranger.ui.modals.upload_modal import UploadModal

        # Show the upload modal
        def on_upload_result(result: bool) -> None:
            if result:
                # Upload was successful, refresh the view
                self.refresh_objects()
            # Always restore focus to the object list after modal closes
            self.call_later(self.focus_list)

        self.app.push_screen(UploadModal(upload_destination, False), on_upload_result)

    def action_delete_item(self) -> None:
        """Delete selected items"""
        # Get the currently focused object
        s3_uri = self.get_s3_uri_for_focused_object()
        focused_obj = self.get_focused_object()

        if not s3_uri or not focused_obj:
            self.notify("No object selected for deletion", severity="error")
            return

        # Determine if it's a folder or file
        is_folder = focused_obj.get("is_folder", False)

        # Check if this is the last item in the current directory (excluding parent dir)
        actual_items = [obj for obj in self.objects if obj.get("key") != ".."]
        is_last_item = len(actual_items) == 1 and actual_items[0].get(
            "key"
        ) == focused_obj.get("key")

        # Import here to avoid circular imports
        from s3ranger.ui.modals.delete_modal import DeleteModal

        # Show the delete modal
        def on_delete_result(result: bool) -> None:
            if result:
                # Delete was successful
                if is_last_item and self.current_prefix:
                    # This was the last item and we're not at bucket root, navigate up
                    self._navigate_up()
                else:
                    # Just refresh the view normally
                    self.refresh_objects()
            # Always restore focus to the object list after modal closes
            self.call_later(self.focus_list)

        self.app.push_screen(DeleteModal(s3_uri, is_folder), on_delete_result)

    def action_rename_item(self) -> None:
        """Rename selected item"""
        # Get the currently focused object
        s3_uri = self.get_s3_uri_for_focused_object()
        focused_obj = self.get_focused_object()

        if not s3_uri or not focused_obj:
            self.notify("No object selected for renaming", severity="error")
            return

        # Don't allow renaming of parent directory entry
        if focused_obj.get("key") == "..":
            self.notify("Cannot rename parent directory entry", severity="error")
            return

        # Determine if it's a folder or file
        is_folder = focused_obj.get("is_folder", False)

        # Import here to avoid circular imports
        from s3ranger.ui.modals.rename_modal import RenameModal

        # Show the rename modal
        def on_rename_result(result: bool) -> None:
            if result:
                # Rename was successful, refresh the view
                self.refresh_objects()
            # Always restore focus to the object list after modal closes
            self.call_later(self.focus_list)

        self.app.push_screen(
            RenameModal(s3_uri, is_folder, self.objects), on_rename_result
        )

    # Sorting functionality
    def action_show_sort_overlay(self) -> None:
        """Show the sort overlay for column selection."""

        def on_sort_result(column_index: int | None) -> None:
            self._on_sort_selected(column_index)
            # Always restore focus to the object list after modal closes
            self.call_later(self.focus_list)

        self.app.push_screen(SortOverlay(object_list=self), on_sort_result)

    def _on_sort_selected(self, column_index: int | None) -> None:
        """Handle sort column selection."""
        if column_index is not None:
            # If the same column is selected, toggle sort direction
            if self.sort_column == column_index:
                self.sort_ascending = not self.sort_ascending
            else:
                self.sort_column = column_index
                self.sort_ascending = False  # Start with descending for new columns

            # Apply sorting to current objects
            self.objects = self._sort_objects(
                self._unsorted_objects, self.sort_column, self.sort_ascending
            )

            # Update header to show sort indicator
            self._update_header_sort_indicators()

    def _update_header_sort_indicators(self) -> None:
        """Update header labels to show current sort column and direction."""
        try:
            header_container = self.query_one("#object-list-header")
            labels = header_container.query(Label)

            for idx, label in enumerate(labels):
                if idx < len(COLUMN_NAMES):
                    base_name = COLUMN_NAMES[idx]

                    if self.sort_column == idx:
                        indicator = "↑" if self.sort_ascending else "↓"
                        label.update(f"{base_name} {indicator}")
                    else:
                        label.update(base_name)
        except Exception:
            # Silently ignore if headers not available
            pass

    def _sort_objects(
        self, objects: list[dict], column_index: int, ascending: bool
    ) -> list[dict]:
        """Sort objects by the specified column."""
        if not objects or column_index is None:
            return objects

        # Don't sort parent directory - always keep it at top
        PARENT_DIR_KEY = ".."
        parent_dir = [obj for obj in objects if obj.get("key") == PARENT_DIR_KEY]
        other_objects = [obj for obj in objects if obj.get("key") != PARENT_DIR_KEY]

        if not other_objects:
            return objects

        # Define sort keys for each column
        sort_keys = {
            0: self._get_name_sort_key,  # Name
            1: self._get_type_sort_key,  # Type
            2: self._get_modified_sort_key,  # Modified
            3: self._get_size_sort_key,  # Size
        }

        sort_key_func = sort_keys.get(column_index)
        if sort_key_func:
            try:
                sorted_objects = sorted(
                    other_objects, key=sort_key_func, reverse=not ascending
                )
            except Exception:
                # Fall back to original order if sorting fails
                sorted_objects = other_objects
        else:
            sorted_objects = other_objects

        return parent_dir + sorted_objects

    def _get_name_sort_key(self, obj: dict) -> tuple:
        """Get sort key for name column - folders first, then files."""
        is_folder = obj.get("is_folder", False)
        name = obj.get("key", "").lower()
        return (not is_folder, name)  # False (folders) sorts before True (files)

    def _get_type_sort_key(self, obj: dict) -> tuple:
        """Get sort key for type column."""
        is_folder = obj.get("is_folder", False)
        type_str = obj.get("type", "").lower()
        return (not is_folder, type_str)

    def _get_modified_sort_key(self, obj: dict) -> tuple:
        """Get sort key for modified column."""
        is_folder = obj.get("is_folder", False)
        modified = obj.get("modified", "")
        # Empty dates (folders) should sort to end when ascending, start when descending
        if not modified:
            return (not is_folder, "")
        return (not is_folder, modified)

    def _get_size_sort_key(self, obj: dict) -> tuple:
        """Get sort key for size column."""
        is_folder = obj.get("is_folder", False)
        if is_folder:
            return (0, 0)  # Folders have no size, sort first

        size_str = obj.get("size", "")
        if not size_str:
            return (1, 0)

        # Parse size string to get numeric value for proper sorting
        try:
            # Remove units and convert to bytes for comparison
            size_bytes = self._parse_size_to_bytes(size_str)
            return (1, size_bytes)
        except Exception:
            return (1, 0)

    def _parse_size_to_bytes(self, size_str: str) -> int:
        """Parse size string like '1.2 MB' to bytes for sorting."""
        if not size_str:
            return 0

        size_str = size_str.strip().upper()

        # Define units with their multipliers - check longer units first
        units = [
            ("TB", 1024**4),
            ("GB", 1024**3),
            ("MB", 1024**2),
            ("KB", 1024),
            ("B", 1),
        ]

        # Check for unit suffix
        for unit, multiplier in units:
            if size_str.endswith(unit):
                number_part = size_str[: -len(unit)].strip()
                try:
                    return int(float(number_part) * multiplier)
                except ValueError:
                    return 0

        # Try to parse as plain number
        try:
            return int(float(size_str))
        except ValueError:
            return 0
