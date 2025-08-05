import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, ListItem, ListView, LoadingIndicator, Static

from s3tui.gateways.s3 import S3
from s3tui.ui.utils import format_file_size, format_folder_display_text
from s3tui.ui.widgets.breadcrumb import Breadcrumb

# Constants
PARENT_DIR_KEY = ".."
FILE_ICON = "📄"


class ObjectItem(ListItem):
    """Individual object item widget"""

    def __init__(self, object_info: dict):
        super().__init__()
        self.object_info = self._extract_object_info(object_info)

    def _extract_object_info(self, object_info: dict) -> dict:
        """Extract relevant information from the object info dictionary."""
        is_folder = object_info.get("is_folder", False)
        key = object_info.get("key", "")

        return {
            "key": key,
            "is_folder": is_folder,
            "type": object_info.get("type", ""),
            "modified": object_info.get("modified", ""),
            "size": object_info.get("size", ""),
        }

    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if not filename or "." not in filename:
            return ""
        return filename.split(".")[-1].lower()

    def _format_object_name(self, name: str, is_folder: bool) -> str:
        """Format object name with appropriate icon."""
        if is_folder:
            return format_folder_display_text(name)
        return f"{FILE_ICON} {name}"

    def compose(self) -> ComposeResult:
        name_with_icon = self._format_object_name(self.object_info["key"], self.object_info["is_folder"])
        with Horizontal():
            yield Label(name_with_icon, classes="object-key")
            yield Label(self.object_info["type"], classes="object-extension")
            yield Label(self.object_info["modified"], classes="object-modified")
            yield Label(self.object_info["size"], classes="object-size")

    @property
    def object_key(self) -> str:
        return self.object_info["key"]

    @property
    def is_folder(self) -> bool:
        return self.object_info["is_folder"]


