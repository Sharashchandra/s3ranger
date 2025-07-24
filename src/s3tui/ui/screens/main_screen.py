from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer

from s3tui.ui.modals.download_modal import DownloadModal
from s3tui.ui.widgets.bucket_list import BucketList
from s3tui.ui.widgets.object_list import ObjectList
from s3tui.ui.widgets.title_bar import TitleBar


class MainScreen(Screen):
    """Main screen displaying S3 buckets and objects."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("tab", "switch_panel", "Switch Panel"),
        Binding("enter", "open_item", "Open"),
        Binding("space", "select_item", "Select"),
        Binding("d", "download", "Download"),
        Binding("u", "upload", "Upload"),
        Binding("delete", "delete_item", "Delete"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Create the layout for the main screen."""
        with Container(id="main-container"):
            yield TitleBar(id="title-bar")
            with Container(id="content-container"):
                yield BucketList(id="bucket-list")
                yield ObjectList(id="object-list")

            # Footer with key bindings
            yield Footer()

    def on_bucket_list_bucket_selected(self, message: BucketList.BucketSelected) -> None:
        """Handle bucket selection from BucketList widget"""
        object_list = self.query_one("#object-list", ObjectList)
        object_list.set_bucket(message.bucket_name)

    def action_switch_panel(self) -> None:
        """Switch focus between bucket list and object list"""
        bucket_list = self.query_one("#bucket-list", BucketList)
        object_list = self.query_one("#object-list", ObjectList)

        # Toggle focus between panels
        if bucket_list.has_focus:
            object_list.focus()
        else:
            bucket_list.focus()

    def action_open_item(self) -> None:
        """Open the currently focused item"""
        # This will be handled by the individual widgets
        pass

    def action_select_item(self) -> None:
        """Select/multi-select the currently focused item"""
        # This will be handled by the object list widget
        pass

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
                pass

        self.app.push_screen(DownloadModal(s3_uri, is_folder), on_download_result)

    def action_upload(self) -> None:
        """Upload files to current location"""
        self.notify("Upload functionality not yet implemented", severity="error")

    def action_delete_item(self) -> None:
        """Delete selected items"""
        self.notify("Delete functionality not yet implemented", severity="error")

    def action_refresh(self) -> None:
        """Refresh the current view"""
        bucket_list = self.query_one("#bucket-list", BucketList)
        bucket_list.load_buckets()
        self.notify("Refreshed bucket list")
