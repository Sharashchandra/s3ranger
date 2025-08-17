from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, ListView

from s3ranger.ui.modals.help_modal import HelpModal
from s3ranger.ui.widgets.bucket_list import BucketList
from s3ranger.ui.widgets.object_list import ObjectList
from s3ranger.ui.widgets.title_bar import TitleBar


class MainScreen(Screen):
    """Main screen displaying S3 buckets and objects."""

    BINDINGS = [
        Binding("tab", "switch_panel", "Switch Panel"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+h", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        """Create the layout for the main screen."""
        with Container(id="main-container"):
            yield TitleBar(id="title-bar")
            with Container(id="content-container"):
                yield BucketList(id="bucket-list")
                yield ObjectList(id="object-list")

            # Footer with key bindings - now integrated as part of main container
            yield Footer(id="main-footer")

    def on_mount(self) -> None:
        """Called when the screen is mounted. Set initial focus."""
        # Set initial focus to bucket list
        bucket_list = self.query_one("#bucket-list", BucketList)
        try:
            bucket_list_view = bucket_list.query_one("#bucket-list-view", ListView)
            bucket_list_view.focus()
        except Exception:
            bucket_list.focus()

    def on_bucket_list_bucket_selected(
        self, message: BucketList.BucketSelected
    ) -> None:
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
            object_list_view = object_list.query_one("#object-list", ListView)

            # Check which component currently has focus
            if bucket_list_view.has_focus:
                object_list_view.focus()
            else:
                bucket_list_view.focus()
        except Exception:
            # Fallback to widget-level focus if components not found
            if bucket_list.has_focus:
                object_list.focus()
            else:
                bucket_list.focus()

    def action_refresh(self) -> None:
        """Refresh the current view"""
        # Remember which component currently has focus
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
        elif focused_widget == "bucket_list":
            # Refresh the bucket list
            bucket_list.load_buckets(on_complete=on_refresh_complete)
        else:
            # Default to refreshing bucket list if no focus was detected
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
                # Use the dedicated method to restore focus to object list
                object_list.focus_list()
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
        self.app.push_screen(HelpModal())