class ObjectList(Static):
    """Right panel widget displaying the contents of the selected S3 bucket."""

    BINDINGS = [
        Binding("d", "download", "Download"),
        Binding("u", "upload", "Upload"),
        Binding("delete", "delete_item", "Delete"),
    ]

    # Reactive properties
    objects: list[dict] = reactive([])
    current_bucket: str = reactive("")
    current_prefix: str = reactive("")
    is_loading: bool = reactive(False)

    # Private cache for current level objects
    _all_objects: dict = {}
    _on_load_complete_callback: callable = None

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
            # Clear selection first to prevent highlight flashing
            self._clear_selection()
            # Set loading state to prevent UI flash
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
        # Note: Focus is now handled in _update_loading_state and _on_objects_loaded

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
        """Focus the first item in the list"""
        try:
            list_view = self.query_one("#object-list", ListView)
            if len(list_view.children) > 0:
                # Make sure the list view is visible
                list_view.display = True
                # Focus the list view itself
                list_view.focus()
                # Set the index to select the first item
                list_view.index = 0
                # Request another focus call to ensure it sticks
                self.set_timer(0.1, self._ensure_focus)
        except Exception:
            # If we can't focus the list, at least focus the widget itself
            self.focus()

    def _ensure_focus(self) -> None:
        """Ensure focus is maintained on the list view"""
        try:
            list_view = self.query_one("#object-list", ListView)
            if list_view.display and len(list_view.children) > 0:
                # Focus the list view again to ensure it keeps focus
                list_view.focus()
                if list_view.index is None:
                    list_view.index = 0
        except Exception:
            pass

    def _update_loading_state(self, is_loading: bool) -> None:
        """Update UI elements based on loading state"""
        try:
            loading_indicator = self.query_one("#object-loading", LoadingIndicator)
            list_view = self.query_one("#object-list", ListView)

            if is_loading:
                loading_indicator.display = True
                list_view.display = False
            else:
                loading_indicator.display = False
                list_view.display = True
                # Don't set focus here - we'll handle it in _on_objects_loaded
                # with proper timing
        except Exception:
            pass

    def _update_list_display(self) -> None:
        """Update the object list display"""
        try:
            list_view = self.query_one("#object-list", ListView)
            list_view.clear()
            for obj in self.objects:
                list_view.append(ObjectItem(obj))
        except Exception:
            pass

    def _load_bucket_objects(self) -> None:
        """Load objects from the current S3 bucket prefix."""
        if not self.current_bucket:
            self._clear_objects()
            return

        # Note: is_loading should be set before calling this method
        # to prevent UI flash when navigating

        # Use threading to load objects asynchronously
        thread = threading.Thread(target=self._load_objects_async, daemon=True)
        thread.start()

    def _load_objects_async(self) -> None:
        """Asynchronously load objects from S3."""
        try:
            # Use the new list_objects_for_prefix method with current prefix
            objects = S3.list_objects_for_prefix(bucket_name=self.current_bucket, prefix=self.current_prefix)
            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_objects_loaded(objects))
        except Exception as e:
            # Handle S3 errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_objects_error(error))

    def _on_objects_loaded(self, objects: dict) -> None:
        """Handle successful objects loading."""
        self._all_objects = objects
        self._filter_objects_by_prefix()
        self.is_loading = False

        # Focus the first item in the list after loading with a slight delay
        # to ensure the UI has fully updated
        self.set_timer(0.05, self._focus_first_item)

        # Call the completion callback if one was provided
        if self._on_load_complete_callback:
            callback = self._on_load_complete_callback
            self._on_load_complete_callback = None  # Clear the callback
            callback()

    def _on_objects_error(self, error: Exception) -> None:
        """Handle objects loading error."""
        self._clear_objects()
        self.is_loading = False
        # Optionally show an error message
        self.notify(f"Error loading bucket objects: {error}", severity="error")

        # Call the completion callback even on error
        if self._on_load_complete_callback:
            callback = self._on_load_complete_callback
            self._on_load_complete_callback = None  # Clear the callback
            callback()

    def _clear_objects(self) -> None:
        """Clear all object data."""
        self._all_objects = {}
        self.objects = []
        self.is_loading = False

    def _clear_selection(self) -> None:
        """Clear the current selection in the list view to prevent highlighting flashes."""
        try:
            list_view = self.query_one("#object-list", ListView)
            # Reset the index to clear selection
            list_view.index = None
            # Make sure the list isn't visible during navigation
            list_view.display = False
        except Exception:
            # ListView might not be available yet, silently ignore
            pass

    def _filter_objects_by_prefix(self) -> None:
        """Filter cached objects to show only those matching the current prefix."""
        if not self._all_objects:
            self.objects = []
            return

        self.objects = self._build_ui_objects(self._all_objects)

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
        return {"key": PARENT_DIR_KEY, "is_folder": True, "size": "", "modified": "", "type": "dir"}

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

        # Clear selection first to prevent highlight flashing
        self._clear_selection()

        # Set loading state to prevent UI flash
        self.is_loading = True

        path_parts = self.current_prefix.rstrip("/").split("/")
        if len(path_parts) > 1:
            self.current_prefix = "/".join(path_parts[:-1]) + "/"
        else:
            self.current_prefix = ""

        # Reload objects for the new prefix
        self._load_bucket_objects()

    def _navigate_into_folder(self, folder_name: str) -> None:
        """Navigate into the specified folder."""
        # Clear selection first to prevent highlight flashing
        self._clear_selection()

        # Set loading state to prevent UI flash
        self.is_loading = True

        self.current_prefix = f"{self.current_prefix}{folder_name}/"

        # Reload objects for the new prefix
        self._load_bucket_objects()

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
        # Clear selection first to prevent highlight flashing
        self._clear_selection()
        self.is_loading = True
        self._load_bucket_objects()

    def focus_list(self) -> None:
        """Focus the object list view"""
        try:
            list_view = self.query_one("#object-list", ListView)
            if len(list_view.children) > 0:
                list_view.focus()
                list_view.index = 0
        except Exception:
            # List not ready, focus the widget itself
            super().focus()

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
        from s3tui.ui.modals.download_modal import DownloadModal

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
        from s3tui.ui.modals.upload_modal import UploadModal

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

        # Import here to avoid circular imports
        from s3tui.ui.modals.delete_modal import DeleteModal

        # Show the delete modal
        def on_delete_result(result: bool) -> None:
            if result:
                # Delete was successful, refresh the view
                self.refresh_objects()
            # Always restore focus to the object list after modal closes
            self.call_later(self.focus_list)

        self.app.push_screen(DeleteModal(s3_uri, is_folder), on_delete_result)
