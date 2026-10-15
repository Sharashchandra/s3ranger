"""Real keyboard navigation, rendering state and action routing."""

from unittest.mock import Mock

import pytest
from textual.widgets import Input, ListView

from s3ranger.ui.modals.help_modal import HelpModal
from s3ranger.ui.screens.move_screen import MoveScreen
from s3ranger.ui.widgets.breadcrumb import Breadcrumb
from s3ranger.ui.widgets.bucket_list import BucketList, BucketItem
from s3ranger.ui.widgets.object_list import ObjectList, ObjectItem
from s3ranger.ui.widgets.sort_overlay import SortOverlay
from s3ranger.ui.widgets.title_bar import TitleBar
from helpers import app, mock_storage, open_bucket, wait_until, DATE, FILES, FOLDERS


async def test_navigation_selection_sort_filter_refresh(monkeypatch):
    buckets_call, objects_call = mock_storage(monkeypatch)
    application = app()
    async with application.run_test(size=(120, 40)) as pilot:
        objects = await open_bucket(pilot)
        view = objects.query_one(ListView)
        assert objects.get_current_s3_location() == "s3://alpha/"
        await pilot.press("space")
        assert objects.get_selected_s3_uris() == ["s3://alpha/docs/"]
        await pilot.press("space")
        assert not objects.has_selection()
        await pilot.press("ctrl+a")
        assert objects.selected_count == 3
        assert objects.check_action("rename_item", ()) is False
        await pilot.press("escape")
        await pilot.press("ctrl+s")
        assert isinstance(application.screen, SortOverlay)
        await pilot.press("4")
        assert objects.sort_column == 3 and not objects.sort_ascending
        await wait_until(pilot, lambda: view.has_focus)
        await pilot.press("ctrl+s", "4")
        assert objects.sort_ascending
        await wait_until(pilot, lambda: view.has_focus)
        await pilot.press("ctrl+s", "escape")
        assert objects.sort_column == 3
        view.index = next(
            i for i, o in enumerate(objects.objects) if o["key"] == "docs"
        )
        await pilot.press("enter")
        await wait_until(
            pilot, lambda: not objects.is_loading and objects.current_prefix == "docs/"
        )
        assert objects.objects[0]["key"] == ".."
        assert objects.query_one(Breadcrumb).get_path_segments() == [
            ("alpha", ""),
            ("docs", "docs/"),
        ]
        view.index = 0
        view.focus()
        await pilot.press("space")
        assert objects.selected_count == 0
        await pilot.press("enter")
        await wait_until(
            pilot, lambda: not objects.is_loading and objects.current_prefix == ""
        )
        objects._apply_focus()
        await pilot.press("ctrl+r")
        await wait_until(pilot, lambda: not objects.is_loading and view.has_focus)
        await pilot.press("tab")
        buckets = application.screen.query_one(BucketList)
        await wait_until(pilot, lambda: buckets.query_one(ListView).has_focus)
        await pilot.press("ctrl+r")
        await wait_until(pilot, lambda: not buckets.is_loading)
        await pilot.press("ctrl+f")
        filter_input = buckets.query_one(Input)
        assert filter_input.has_focus
        filter_input.value = "BETA"
        await pilot.pause()
        assert [b["name"] for b in buckets._get_filtered_buckets()] == ["beta"]
        await pilot.press("enter")
        assert buckets.query_one(ListView).has_focus
        await pilot.press("escape")
        assert buckets.filter_text == ""
        await pilot.press("ctrl+h")
        assert isinstance(application.screen, HelpModal)
        await pilot.press("escape")
        assert not isinstance(application.screen, HelpModal)
        assert objects_call.call_count >= 4 and buckets_call.call_count >= 2


@pytest.mark.parametrize(
    "key,modal",
    [
        ("u", "UploadModal"),
        ("d", "DownloadModal"),
        ("delete", "DeleteModal"),
        ("ctrl+k", "RenameModal"),
        ("m", "MoveScreen"),
        ("c", "MoveScreen"),
    ],
)
async def test_operation_shortcuts_and_focus_restore(monkeypatch, key, modal):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test(size=(120, 40)) as pilot:
        objects = await open_bucket(pilot)
        view = objects.query_one(ListView)
        view.index = 1
        await pilot.press("space", key)
        assert type(application.screen).__name__ == modal
        await pilot.press("escape")
        await wait_until(pilot, lambda: view.has_focus)
        if key in ("m", "c"):
            assert objects.selected_count == 0


