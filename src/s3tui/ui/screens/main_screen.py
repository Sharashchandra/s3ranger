"""Main screen for the S3TUI application."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from s3tui.ui.constants import WidgetIDs
from s3tui.ui.modals.delete_modal import DeleteModal
from s3tui.ui.modals.download_modal import DownloadModal
from s3tui.ui.modals.upload_modal import UploadModal
from s3tui.ui.utils import build_s3_uri
from s3tui.ui.widgets.bucket_list import BucketList
from s3tui.ui.widgets.object_list import ObjectList
from s3tui.ui.widgets.path_bar import PathBar


class MainScreen(Screen):
    """Main screen displaying S3 buckets and contents."""

    BINDINGS = [
        Binding("u", "upload", "Upload"),
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
        with Container(id=WidgetIDs.MAIN_CONTAINER_ID):
            # Path bar at the top
            yield PathBar(id=WidgetIDs.PATH_BAR_ID)

            with Horizontal(id=WidgetIDs.CONTENT_AREA_ID):
                # Left panel for buckets
                with Vertical(id=WidgetIDs.BUCKET_PANEL_ID):
                    yield Static("Buckets", id=WidgetIDs.BUCKET_HEADER_ID)
                    yield BucketList(id=WidgetIDs.BUCKET_LIST_ID)

                # Right panel for bucket contents
                with Vertical(id=WidgetIDs.CONTENT_PANEL_ID):
                    yield Static("Contents", id=WidgetIDs.CONTENT_HEADER_ID)
                    yield ObjectList(id=WidgetIDs.OBJECT_LIST_ID)

            # Footer with key bindings
            yield Footer()

    # Widget helper methods
    def _get_path_bar(self) -> PathBar:
        """Get the PathBar widget."""
        return self.query_one(f"#{WidgetIDs.PATH_BAR_ID}", PathBar)

    def _get_object_list(self) -> ObjectList:
        """Get the ObjectList widget."""
        return self.query_one(f"#{WidgetIDs.OBJECT_LIST_ID}", ObjectList)

    def _get_bucket_list(self) -> BucketList:
        """Get the BucketList widget."""
        return self.query_one(f"#{WidgetIDs.BUCKET_LIST_ID}", BucketList)

    def _refresh_object_list(self) -> None:
        """Refresh the object list to show updated state."""
        object_list = self._get_object_list()
        object_list.refresh_objects()

    def _determine_upload_destination(self) -> str | None:
        """Determine the upload destination based on current selection."""
        if self.selected_object:
            # If an object/folder is selected, upload to that location
            return self.selected_object
        elif self.selected_bucket:
            # If only a bucket is selected, upload to bucket root
            return build_s3_uri(self.selected_bucket)
        return None

    def get_current_path(self) -> str:
        """Get the current path from the PathBar."""
        path_bar = self._get_path_bar()
        return path_bar.get_path()

    def action_download(self) -> None:
        """Download the currently selected S3 object."""
        if not self.selected_object:
            return

        modal = DownloadModal(self.selected_object)
        self.app.push_screen(modal)

    def action_delete(self) -> None:
        """Delete the currently selected S3 object."""
        if not self.selected_object:
            return

        modal = DeleteModal(self.selected_object)
        self.app.push_screen(modal, self._on_delete_complete)

    def action_upload(self) -> None:
        """Upload a file to the currently selected S3 location."""
        destination = self._determine_upload_destination()
        if not destination:
            return

        modal = UploadModal(destination)
        self.app.push_screen(modal, self._on_upload_complete)

    def action_refresh(self) -> None:
        """Refresh the current view."""
        bucket_list = self._get_bucket_list()
        bucket_list.refresh_buckets()

        # Also refresh object list if a bucket is selected
        if self.selected_bucket:
            self._refresh_object_list()

    def _on_upload_complete(self, uploaded: bool) -> None:
        """Handle the result of the upload operation."""
        if uploaded:
            self._refresh_object_list()

    def _on_delete_complete(self, deleted: bool) -> None:
        """Handle the result of the delete operation."""
        if deleted:
            self._refresh_object_list()

    def on_bucket_list_bucket_selected(self, message: BucketList.BucketSelected) -> None:
        """Handle bucket selection from the bucket list widget."""
        bucket_name = message.bucket_name
        self.selected_bucket = bucket_name

        # Update path using PathBar widget
        path_bar = self._get_path_bar()
        path_bar.navigate_to_bucket(bucket_name)

        # Focus on the object list
        object_list = self._get_object_list()
        object_list.focus()

        # Load bucket contents using the ObjectList widget
        object_list.run_worker(object_list.load_objects_for_bucket(bucket_name))

    def on_object_list_object_selected(self, message: ObjectList.ObjectSelected) -> None:
        """Handle object selection from the object list widget."""
        object_key = message.object_key
        bucket_name = message.bucket_name

        # Store selected object for download functionality
        self.selected_object = build_s3_uri(bucket_name, object_key)

        # Update path to show the selected object
        path_bar = self._get_path_bar()
        path_bar.update_path(self.selected_object)

    def on_object_list_folder_navigated(self, message: ObjectList.FolderNavigated) -> None:
        """Handle folder navigation from the object list widget."""
        folder_path = message.folder_path
        bucket_name = message.bucket_name

        # Update path bar to show the current folder
        path_bar = self._get_path_bar()
        path_bar.navigate_to_folder(bucket_name, folder_path)
