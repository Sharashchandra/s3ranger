"""Main screen for the S3TUI application."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from s3tui.ui.modals.delete_modal import DeleteModal
from s3tui.ui.modals.download_modal import DownloadModal
from s3tui.ui.widgets.bucket_list import BucketList
from s3tui.ui.widgets.object_list import ObjectList
from s3tui.ui.widgets.path_bar import PathBar


class MainScreen(Screen):
    """Main screen displaying S3 buckets and contents."""

    BINDINGS = [
        Binding("d", "download", "Download"),
        Binding("y", "delete", "Delete"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.selected_bucket = None
        self.selected_object = None

    def compose(self) -> ComposeResult:
        """Create the layout for the main screen."""
        with Container(id="main-container"):
            # Path bar at the top
            yield PathBar(id="path-bar")

            with Horizontal(id="content-area"):
                # Left panel for buckets
                with Vertical(id="bucket-panel"):
                    yield Static("Buckets", id="bucket-header")
                    yield BucketList(id="bucket-list")

                # Right panel for bucket contents
                with Vertical(id="content-panel"):
                    yield Static("Contents", id="content-header")
                    yield ObjectList(id="object-list")

            # Footer with key bindings
            yield Footer()

    def action_download(self) -> None:
        """Download the currently selected S3 object."""
        if self.selected_object:
            # Push the download modal
            modal = DownloadModal(self.selected_object)
            self.app.push_screen(modal)

    def action_delete(self) -> None:
        """Delete the currently selected S3 object."""
        if self.selected_object:
            # Push the delete modal and handle the result
            modal = DeleteModal(self.selected_object)
            self.app.push_screen(modal, self._on_delete_complete)

    def _on_delete_complete(self, deleted: bool) -> None:
        """Handle the result of the delete operation."""
        if deleted:
            # Refresh the object list to show the updated state
            object_list = self.query_one("#object-list", ObjectList)
            object_list.refresh_objects()

    def on_bucket_list_bucket_selected(self, message: BucketList.BucketSelected) -> None:
        """Handle bucket selection from the bucket list widget."""
        bucket_name = message.bucket_name
        self.selected_bucket = bucket_name

        # Update path using PathBar widget
        path_bar = self.query_one("#path-bar", PathBar)
        path_bar.navigate_to_bucket(bucket_name)

        # Focus on the object list
        object_list = self.query_one("#object-list", ObjectList)
        object_list.focus()

        # Load bucket contents using the ObjectList widget
        object_list.run_worker(object_list.load_objects_for_bucket(bucket_name))

    def on_object_list_object_selected(self, message: ObjectList.ObjectSelected) -> None:
        """Handle object selection from the object list widget."""
        object_key = message.object_key
        bucket_name = message.bucket_name

        # Store selected object for download functionality
        self.selected_object = f"s3://{bucket_name}/{object_key}"

        # Update path to show the selected object
        path_bar = self.query_one("#path-bar", PathBar)
        path_bar.update_path(f"s3://{bucket_name}/{object_key}")

    def on_object_list_folder_navigated(self, message: ObjectList.FolderNavigated) -> None:
        """Handle folder navigation from the object list widget."""
        folder_path = message.folder_path
        bucket_name = message.bucket_name

        # Update path bar to show the current folder
        path_bar = self.query_one("#path-bar", PathBar)
        path_bar.navigate_to_folder(bucket_name, folder_path)

    def get_current_path(self) -> str:
        """Get the current path from the PathBar."""
        path_bar = self.query_one("#path-bar", PathBar)
        return path_bar.get_path()

    def action_refresh(self) -> None:
        """Refresh the current view."""
        bucket_list = self.query_one("#bucket-list", BucketList)
        bucket_list.refresh_buckets()

        # Also refresh object list if a bucket is selected
        if self.selected_bucket:
            object_list = self.query_one("#object-list", ObjectList)
            object_list.refresh_objects()