@pytest.mark.parametrize(
    "key,modal", [("d", "MultiDownloadModal"), ("delete", "MultiDeleteModal")]
)
async def test_multi_selection_routes(monkeypatch, key, modal):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        await pilot.press("ctrl+a", key)
        assert type(application.screen).__name__ == modal
        assert len(application.screen.s3_paths) == 3
        await pilot.press("escape")
        await wait_until(pilot, lambda: objects.query_one(ListView).has_focus)


async def test_paginated_lists_deduplicate_and_preserve_selection(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        view = objects.query_one(ListView)
        view.index = 1
        await pilot.press("space")
        objects._on_objects_loaded(
            FILES + [{**FILES[0], "Key": "new.txt"}], FOLDERS, "next", True
        )
        await pilot.pause()
        assert [o["key"] for o in objects.objects] == [
            "docs",
            "notes.txt",
            "photo.bin",
            "new.txt",
        ]
        assert objects.get_selected_s3_uris() == ["s3://alpha/notes.txt"]
        assert view.index == 1
        # Keep auto-pagination gated until explicitly requested.
        objects._is_fetching = True
        objects._load_more_objects()
        objects._is_fetching = False
        objects.has_more_objects = False
        objects._load_more_objects()
        objects.has_more_objects = True
        objects._continuation_token = "next"
        objects._load_more_objects()
        await wait_until(pilot, lambda: not objects._is_fetching)
        buckets = application.screen.query_one(BucketList)
        buckets._on_buckets_loaded(
            [
                {"name": "alpha", "region": "us-east-1"},
                {"name": "gamma", "region": "Unknown"},
            ],
            None,
            True,
        )
        await pilot.pause()
        assert len(buckets._all_loaded_buckets) == 3
        buckets._restore_list_position(100)
        assert buckets.query_one(ListView).index == 2
        objects._on_objects_error(RuntimeError("page failed"), True)
        assert objects.objects
        buckets._on_buckets_error(RuntimeError("page failed"), True)
        assert buckets.buckets
        objects._on_objects_error(RuntimeError("initial failed"))
        assert not objects.objects
        buckets._on_buckets_error(RuntimeError("initial failed"))
        assert not buckets.buckets
        assert application.screen.query_one(TitleBar).connection_error
        buckets.load_buckets()
        await wait_until(pilot, lambda: not buckets.is_loading)
        assert not application.screen.query_one(TitleBar).connection_error


async def test_background_failures_and_filter_pages(monkeypatch):
    bucket_call, object_call = mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        buckets = application.screen.query_one(BucketList)
        buckets._continuation_token = "next"
        buckets.has_more_buckets = True
        buckets.filter_text = "gam"
        bucket_call.return_value = {
            "buckets": [{"Name": "gamma", "CreationDate": DATE}],
            "continuation_token": None,
        }
        buckets._trigger_server_filter()
        await wait_until(pilot, lambda: not buckets._is_fetching)
        assert [b["name"] for b in buckets.buckets] == ["gamma"]
        buckets._on_all_buckets_loaded_for_filter([], "stale")
        assert buckets.buckets[0]["name"] == "gamma"
        buckets._on_filter_fetch_aborted()
        buckets._on_filtered_buckets_error(RuntimeError("filter"))
        buckets.filter_text = ""
        buckets.has_more_buckets = False
        buckets._schedule_server_filter()
        bucket_call.side_effect = RuntimeError("offline")
        object_call.side_effect = RuntimeError("offline")
        buckets.load_buckets()
        objects.refresh_objects()
        await wait_until(
            pilot, lambda: not buckets.is_loading and not objects.is_loading
        )
        assert not buckets.buckets and not objects.objects


async def test_breadcrumb_and_title(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test():
        breadcrumb = application.screen.query_one(Breadcrumb)
        assert breadcrumb.get_path_segments() == []
        breadcrumb.set_path("alpha", "one/two/")
        breadcrumb.set_separator(" > ")
        assert breadcrumb.get_path_segments() == [
            ("alpha", ""),
            ("one", "one/"),
            ("two", "one/two/"),
        ]
        assert "two" in str(breadcrumb.content)
        breadcrumb.clear()
        assert str(breadcrumb.content) == ""
        title = application.screen.query_one(TitleBar)
        title.connection_error = True
        assert "error" in title.query_one("#connected-indicator").classes
        title.connection_error = False
        assert "error" not in title.query_one("#connected-indicator").classes


@pytest.mark.parametrize("column", range(4))
def test_sort_contracts(column):
    objects = ObjectList()
    parent = {"key": "..", "is_folder": True}
    folder = {"key": "folder", "is_folder": True, "modified": "", "type": "dir"}
    a = {"key": "a", "is_folder": False, "size": "1 B", "type": "a", "modified": "2025"}
    z = {
        "key": "Z",
        "is_folder": False,
        "size": "1 MB",
        "type": "z",
        "modified": "2026",
    }
    data = [parent, z, a, folder]
    assert objects._sort_objects(data, column, True) == [parent, folder, a, z]
    assert objects._sort_objects(data, column, False) == [parent, z, a, folder]
    assert objects._sort_objects([], column, True) == []
    assert objects._sort_objects([parent], column, True) == [parent]
    assert objects._sort_objects(data, None, True) == data
    assert objects._sort_objects(data, 99, True) == data
    assert objects._get_size_sort_key({}) == (1, 0)
    assert objects._get_size_sort_key({"size": "invalid"}) == (1, 0)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", 0),
        ("bad", 0),
        ("bad MB", 0),
        ("12", 12),
        ("1 B", 1),
        ("1 KB", 1024),
        ("1 MB", 1024**2),
        ("1 GB", 1024**3),
        ("1 TB", 1024**4),
    ],
)
def test_size_sort_parser(value, expected):
    assert ObjectList()._parse_size_to_bytes(value) == expected


