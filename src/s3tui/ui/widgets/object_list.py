from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from ..utils import format_folder_display_text
from .breadcrumb import Breadcrumb


class ObjectList(Static):
    """Right panel widget displaying S3 objects"""

    objects: list[dict] = reactive([])
    current_bucket: str = reactive("")
    current_prefix: str = reactive("")
    selected_objects: set[int] = reactive(set())

    class ObjectSelected(Message):
        """Message sent when object is selected"""

        def __init__(self, object_key: str, is_folder: bool) -> None:
            super().__init__()
            self.object_key = object_key
            self.is_folder = is_folder

    def compose(self) -> ComposeResult:
        with Vertical(id="object-list-container"):
            # Breadcrumb bar
            yield Breadcrumb()

            # Object list table
            yield DataTable(id="object-table")

    def on_mount(self) -> None:
        """Initialize the object table when mounted"""
        self._setup_table()

    def _setup_table(self) -> None:
        """Setup the data table columns and styling"""
        table = self.query_one("#object-table", DataTable)
        table.add_columns("Name", "Type", "Modified", "Size")
        table.cursor_type = "row"
        table.zebra_stripes = False

    def _focus_first_item(self, widget_id: str = "object-table") -> None:
        """Focus on the first item in the object table.

        Args:
            widget_id: The ID of the table widget to focus
        """
        try:
            table = self.query_one(f"#{widget_id}", DataTable)
            if table.row_count > 0:
                table.focus()
                table.move_cursor(row=0)
        except Exception:
            # Table not ready yet, ignore
            pass

    def watch_current_bucket(self, bucket_name: str) -> None:
        """Called when bucket changes"""
        if bucket_name:
            self.current_prefix = ""
            self._update_breadcrumb()
            self._load_dummy_objects()
            self._focus_first_item()

    def watch_current_prefix(self, prefix: str) -> None:
        """Called when prefix changes"""
        self._update_breadcrumb()
        self._load_dummy_objects()

    def watch_objects(self, objects: list[dict]) -> None:
        """Called when objects reactive property changes"""
        self._update_object_table()
        # Focus first item after table is updated
        self._focus_first_item()

    def _update_breadcrumb(self) -> None:
        """Update the breadcrumb navigation"""
        try:
            breadcrumb = self.query_one(Breadcrumb)
            breadcrumb.set_path(self.current_bucket, self.current_prefix)
        except Exception:
            # Breadcrumb not ready yet, ignore
            pass

    def _load_dummy_objects(self) -> None:
        """Load dummy S3 objects for current bucket and prefix"""
        if not self.current_bucket:
            self.objects = []
            return

        objects = []

        # Add parent directory if we're in a subfolder
        if self.current_prefix:
            objects.append({"key": "..", "is_folder": True, "size": "", "modified": "", "type": "dir"})

        # Add dummy data based on current prefix
        objects.extend(self._get_dummy_data_for_prefix())
        self.objects = objects

    def _get_dummy_data_for_prefix(self) -> list[dict]:
        """Get dummy data based on current prefix"""
        if not self.current_prefix:
            return self._get_root_level_data()
        elif self.current_prefix == "images/":
            return self._get_images_data()
        elif self.current_prefix == "uploads/":
            return self._get_uploads_data()
        else:
            return self._get_generic_data()

    def _get_root_level_data(self) -> list[dict]:
        """Get root level dummy data"""
        return [
            {"key": "uploads", "is_folder": True, "size": "", "modified": "2024-01-20", "type": "dir"},
            {"key": "images", "is_folder": True, "size": "", "modified": "2024-01-19", "type": "dir"},
            {"key": "logs", "is_folder": True, "size": "", "modified": "2024-01-18", "type": "dir"},
            {"key": "config.json", "is_folder": False, "size": "2.1K", "modified": "2024-01-20 14:32", "type": "json"},
            {"key": "README.md", "is_folder": False, "size": "4.2K", "modified": "2024-01-19 16:22", "type": "md"},
            {"key": "app.log", "is_folder": False, "size": "892K", "modified": "2024-01-17 15:30", "type": "log"},
        ]

    def _get_images_data(self) -> list[dict]:
        """Get images folder dummy data"""
        return [
            {"key": "avatars", "is_folder": True, "size": "", "modified": "2024-01-20", "type": "dir"},
            {"key": "thumbnails", "is_folder": True, "size": "", "modified": "2024-01-19", "type": "dir"},
            {
                "key": "hero-banner.jpg",
                "is_folder": False,
                "size": "2.1M",
                "modified": "2024-01-20 14:32",
                "type": "jpg",
            },
            {"key": "logo-dark.svg", "is_folder": False, "size": "12K", "modified": "2024-01-20 11:45", "type": "svg"},
            {"key": "logo-light.svg", "is_folder": False, "size": "11K", "modified": "2024-01-20 11:45", "type": "svg"},
            {
                "key": "background.png",
                "is_folder": False,
                "size": "4.7M",
                "modified": "2024-01-19 16:22",
                "type": "png",
            },
        ]

    def _get_uploads_data(self) -> list[dict]:
        """Get uploads folder dummy data"""
        return [
            {"key": "2024", "is_folder": True, "size": "", "modified": "2024-01-20", "type": "dir"},
            {"key": "temp", "is_folder": True, "size": "", "modified": "2024-01-19", "type": "dir"},
            {"key": "document.pdf", "is_folder": False, "size": "1.2M", "modified": "2024-01-18 09:15", "type": "pdf"},
            {
                "key": "spreadsheet.xlsx",
                "is_folder": False,
                "size": "543K",
                "modified": "2024-01-17 15:28",
                "type": "xlsx",
            },
        ]

    def _get_generic_data(self) -> list[dict]:
        """Get generic folder dummy data"""
        return [
            {"key": "file1.txt", "is_folder": False, "size": "1.2K", "modified": "2024-01-15 10:30", "type": "txt"},
            {"key": "file2.txt", "is_folder": False, "size": "856B", "modified": "2024-01-14 09:15", "type": "txt"},
        ]

    def _update_object_table(self) -> None:
        """Update the object table with current objects"""
        table = self.query_one("#object-table", DataTable)
        table.clear(columns=False)

        for i, obj in enumerate(self.objects):
            # Format the name with icon
            name_with_icon = self._format_name_with_icon(obj["key"], obj["is_folder"])

            table.add_row(name_with_icon, obj["type"], obj["modified"], obj["size"], key=str(i))

    def _format_name_with_icon(self, name: str, is_folder: bool) -> str:
        """Format object name with appropriate icon"""
        if is_folder:
            return format_folder_display_text(name)
        else:
            return f"📄 {name}"

    def _get_file_type(self, filename: str) -> str:
        """Get file type from filename extension"""
        if not filename or "." not in filename:
            return ""
        return filename.split(".")[-1].lower()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table"""
        if event.row_key is None:
            return

        row_index = int(event.row_key.value)
        if 0 <= row_index < len(self.objects):
            obj = self.objects[row_index]

            if obj["is_folder"]:
                if obj["key"] == "..":
                    self._navigate_up()
                else:
                    self._navigate_into_folder(obj["key"])
            else:
                # File selected - emit message
                self.post_message(self.ObjectSelected(obj["key"], False))

    def _navigate_up(self) -> None:
        """Navigate to parent directory"""
        if not self.current_prefix:
            return

        # Remove the last part of the prefix
        parts = self.current_prefix.rstrip("/").split("/")
        if len(parts) > 1:
            self.current_prefix = "/".join(parts[:-1]) + "/"
        else:
            self.current_prefix = ""

    def _navigate_into_folder(self, folder_name: str) -> None:
        """Navigate into a folder"""
        self.current_prefix = self.current_prefix + folder_name + "/"

    def set_bucket(self, bucket_name: str) -> None:
        """Set the current bucket and load its objects"""
        self.current_bucket = bucket_name
