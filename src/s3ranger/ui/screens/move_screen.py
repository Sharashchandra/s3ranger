"""Move/Copy screen for selecting destination in S3Ranger."""

import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Label, ListView

from s3ranger.gateways.s3 import S3
from s3ranger.ui.widgets.bucket_list import BucketList
from s3ranger.ui.widgets.object_list import ObjectList
from s3ranger.ui.widgets.title_bar import TitleBar


class MoveScreen(Screen[bool]):
    """Screen for selecting destination when moving or copying files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+enter", "confirm", "Confirm"),
        Binding("tab", "switch_panel", "Switch Panel"),
        Binding("ctrl+r", "refresh", "Refresh"),
    ]

    # Reactive properties
    is_processing: bool = reactive(False)

    def __init__(
        self,
        source_bucket: str,
        source_prefix: str,
        selected_objects: list[dict],
        is_move: bool = True,
    ) -> None:
        """Initialize the move/copy screen.

        Args:
            source_bucket: Source bucket name
            source_prefix: Source prefix (folder path)
            selected_objects: List of selected objects to move/copy
            is_move: True for move (delete source), False for copy (keep source)
        """
        super().__init__()
        self.source_bucket = source_bucket
        self.source_prefix = source_prefix
        self.selected_objects = selected_objects
        self.is_move = is_move
        self.destination_bucket = ""
        self.destination_prefix = ""

    def compose(self) -> ComposeResult:
        """Create the layout for the move screen."""
        with Container(id="move-screen-container"):
            yield TitleBar(id="title-bar")

            # Header banner showing source info and operation type
            with Container(id="move-header-banner"):
                operation = "Moving" if self.is_move else "Copying"
                file_count = len(self.selected_objects)
                file_word = "file" if file_count == 1 else "files"

                # Build file list preview
                file_names = [obj["key"] for obj in self.selected_objects[:3]]
                if file_count > 3:
                    file_preview = ", ".join(file_names) + f", ... (+{file_count - 3} more)"
                else:
                    file_preview = ", ".join(file_names)

                yield Label(
                    f"📁 {operation} {file_count} {file_word} from s3://{self.source_bucket}/{self.source_prefix}",
                    id="move-operation-label",
                )
                yield Label(f"   • {file_preview}", id="move-files-preview")

                if self.is_move:
                    yield Label(
                        "⚠️  Files will be deleted from source after move",
                        id="move-warning-label",
                    )
                else:
                    yield Label(
                        "✓ Original files will remain in source location",
                        id="copy-info-label",
                    )

                yield Label(
                    "Press Ctrl+Enter to move/copy here, Esc to cancel",
                    id="move-instruction-label",
                )

            # Main content area with bucket list and object list (folders only)
            with Container(id="content-container"):
                yield BucketList(id="bucket-list")
                yield ObjectList(id="object-list", folders_only=True)

            # Footer with key bindings
            yield Footer(id="main-footer")

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Set initial focus to bucket list
        bucket_list = self.query_one("#bucket-list", BucketList)
        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            bucket_list_view.focus()
        except Exception:
            bucket_list.focus()

    def on_bucket_list_bucket_selected(self, message: BucketList.BucketSelected) -> None:
        """Handle bucket selection from BucketList widget."""
        self.destination_bucket = message.bucket_name
        object_list = self.query_one("#object-list", ObjectList)
        object_list.set_bucket(message.bucket_name)

    def watch_is_processing(self, is_processing: bool) -> None:
        """React to processing state changes."""
        if is_processing:
            # Show progress modal
            from s3ranger.ui.modals.progress_modal import ProgressModal
            operation = "Moving" if self.is_move else "Copying"
            file_count = len(self.selected_objects)
            file_word = "file" if file_count == 1 else "files"
            message = f"{operation} {file_count} {file_word}..."

            # Store the modal reference so we can dismiss it later
            self._progress_modal = ProgressModal(message)
            self.app.push_screen(self._progress_modal)
        else:
            # Hide progress modal
            if hasattr(self, '_progress_modal') and self._progress_modal:
                try:
                    self.app.pop_screen()
                except Exception:
                    pass
                self._progress_modal = None

    def action_switch_panel(self) -> None:
        """Switch focus between bucket list and object list."""
        bucket_list = self.query_one("#bucket-list", BucketList)
        object_list = self.query_one("#object-list", ObjectList)

        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            object_list_view = object_list.query_one("#object-list", ListView)

            if bucket_list_view.has_focus:
                object_list_view.focus()
            else:
                bucket_list_view.focus()
        except Exception:
            if bucket_list.has_focus:
                object_list.focus()
            else:
                bucket_list.focus()

    def action_refresh(self) -> None:
        """Refresh the current view."""
        bucket_list = self.query_one("#bucket-list", BucketList)
        object_list = self.query_one("#object-list", ObjectList)

        focused_widget = None
        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            object_list_view = object_list.query_one("#object-list", ListView)

            if bucket_list_view.has_focus:
                focused_widget = "bucket_list"
            elif object_list_view.has_focus:
                focused_widget = "object_list"
        except Exception:
            if bucket_list.has_focus:
                focused_widget = "bucket_list"
            elif object_list.has_focus:
                focused_widget = "object_list"

        # Refresh the appropriate widget
        if focused_widget == "object_list":
            object_list.refresh_objects()
        else:
            bucket_list.load_buckets()

    def action_cancel(self) -> None:
        """Cancel the move/copy operation."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Confirm and execute the move/copy operation."""
        # Get current destination from object list
        object_list = self.query_one("#object-list", ObjectList)

        # If object list has a bucket set, use that as destination
        if object_list.current_bucket:
            self.destination_bucket = object_list.current_bucket
            self.destination_prefix = object_list.current_prefix
        # Otherwise, check if a bucket is selected (for empty buckets)
        elif self.destination_bucket:
            # destination_bucket was set when we selected a bucket
            # destination_prefix remains empty (root of bucket)
            pass
        else:
            self.notify("Please select a destination bucket", severity="error")
            return

        # Validate destination
        if not self.destination_bucket:
            self.notify("Please select a destination bucket", severity="error")
            return

        # Check if source and destination are the same
        if (
            self.source_bucket == self.destination_bucket
            and self.source_prefix == self.destination_prefix
        ):
            self.notify("Source and destination are the same", severity="error")
            return

        # Start processing
        self.is_processing = True

        # Execute move/copy in background thread
        thread = threading.Thread(target=self._execute_operation, daemon=True)
        thread.start()

    def _execute_operation(self) -> None:
        """Execute the move or copy operation in background thread."""
        try:
            operation_name = "move" if self.is_move else "copy"

            # Map operation type and object type to the appropriate S3 method
            operations = {
                (True, True): S3.move_directory,    # move folder
                (True, False): S3.move_file,        # move file
                (False, True): S3.copy_directory,   # copy folder
                (False, False): S3.copy_file,       # copy file
            }

            for obj in self.selected_objects:
                source_key = f"{self.source_prefix}{obj['key']}"
                dest_key = f"{self.destination_prefix}{obj['key']}"
                is_folder = obj.get("is_folder", False)

                # Get the appropriate operation function
                operation_func = operations[(self.is_move, is_folder)]

                # Call with appropriate parameters based on whether it's a file or folder
                if is_folder:
                    operation_func(
                        source_s3_bucket=self.source_bucket,
                        source_s3_prefix=source_key,
                        destination_s3_bucket=self.destination_bucket,
                        destination_s3_prefix=dest_key,
                    )
                else:
                    operation_func(
                        source_s3_bucket=self.source_bucket,
                        source_s3_key=source_key,
                        destination_s3_bucket=self.destination_bucket,
                        destination_s3_key=dest_key,
                    )

            # Success
            file_count = len(self.selected_objects)
            file_word = "file" if file_count == 1 else "files"
            message = f"{operation_name.capitalize()}d {file_count} {file_word} to s3://{self.destination_bucket}/{self.destination_prefix}"
            self.app.call_later(lambda: self._on_success(message))

        except Exception as e:
            # Error
            self.app.call_later(lambda: self._on_error(e))

    def _on_success(self, message: str) -> None:
        """Handle successful operation."""
        self.is_processing = False
        self.notify(message, severity="information")
        self.dismiss(True)

    def _on_error(self, error: Exception) -> None:
        """Handle operation error."""
        self.is_processing = False
        operation_name = "move" if self.is_move else "copy"
        self.notify(f"{operation_name.capitalize()} failed: {str(error)}", severity="error")