def test_action_availability_and_item_properties():
    objects = ObjectList()
    for key in ("preview", "download", "delete_item", "rename_item", "move", "copy"):
        assert not objects.check_action(key, ())
    objects.selected_count = 2
    for key in ("preview", "upload", "rename_item", "show_sort_overlay"):
        assert not objects.check_action(key, ())
    objects.selected_count = 1
    assert objects.check_action("preview", ())
    destination = ObjectList(folders_only=True)
    for binding in destination.BINDINGS:
        assert destination.check_action(binding.action, ()) is False
    assert destination.check_action("other", ())
    parent = ObjectItem({"key": "..", "is_folder": True})
    assert not parent.can_select and not parent.toggle_selection()
    assert parent.is_folder and parent.object_key == ".."
    item = ObjectItem({"key": "file"})
    assert item.toggle_selection() and item._get_checkbox_display() == "[✓]"
    assert not item.toggle_selection()
    assert ObjectItem({"key": "file"}, False)._get_checkbox_display() == "   "
    assert BucketItem("alpha").bucket_name == "alpha"
    assert ObjectList.ObjectSelected("file", False).object_key == "file"
    assert ObjectList.MultiSelectionChanged(1, {"file"}).selected_count == 1
    assert Breadcrumb.BreadcrumbClicked("one/").target_prefix == "one/"


async def test_pre_mount_helpers_and_empty_actions(monkeypatch):
    """Widget helpers tolerate composition not having happened yet."""
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test():
        objects = ObjectList()
        buckets = BucketList()
        for callback in (
            objects._setup_scroll_monitoring,
            objects._clear_selection,
            objects._update_list_display,
            objects._update_breadcrumb,
            objects._update_header_sort_indicators,
            objects._apply_focus,
            objects._ensure_focus,
            objects.action_toggle_selection,
            objects.action_select_all,
            objects._clear_all_selections,
            objects._check_scroll_for_pagination,
            objects._load_bucket_objects,
            buckets._setup_scroll_monitoring,
            buckets.clear_filter,
            buckets.focus_filter,
            buckets.focus_list_view,
            buckets._focus_first_item,
            buckets._focus_first_item_if_needed,
            buckets._move_to_first_item,
            buckets._update_list_display,
            buckets._check_scroll_for_pagination,
        ):
            callback()
        assert objects.get_focused_object() is None
        assert objects.get_current_s3_location() is None
        assert objects.get_selected_s3_uris() == []
        objects._update_loading_state(True)
        objects._update_loading_more_state(True)
        objects._focus_first_item()
        buckets._update_title(0, 0)
        buckets._populate_list_view([], True)
        buckets._restore_list_position(0)
        buckets._update_loading_state(True)
        buckets._update_loading_more_state(True)
        buckets._update_connection_status(True)
        notify = Mock()
        monkeypatch.setattr(objects, "notify", notify)
        for callback in (
            objects.action_preview,
            objects.action_download,
            objects.action_upload,
            objects.action_delete_item,
            objects.action_rename_item,
            objects.action_move,
            objects.action_copy,
        ):
            callback()
        assert notify.call_count == 7
        objects.selected_count = 2
        objects.action_upload()
        objects.action_rename_item()
        objects.action_show_sort_overlay()
        assert notify.call_count == 10
        objects.objects = [{"key": "..", "is_folder": True}]
        objects._selected_keys.add("..")
        objects.selected_count = 1
        objects.action_move()
        objects._navigate_up()
        assert objects.current_prefix == ""
        assert objects._get_file_extension("") == ""
        assert objects._get_file_extension("README") == ""
        assert objects._get_file_extension("FILE.TXT") == "txt"
        objects._get_size_sort_key({"size": object()})
        data = [{"key": "x"}]
        monkeypatch.setattr(
            objects, "_get_name_sort_key", Mock(side_effect=ValueError("bad metadata"))
        )
        assert objects._sort_objects(data, 0, True) == data

        title = TitleBar()
        title.watch_connection_error(True)
        overlay = SortOverlay(objects)
        overlay._update_headers_with_numbers()


