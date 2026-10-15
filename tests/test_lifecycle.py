"""Boundary states: empty lists, pre-mount callbacks, cancellation and refresh."""

from unittest.mock import Mock

import pytest
from textual.events import Key
from textual.widgets import Input, ListView, Static, TextArea

from s3ranger.gateways.s3 import S3, PREVIEW_LIMIT
from s3ranger.ui.modals.delete_modal import DeleteModal
from s3ranger.ui.modals.download_modal import DownloadModal
from s3ranger.ui.modals.multi_delete_modal import MultiDeleteModal
from s3ranger.ui.modals.multi_download_modal import MultiDownloadModal
from s3ranger.ui.modals.preview_modal import PreviewModal
from s3ranger.ui.modals.rename_modal import RenameModal
from s3ranger.ui.modals.upload_modal import UploadModal
from s3ranger.ui.screens.main_screen import MainScreen
from s3ranger.ui.screens.move_screen import MoveScreen
from s3ranger.ui.widgets.bucket_list import BucketList, BucketItem
from s3ranger.ui.widgets.object_list import ObjectList
from s3ranger.ui.widgets.progress_widget import ProgressWidget
from s3ranger.ui.widgets.sort_overlay import SortOverlay
from helpers import app, mock_storage, open_bucket, wait_until, FILES, OBJECTS, URIS


