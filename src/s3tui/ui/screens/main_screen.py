from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, ListView

from s3tui.ui.modals.delete_modal import DeleteModal
from s3tui.ui.modals.download_modal import DownloadModal
from s3tui.ui.modals.upload_modal import UploadModal
from s3tui.ui.widgets.bucket_list import BucketList
from s3tui.ui.widgets.object_list import ObjectList
from s3tui.ui.widgets.title_bar import TitleBar


class MainScreen(Screen):
    """Main screen displaying S3 buckets and objects."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "switch_panel", "Switch Panel"),
        Binding("d", "download", "Download"),
        Binding("u", "upload", "Upload"),
        Binding("delete", "delete_item", "Delete"),
        Binding("r", "refresh", "Refresh"),
        Binding("h", "help", "Help", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Create the layout for the main screen."""
        with Container(id="main-container"):
            yield TitleBar(id="title-bar")
            with Container(id="content-container"):
                yield BucketList(id="bucket-list")
                yield ObjectList(id="object-list")

            # Footer with key bindings - now integrated as part of main container
            yield Footer(id="main-footer", show_command_palette=False)

    def on_mount(self) -> None:
        """Called when the screen is mounted. Set initial focus."""
        # Set initial focus to bucket list
        bucket_list = self.query_one("#bucket-list", BucketList)
        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            bucket_list_view.focus()
        except Exception:
            bucket_list.focus()

    def on_bucket_list_bucket_selected(self, message: BucketList.BucketSelected) -> None:
        """Handle bucket selection from BucketList widget"""
        object_list = self.query_one("#object-list", ObjectList)
        object_list.set_bucket(message.bucket_name)

    def action_switch_panel(self) -> None:
        """Switch focus between bucket list and object list"""
        bucket_list = self.query_one("#bucket-list", BucketList)
        object_list = self.query_one("#object-list", ObjectList)

        # Try to find the focusable components within each widget
        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            object_table = object_list.query_one("#object-table", DataTable)

            # Check which component currently has focus
            if bucket_list_view.has_focus:
                object_table.focus()
            else:
                bucket_list_view.focus()
        except Exception:
            # Fallback to widget-level focus if components not found
            if bucket_list.has_focus:
                object_list.focus()
            else:
                bucket_list.focus()

    def action_download(self) -> None:
        """Download selected items"""
        object_list = self.query_one("#object-list", ObjectList)

        # Get the currently focused object
        s3_uri = object_list.get_s3_uri_for_focused_object()
        focused_obj = object_list.get_focused_object()

        if not s3_uri or not focused_obj:
            self.notify("No object selected for download", severity="error")
            return

        # Determine if it's a folder or file
        is_folder = focused_obj.get("is_folder", False)

        # Show the download modal
        def on_download_result(result: bool) -> None:
            if result:
                # Download was successful, refresh the view if needed
                object_list = self.query_one("#object-list", ObjectList)
                object_list.refresh_objects()

        self.app.push_screen(DownloadModal(s3_uri, is_folder), on_download_result)

    def action_upload(self) -> None:
        """Upload files to current location"""
        object_list = self.query_one("#object-list", ObjectList)

        # Get the current S3 location (bucket + prefix)
        current_location = object_list.get_current_s3_location()

        if not current_location:
            self.notify("No bucket selected for upload", severity="error")
            return

        # Always upload to current location (bucket root or current prefix)
        # This ensures we upload to the current directory, not to a focused folder
        upload_destination = current_location

        # Show the upload modal
        def on_upload_result(result: bool) -> None:
            if result:
                # Upload was successful, refresh the view
                object_list.refresh_objects()

        self.app.push_screen(UploadModal(upload_destination, False), on_upload_result)

    def action_delete_item(self) -> None:
        """Delete selected items"""
        object_list = self.query_one("#object-list", ObjectList)

        # Get the currently focused object
        s3_uri = object_list.get_s3_uri_for_focused_object()
        focused_obj = object_list.get_focused_object()

        if not s3_uri or not focused_obj:
            self.notify("No object selected for deletion", severity="error")
            return

        # Determine if it's a folder or file
        is_folder = focused_obj.get("is_folder", False)

        # Show the delete modal
        def on_delete_result(result: bool) -> None:
            if result:
                # Delete was successful, refresh the view
                object_list = self.query_one("#object-list", ObjectList)
                object_list.refresh_objects()

        self.app.push_screen(DeleteModal(s3_uri, is_folder), on_delete_result)

    def action_refresh(self) -> None:
        """Refresh the current view"""
        # Remember which component currently has focus
        bucket_list = self.query_one("#bucket-list", BucketList)
        object_list = self.query_one("#object-list", ObjectList)

        focused_widget = None
        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            object_table = object_list.query_one("#object-table", DataTable)

            if bucket_list_view.has_focus:
                focused_widget = "bucket_list"
            elif object_table.has_focus:
                focused_widget = "object_list"
        except Exception:
            # Fallback to widget-level focus check
            if bucket_list.has_focus:
                focused_widget = "bucket_list"
            elif object_list.has_focus:
                focused_widget = "object_list"

        # Define callback to restore focus when refresh is complete
        def on_refresh_complete():
            if focused_widget:
                self._restore_focus_after_refresh(focused_widget)
            else:
                # If no specific focus was detected, default to bucket list
                self._restore_focus_after_refresh("bucket_list")

        # Refresh the appropriate widget based on focus
        if focused_widget == "object_list":
            # Refresh the object list
            object_list.refresh_objects(on_complete=on_refresh_complete)
        else:
            # Default to refreshing bucket list
            bucket_list.load_buckets(on_complete=on_refresh_complete)

    def _restore_focus_after_refresh(self, focused_widget: str) -> None:
        """Restore focus to the appropriate widget after refresh"""
        # Add a small delay to ensure the UI has fully updated
        self.call_later(lambda: self._do_focus_restore(focused_widget))

    def _do_focus_restore(self, focused_widget: str) -> None:
        """Actually perform the focus restoration"""
        try:
            bucket_list = self.query_one("#bucket-list", BucketList)
            object_list = self.query_one("#object-list", ObjectList)

            if focused_widget == "bucket_list":
                # Use the dedicated method to restore focus to bucket list
                bucket_list.focus_list_view()
            elif focused_widget == "object_list":
                # Use the dedicated method to restore focus to object table
                object_list.focus_table()
        except Exception:
            # Fallback to widget-level focus
            if focused_widget == "bucket_list":
                bucket_list = self.query_one("#bucket-list", BucketList)
                bucket_list.focus()
            elif focused_widget == "object_list":
                object_list = self.query_one("#object-list", ObjectList)
                object_list.focus()

    def action_help(self) -> None:
        """Show help information"""
        # This could be a modal or a simple notification
        self.notify(
            "Help: Use 'q' to quit, 'd' to download, 'u' to upload, 'delete' to delete items, 'r' to refresh.",
            severity="info",
        )