@pytest.mark.parametrize("key", ["d", "delete", "ctrl+k", "u", "m", "c"])
async def test_successful_operation_returns_and_refreshes(monkeypatch, key):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        objects.query_one(ListView).index = 1
        await pilot.press("space", key)
        screen = application.screen
        screen.dismiss(True)
        await wait_until(
            pilot,
            lambda: not objects.is_loading and objects.query_one(ListView).has_focus,
        )
        assert objects.selected_count == 0


async def test_delete_all_in_folder_navigates_up(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        objects = await open_bucket(pilot)
        objects.query_one(ListView).index = 0
        await pilot.press("enter")
        await wait_until(pilot, lambda: not objects.is_loading)
        objects._apply_focus()
        await pilot.press("ctrl+a", "delete")
        application.screen.dismiss(True)
        await wait_until(
            pilot, lambda: not objects.is_loading and objects.current_prefix == ""
        )


async def test_move_screen_navigation_refresh_and_cancel(monkeypatch):
    mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        screen = MoveScreen("alpha", "", [{"key": str(i)} for i in range(5)])
        application.push_screen(screen)
        await pilot.pause()
        objects = await open_bucket(pilot, "beta")
        assert screen.destination_bucket == "beta"
        await pilot.press("tab", "ctrl+r")
        buckets = screen.query_one(BucketList)
        await wait_until(pilot, lambda: not buckets.is_loading)
        await pilot.press("tab")
        objects.query_one(ListView).focus()
        await pilot.press("ctrl+r")
        await wait_until(pilot, lambda: not objects.is_loading)
        await pilot.press("escape")
        assert application.screen is not screen


async def test_bucket_pagination_and_filter_abort(monkeypatch):
    call, _ = mock_storage(monkeypatch)
    application = app()
    async with application.run_test() as pilot:
        buckets = application.screen.query_one(BucketList)
        await wait_until(
            pilot, lambda: not buckets.is_loading and bool(buckets.buckets)
        )
        buckets.has_more_buckets = True
        buckets._is_fetching = True
        buckets._load_more_buckets()
        buckets._is_fetching = False
        buckets._continuation_token = "next"
        buckets._load_more_buckets()
        await wait_until(pilot, lambda: not buckets._is_fetching)
        buckets._load_more_buckets()
        buckets._on_load_complete_callback = Mock()
        callback = buckets._on_load_complete_callback
        buckets._on_buckets_error(RuntimeError("error"), True)
        callback.assert_called_once()
        buckets.has_more_buckets = True
        buckets._continuation_token = "next"
        buckets.filter_text = "a"
        buckets._schedule_server_filter()
        buckets._schedule_server_filter()
        if buckets._filter_debounce_timer:
            buckets._filter_debounce_timer.cancel()
        buckets.filter_text = "changed"
        buckets._fetch_all_remaining_buckets("a")
        await pilot.pause()
        assert not buckets._is_fetching
        call.side_effect = RuntimeError("filter error")
        buckets._fetch_all_remaining_buckets("changed")
        await pilot.pause()
        assert not buckets._is_fetching
        buckets.filter_text = ""
        buckets._schedule_server_filter()
        application.enable_pagination = False
        buckets._check_scroll_for_pagination()
        application.screen.query_one(ObjectList)._check_scroll_for_pagination()
