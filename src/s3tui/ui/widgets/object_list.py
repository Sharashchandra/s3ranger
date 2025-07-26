import threading

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable, LoadingIndicator, Static

from s3tui.gateways.s3 import S3

from ..utils import format_file_size, format_folder_display_text
from .breadcrumb import Breadcrumb

# Constants
PARENT_DIR_KEY = ".."
FILE_ICON = "📄"
DEFAULT_TABLE_ROW_HEIGHT = 2
TABLE_COLUMNS = ["Name", "Type", "Modified", "Size"]


class ObjectList(Static):
    """Widget for displaying S3 objects with navigation support."""

    # Reactive properties
    objects: list[dict] = reactive([])
    current_bucket: str = reactive("")
    current_prefix: str = reactive("")
    selected_objects: set[int] = reactive(set())
    is_loading: bool = reactive(False)

    # Private cache for all bucket objects
    _all_objects: list[dict] = []
    _table_mounted: bool = False

    class ObjectSelected(Message):
        """Message sent when an object is selected."""

        def __init__(self, object_key: str, is_folder: bool) -> None:
            super().__init__()
            self.object_key = object_key
            self.is_folder = is_folder

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Vertical(id="object-list-container"):
            yield Breadcrumb()
            yield LoadingIndicator(id="object-loading")

    def on_mount(self) -> None:
        """Initialize the widget when mounted."""
        # Don't setup table immediately - wait for bucket selection
        pass

    def _setup_table(self) -> None:
        """Configure the data table columns and styling."""
        table = self.query_one("#object-table", DataTable)
        table.add_columns(*TABLE_COLUMNS)
        table.cursor_type = "row"
        table.zebra_stripes = False

    def _ensure_table_mounted(self) -> None:
        """Ensure the datatable is mounted and configured."""
        if not self._table_mounted:
            # Mount the datatable
            container = self.query_one("#object-list-container", Vertical)
            table = DataTable(id="object-table")
            container.mount(table)
            self._setup_table()
            self._table_mounted = True

    def _focus_first_row(self) -> None:
        """Focus on the first row in the object table."""
        try:
            if not self._table_mounted:
                return
            table = self.query_one("#object-table", DataTable)
            if table.row_count > 0:
                table.focus()
                table.move_cursor(row=0)
        except Exception:
            # Table not ready yet, silently ignore
            pass

    def watch_current_bucket(self, bucket_name: str) -> None:
        """React to bucket changes."""
        if bucket_name:
            # Mount the datatable when a bucket is selected for the first time
            self._ensure_table_mounted()
            self.current_prefix = ""
            self._update_breadcrumb()
            self._load_bucket_objects()
            self._focus_first_row()

    def watch_current_prefix(self, prefix: str) -> None:
        """React to prefix changes."""
        self._update_breadcrumb()
        self._filter_objects_by_prefix()

    def watch_objects(self, objects: list[dict]) -> None:
        """React to objects list changes."""
        self._update_table_display()
        self._focus_first_row()

    def watch_is_loading(self, is_loading: bool) -> None:
        """React to loading state changes."""
        try:
            loading_indicator = self.query_one("#object-loading", LoadingIndicator)

            if self._table_mounted:
                table = self.query_one("#object-table", DataTable)
                if is_loading:
                    loading_indicator.display = True
                    table.display = False
                else:
                    loading_indicator.display = False
                    table.display = True
            else:
                # If table not mounted, just show/hide loading indicator
                loading_indicator.display = is_loading
        except Exception:
            # Widgets not ready yet, silently ignore
            pass

    def _update_breadcrumb(self) -> None:
        """Update the breadcrumb navigation display."""
        try:
            breadcrumb = self.query_one(Breadcrumb)
            breadcrumb.set_path(self.current_bucket, self.current_prefix)
        except Exception:
            # Breadcrumb not ready yet, silently ignore
            pass

    def _load_bucket_objects(self) -> None:
        """Load all objects from the current S3 bucket."""
        if not self.current_bucket:
            self._clear_objects()
            return

        # Start loading
        self.is_loading = True

        # Use threading to load objects asynchronously
        thread = threading.Thread(target=self._load_objects_async, daemon=True)
        thread.start()

    def _load_objects_async(self) -> None:
        """Asynchronously load objects from S3."""
        try:
            s3_uri = f"s3://{self.current_bucket}/"
            objects = S3.list_objects(s3_uri=s3_uri)
            # Update state on the main thread using call_later
            self.app.call_later(lambda: self._on_objects_loaded(objects))
        except Exception as e:
            # Handle S3 errors gracefully - capture exception in closure
            error = e
            self.app.call_later(lambda: self._on_objects_error(error))

    def _on_objects_loaded(self, objects: list[dict]) -> None:
        """Handle successful objects loading."""
        self._all_objects = objects
        self._filter_objects_by_prefix()
        self.is_loading = False

    def _on_objects_error(self, error: Exception) -> None:
        """Handle objects loading error."""
        self._clear_objects()
        self.is_loading = False
        # Optionally show an error message
        self.notify(f"Error loading bucket objects: {error}", severity="error")

    def _clear_objects(self) -> None:
        """Clear all object data."""
        self._all_objects = []
        self.objects = []
        self.is_loading = False

    def _filter_objects_by_prefix(self) -> None:
        """Filter cached objects to show only those matching the current prefix."""
        if not self._all_objects:
            self.objects = []
            return

        self.objects = self._build_ui_objects(self._all_objects)

    def _build_ui_objects(self, raw_objects: list[dict]) -> list[dict]:
        """Transform S3 objects into UI-friendly format with folder hierarchy."""
        ui_objects = []
        folders = set()

        # Add parent directory navigation if in a subfolder
        if self.current_prefix:
            ui_objects.append(self._create_parent_dir_object())

        # Process each S3 object
        for s3_object in raw_objects:
            key = s3_object["Key"]
            relative_path = self._get_relative_path(key)

            if not relative_path:
                continue

            if self._is_folder_path(relative_path):
                folder_name = self._extract_folder_name(relative_path)
                if folder_name not in folders:
                    folders.add(folder_name)
                    ui_objects.append(self._create_folder_object(folder_name))
            else:
                ui_objects.append(self._create_file_object(relative_path, s3_object))

        return ui_objects

    def _create_parent_dir_object(self) -> dict:
        """Create the parent directory (..) object."""
        return {"key": PARENT_DIR_KEY, "is_folder": True, "size": "", "modified": "", "type": "dir"}

    def _create_folder_object(self, folder_name: str) -> dict:
        """Create a folder object for the UI."""
        return {"key": folder_name, "is_folder": True, "size": "", "modified": "", "type": "dir"}

    def _create_file_object(self, filename: str, s3_object: dict) -> dict:
        """Create a file object for the UI."""
        return {
            "key": filename,
            "is_folder": False,
            "size": format_file_size(s3_object["Size"]),
            "modified": s3_object["LastModified"].strftime("%Y-%m-%d %H:%M"),
            "type": self._get_file_extension(filename),
        }

    def _get_relative_path(self, key: str) -> str:
        """Get the relative path from the current prefix."""
        if self.current_prefix and not key.startswith(self.current_prefix):
            return ""
        return key[len(self.current_prefix) :] if self.current_prefix else key

    def _is_folder_path(self, path: str) -> bool:
        """Check if the path represents a folder (contains subdirectories)."""
        return "/" in path

    def _extract_folder_name(self, path: str) -> str:
        """Extract the folder name from a path."""
        return path.split("/")[0]

    def _update_table_display(self) -> None:
        """Update the table with current objects."""
        if not self._table_mounted:
            return

        table = self.query_one("#object-table", DataTable)
        table.clear(columns=False)

        for i, obj in enumerate(self.objects):
            name_with_icon = self._format_object_name(obj["key"], obj["is_folder"])
            table.add_row(
                name_with_icon, obj["type"], obj["modified"], obj["size"], key=str(i), height=DEFAULT_TABLE_ROW_HEIGHT
            )

    def _format_object_name(self, name: str, is_folder: bool) -> str:
        """Format object name with appropriate icon."""
        if is_folder:
            return format_folder_display_text(name)
        return f"{FILE_ICON} {name}"

    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if not filename or "." not in filename:
            return ""
        return filename.split(".")[-1].lower()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        if event.row_key is None:
            return

        row_index = int(event.row_key.value)
        if not (0 <= row_index < len(self.objects)):
            return

        selected_object = self.objects[row_index]

        if selected_object["is_folder"]:
            self._handle_folder_selection(selected_object["key"])
        else:
            self._handle_file_selection(selected_object["key"])

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

        path_parts = self.current_prefix.rstrip("/").split("/")
        if len(path_parts) > 1:
            self.current_prefix = "/".join(path_parts[:-1]) + "/"
        else:
            self.current_prefix = ""

    def _navigate_into_folder(self, folder_name: str) -> None:
        """Navigate into the specified folder."""
        self.current_prefix = f"{self.current_prefix}{folder_name}/"

    def set_bucket(self, bucket_name: str) -> None:
        """Set the current bucket and load its objects."""
        self.current_bucket = bucket_name

    def get_focused_object(self) -> dict | None:
        """Get the currently focused object in the table."""
        try:
            if not self._table_mounted:
                return None
            table = self.query_one("#object-table", DataTable)
            if table.cursor_row is None or not self.objects:
                return None

            cursor_row = table.cursor_row
            if 0 <= cursor_row < len(self.objects):
                return self.objects[cursor_row]
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

    def refresh_objects(self) -> None:
        """Refresh the object list for the current bucket."""
        self._load_bucket_objects()

    def focus(self) -> None:
        """Override focus to only focus the table if it's mounted."""
        if self._table_mounted:
            try:
                table = self.query_one("#object-table", DataTable)
                table.focus()
            except Exception:
                # Table not ready, focus the widget itself
                super().focus()
        else:
            # If table not mounted, focus the widget itself
            super().focus()