async def test_dialog_callbacks_before_mount(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test():
        cases = [
            (DeleteModal(""), "watch_is_deleting"),
            (DownloadModal(""), "watch_is_downloading"),
            (MultiDeleteModal([], []), "watch_is_deleting"),
            (MultiDownloadModal([], []), "watch_is_downloading"),
            (RenameModal(""), "watch_is_renaming"),
            (UploadModal(""), "watch_is_uploading"),
        ]
        for modal, watcher in cases:
            getattr(modal, watcher)(True)
            getattr(modal, watcher)(False)
            if hasattr(modal, "watch_delete_progress"):
                modal.watch_delete_progress("changed")
                modal.watch_delete_progress("")
            if hasattr(modal, "watch_download_progress"):
                modal.watch_download_progress("changed")
                modal.watch_download_progress("")
        progress = ProgressWidget("starting")
        progress.on_unmount()


async def test_empty_lists_focus_loading_and_action_guards(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        buckets = application.screen.query_one(BucketList)
        view = objects.query_one(ListView)
        view.index = None
        objects.action_toggle_selection()
        assert objects.get_focused_object() is None
        objects._clear_objects()
        objects._ensure_focus()
        assert objects.get_focused_object() is None
        objects._clear_all_selections()
        objects._check_scroll_for_pagination()
        buckets._all_loaded_buckets = []
        buckets.buckets = []
        buckets._update_list_display()
        await pilot.pause()
        buckets._check_scroll_for_pagination()
        buckets._restore_list_position(0)
        buckets.focus_list_view()
        buckets._move_to_first_item()
        assert not buckets.query_one(ListView).children
        # Unrelated input/key events must not trigger bucket filtering or object operations.
        buckets.on_input_changed(Input.Changed(Input(id="unrelated"), "text"))
        buckets.on_list_view_highlighted(
            ListView.Highlighted(buckets.query_one(ListView), None)
        )
        objects.on_list_view_highlighted(ListView.Highlighted(view, None))
        buckets._prevent_next_selection = True
        buckets.on_list_view_selected(
            ListView.Selected(buckets.query_one(ListView), BucketItem("alpha"), 0)
        )
        assert not buckets._prevent_next_selection
        buckets.on_key(Key("x", "x"))
        objects.current_prefix = "one/two/"
        objects._navigate_up()
        await wait_until(pilot, lambda: not objects.is_loading)
        assert objects.current_prefix == "one/"
        objects.current_prefix = ""
        objects._all_loaded_folders = [{"Prefix": ""}]
        objects._all_loaded_files = [{"Key": ""}]
        objects._build_and_set_objects()
        assert objects.objects == []
        objects._all_loaded_files = FILES
        objects._build_and_set_objects()
        await pilot.pause()
        view.index = 0
        objects.is_loading = True
        notify = Mock()
        monkeypatch.setattr(objects, "notify", notify)
        objects._selected_keys = {objects.objects[0]["key"]}
        objects.selected_count = 1
        objects.action_preview()
        objects.is_loading = False
        objects.objects[0]["size_bytes"] = PREVIEW_LIMIT
        objects.action_preview()
        assert notify.call_count == 2
        objects._handle_file_selection("notes.txt")
        # An unusable selected key/bucket must never dispatch a storage operation.
        objects._selected_keys = {"notes.txt"}
        objects.selected_count = 1
        objects.current_bucket = ""
        for callback in (
            objects.action_download,
            objects.action_delete_item,
            objects.action_rename_item,
        ):
            callback()
        assert notify.call_count == 5
        objects.current_bucket = "alpha"
        await wait_until(pilot, lambda: not objects.is_loading)
        objects.objects = [{"key": "..", "is_folder": True}]
        objects._selected_keys = {".."}
        objects.action_rename_item()
        assert notify.call_count == 6
        view.display = False
        objects._ensure_focus()


async def test_refresh_focus_variants_and_destination_empty_bucket(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        main = application.screen
        buckets = main.query_one(BucketList)
        await wait_until(pilot, lambda: not buckets.is_loading)
        buckets.query_one(Input).focus()
        main.action_refresh()
        await wait_until(pilot, lambda: not buckets.is_loading)
        main._do_focus_restore("unrecognized")
        main._restore_focus_after_refresh("bucket_list")
        move = MoveScreen("alpha", "", OBJECTS, False)
        application.push_screen(move)
        await pilot.pause()
        buckets = move.query_one(BucketList)
        await wait_until(pilot, lambda: not buckets.is_loading)
        buckets.query_one(Input).focus()
        move.action_refresh()
        await wait_until(pilot, lambda: not buckets.is_loading)
        move.destination_bucket = "empty"
        call = Mock()
        monkeypatch.setattr(S3, "copy_file", call)
        monkeypatch.setattr(S3, "copy_directory", call)
        move.action_confirm()
        await wait_until(pilot, lambda: not move.is_processing)
        assert call.call_count == 2


async def test_progress_bounces_and_preview_search_boundaries(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        modal = DownloadModal(URIS[0])
        application.push_screen(modal)
        await pilot.pause()
        progress = modal.query_one(ProgressWidget)
        progress.timer.stop()
        for position in (-3, 0, 22, 30):
            progress.progress_position = position
            progress.update_progress()
            assert 0 <= progress.progress_position <= 22
        progress.set_text("Second file")
        assert (
            str(progress.query_one(".progress-text", Static).content) == "Second file"
        )
        await pilot.press("escape")
        modal = PreviewModal("alpha", "notes.txt")
        application.push_screen(modal)
        await pilot.pause()
        await application.workers.wait_for_complete()
        await pilot.pause()
        modal.action_find_previous()
        await pilot.pause()
        assert modal.query_one(TextArea).has_focus
        await pilot.press("ctrl+f")
        assert modal.query_one(Input).has_focus
        modal.query_one(Input).value = "needle"
        await pilot.pause()
        modal.action_find_previous()
        assert modal.match is not None
        modal.action_find_previous()
        modal.action_find_previous()
        assert modal.match is not None
        await pilot.press("escape", "escape")


async def test_folder_only_listing_and_sort_ignored_keys(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        objects._on_sort_selected(None)
        overlay = SortOverlay(objects)
        application.push_screen(overlay)
        await pilot.pause()
        await pilot.press("x")
        assert application.screen is overlay
        await pilot.press("escape")
        move = MoveScreen("alpha", "", OBJECTS)
        application.push_screen(move)
        await pilot.pause()
        destination = await open_bucket(pilot, "beta")
        assert all(o["is_folder"] for o in destination.objects)
        assert len(destination.query_one(ListView).children) == 1
        await pilot.press("escape")


async def test_screen_fallbacks_when_lists_are_unavailable(monkeypatch):
    """The documented widget-level focus fallback survives a missing inner list."""
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        await open_bucket(pilot)
        for screen in (application.screen, MoveScreen("alpha", "", OBJECTS)):
            if isinstance(screen, MoveScreen):
                application.push_screen(screen)
                await pilot.pause()
            buckets = screen.query_one(BucketList)
            objects = screen.query_one(ObjectList)
            with monkeypatch.context() as patch:
                patch.setattr(
                    buckets,
                    "query_one",
                    Mock(side_effect=LookupError("inner list unavailable")),
                )
                patch.setattr(
                    objects,
                    "query_one",
                    Mock(side_effect=LookupError("inner list unavailable")),
                )
                patch.setattr(buckets, "focus", Mock())
                patch.setattr(objects, "focus", Mock())
                patch.setattr(
                    buckets,
                    "focus_list_view",
                    Mock(side_effect=LookupError("list gone")),
                )
                patch.setattr(
                    objects, "focus_list", Mock(side_effect=LookupError("list gone"))
                )
                patch.setattr(buckets, "load_buckets", Mock())
                patch.setattr(objects, "refresh_objects", Mock())
                screen.on_mount()
                buckets.focus.assert_called_once()
                patch.setattr(type(buckets), "has_focus", property(lambda self: True))
                screen.action_switch_panel()
                objects.focus.assert_called_once()
                screen.action_refresh()
                buckets.load_buckets.assert_called_once()
                patch.setattr(type(buckets), "has_focus", property(lambda self: False))
                patch.setattr(type(objects), "has_focus", property(lambda self: True))
                screen.action_switch_panel()
                screen.action_refresh()
                objects.refresh_objects.assert_called_once()
                if isinstance(screen, MainScreen):
                    screen._do_focus_restore("bucket_list")
                    screen._do_focus_restore("object_list")
                    screen._do_focus_restore("other")
                patch.setattr(type(objects), "has_focus", property(lambda self: False))
                screen.action_refresh()
            if isinstance(screen, MoveScreen):
                screen.action_cancel()
        await pilot.pause()


@pytest.mark.parametrize(
    "kind", ["upload", "download", "multi", "rename", "delete", "multi-delete"]
)
async def test_unrelated_dialog_events_and_cancel_button(monkeypatch, kind):
    mock_storage(monkeypatch)
    constructors = {
        "upload": lambda: UploadModal(URIS[0]),
        "download": lambda: DownloadModal(URIS[0]),
        "multi": lambda: MultiDownloadModal(URIS, OBJECTS),
        "rename": lambda: RenameModal(URIS[0]),
        "delete": lambda: DeleteModal(URIS[0]),
        "multi-delete": lambda: MultiDeleteModal(URIS, OBJECTS),
    }
    application = app()
    async with application.run_test(size=(120, 40)) as pilot:
        modal = constructors[kind]()
        application.push_screen(modal)
        await pilot.pause()
        from textual.widgets import Button

        modal.on_button_pressed(Button.Pressed(Button("unrelated", id="other")))
        if hasattr(modal, "on_input_changed"):
            modal.on_input_changed(Input.Changed(Input(id="other"), "ignored"))
        assert application.screen is modal
        await pilot.click("#cancel-btn")
        await wait_until(pilot, lambda: application.screen is not modal)


async def test_bucket_and_object_instances_do_not_share_selections(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        await pilot.press("ctrl+a")
        assert objects.has_selection()
        assert ObjectList()._selected_keys == set()
        objects.set_bucket("beta")
        await wait_until(pilot, lambda: not objects.is_loading)
        assert not objects.has_selection()
        assert all(
            not item.is_selected for item in objects.query_one(ListView).children
        )
