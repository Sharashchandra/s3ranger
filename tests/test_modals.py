"""Operation dialogs: validation, background completion, retries and pickers."""

import asyncio
import threading
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Input

from s3ranger.gateways.s3 import S3
from s3ranger.ui.modals.delete_modal import DeleteModal
from s3ranger.ui.modals.download_modal import DownloadModal
from s3ranger.ui.modals.multi_delete_modal import MultiDeleteModal
from s3ranger.ui.modals.multi_download_modal import MultiDownloadModal
from s3ranger.ui.modals.rename_modal import RenameModal
from s3ranger.ui.modals.upload_modal import UploadModal
from s3ranger.ui.screens.move_screen import MoveScreen
from s3ranger.ui.widgets.progress_widget import ProgressWidget
from helpers import app, mock_storage, wait_until, OBJECTS, URIS


@pytest.mark.parametrize("kind", ["upload", "download", "delete", "rename"])
@pytest.mark.parametrize("folder", [False, True])
@pytest.mark.parametrize("failure", [False, True])
async def test_single_operation_lifecycle(monkeypatch, tmp_path, kind, folder, failure):
    mock_storage(monkeypatch)
    source = tmp_path / "source"
    source.mkdir() if folder else source.write_text("data")
    uri = "s3://alpha/dir/docs/" if folder else "s3://alpha/dir/notes.txt"
    modal = {
        "upload": lambda: UploadModal(uri),
        "download": lambda: DownloadModal(
            uri, folder, str(tmp_path) + "/", "directory warning"
        ),
        "delete": lambda: DeleteModal(uri, folder),
        "rename": lambda: RenameModal(uri, folder, OBJECTS),
    }[kind]()
    operation = {
        "upload": "upload_directory" if folder else "upload_file",
        "download": "download_directory" if folder else "download_file",
        "delete": "delete_directory" if folder else "delete_file",
        "rename": "move_directory" if folder else "move_file",
    }[kind]
    started, release = threading.Event(), threading.Event()

    def perform(**kw):
        started.set()
        assert release.wait(5), "operation was not released"
        if failure:
            raise RuntimeError("Access denied")

    call = Mock(side_effect=perform)
    monkeypatch.setattr(S3, operation, call)
    application = app()
    results = []
    async with application.run_test(size=(120, 40)) as pilot:
        application.push_screen(modal, results.append)
        await pilot.pause()
        notify = Mock()
        monkeypatch.setattr(modal, "notify", notify)
        if kind == "upload":
            modal.query_one(Input).value = str(source)
        elif kind == "rename":
            modal.query_one(Input).value = "renamed"
        await pilot.pause()
        await pilot.press("ctrl+enter")
        assert await asyncio.to_thread(started.wait, 2)
        try:
            assert getattr(
                modal,
                {
                    "upload": "is_uploading",
                    "download": "is_downloading",
                    "delete": "is_deleting",
                    "rename": "is_renaming",
                }[kind],
            )
            assert modal.query_one(ProgressWidget).display
        finally:
            release.set()
        if failure:
            await wait_until(
                pilot,
                lambda: not getattr(
                    modal,
                    {
                        "upload": "is_uploading",
                        "download": "is_downloading",
                        "delete": "is_deleting",
                        "rename": "is_renaming",
                    }[kind],
                ),
            )
            assert application.screen is modal
            assert any("Access denied" in str(c) for c in notify.call_args_list)
            assert not modal.query_one(ProgressWidget).display
            await pilot.click("#cancel-btn")
            await wait_until(pilot, lambda: application.screen is not modal)
            assert results == [False]
        else:
            await wait_until(pilot, lambda: application.screen is not modal)
            assert results == [True]
        assert call.call_count == 1
        if kind == "rename":
            kw = call.call_args.kwargs
            assert kw["destination_s3_prefix" if folder else "destination_s3_key"] == (
                "dir/renamed/" if folder else "dir/renamed"
            )
        elif kind == "upload":
            assert call.call_args.kwargs["s3_uri"] == uri


@pytest.mark.parametrize("kind", ["download", "delete"])
@pytest.mark.parametrize("outcome", ["success", "partial", "failure"])
async def test_multi_operation_results(monkeypatch, tmp_path, kind, outcome):
    mock_storage(monkeypatch)
    modal = (
        MultiDeleteModal(URIS, OBJECTS)
        if kind == "delete"
        else MultiDownloadModal(URIS, OBJECTS, str(tmp_path / "new"), "warning")
    )
    file_call, folder_call = Mock(), Mock()
    if outcome != "success":
        folder_call.side_effect = RuntimeError("folder failed")
    if outcome == "failure":
        file_call.side_effect = RuntimeError("file failed")
    monkeypatch.setattr(S3, kind + "_file", file_call)
    monkeypatch.setattr(S3, kind + "_directory", folder_call)
    application = app()
    results = []
    async with application.run_test(size=(120, 40)) as pilot:
        application.push_screen(modal, results.append)
        await pilot.pause()
        notify = Mock()
        monkeypatch.setattr(modal, "notify", notify)
        progress_widget = modal.query_one(ProgressWidget)
        await pilot.click("#" + kind + "-btn")
        await wait_until(
            pilot,
            lambda: not getattr(
                modal, "is_deleting" if kind == "delete" else "is_downloading"
            ),
        )
        assert file_call.call_count == folder_call.call_count == 1
        if outcome == "failure":
            assert application.screen is modal
            assert "All 2" in notify.call_args.args[0]
            await pilot.press("escape")
            assert results == [False]
        else:
            await wait_until(pilot, lambda: bool(results))
            assert results == [True]
            assert notify.call_args.kwargs["severity"] == (
                "warning" if outcome == "partial" else "information"
            )
        progress = getattr(
            modal, "delete_progress" if kind == "delete" else "download_progress"
        )
        assert "2/2" in progress
        assert progress_widget.progress_text == progress


async def test_invalid_inputs_prevent_operations(monkeypatch, tmp_path):
    mock_storage(monkeypatch)
    operation = Mock()
    for name in (
        "upload_file",
        "upload_directory",
        "download_file",
        "download_directory",
        "delete_file",
        "delete_directory",
        "move_file",
    ):
        monkeypatch.setattr(S3, name, operation)
    application = app()
    async with application.run_test(size=(120, 40)) as pilot:
        for modal in (
            UploadModal(""),
            DownloadModal(""),
            DeleteModal(""),
            RenameModal(""),
            MultiDeleteModal([], []),
            MultiDownloadModal([], [], str(tmp_path)),
        ):
            application.push_screen(modal)
            await pilot.pause()
            notify = Mock()
            monkeypatch.setattr(modal, "notify", notify)
            for field in modal.query(Input):
                field.value = " "
            await pilot.pause()
            await pilot.press("ctrl+enter")
            assert operation.call_count == 0
            assert notify.called
            for button in modal.query(".primary"):
                assert button.disabled
            if isinstance(modal, UploadModal):
                modal.query_one(Input).value = str(tmp_path / "missing")
                await pilot.pause()
                await pilot.press("ctrl+enter")
                assert "does not exist" in notify.call_args.args[0]
            await pilot.press("escape")
        modal = RenameModal("s3://alpha/notes.txt", current_objects=OBJECTS)
        application.push_screen(modal)
        await pilot.pause()
        assert modal.query_one("#rename-btn", Button).disabled
        modal.query_one(Input).value = "notes.txt"
        modal.action_rename()
        assert operation.call_count == 0
        assert modal._validate_new_name(" ")[0] is False
        assert modal._extract_name_from_s3_path("invalid") == ""
        assert modal._extract_name_from_s3_path("s3://alpha") == ""
        await pilot.press("escape")
        modal = MultiDownloadModal(URIS, OBJECTS, str(tmp_path / "file" / "new"))
        (tmp_path / "file").write_text("not directory")
        application.push_screen(modal)
        await pilot.pause()
        notify = Mock()
        monkeypatch.setattr(modal, "notify", notify)
        await pilot.press("ctrl+enter")
        assert "Failed to create" in notify.call_args.args[0]
        assert not modal.is_downloading
        await pilot.press("escape")


@pytest.mark.parametrize(
    "kind,key",
    [
        ("upload", "ctrl+o"),
        ("upload", "ctrl+l"),
        ("download", "ctrl+o"),
        ("multi", "ctrl+o"),
    ],
)
@pytest.mark.parametrize("selected", [False, True])
async def test_file_picker_roundtrip(monkeypatch, tmp_path, kind, key, selected):
    mock_storage(monkeypatch)
    from textual_fspicker import FileOpen, SelectDirectory

    application = app()
    modal = (
        UploadModal("s3://alpha/")
        if kind == "upload"
        else DownloadModal(URIS[0], download_directory=str(tmp_path))
        if kind == "download"
        else MultiDownloadModal(URIS, OBJECTS, str(tmp_path))
    )
    monkeypatch.setattr(
        "s3ranger.ui.modals.upload_modal.FILE_PICKER_DEFAULT_PATH", str(tmp_path)
    )
    async with application.run_test(size=(120, 40)) as pilot:
        application.push_screen(modal)
        await pilot.pause()
        previous = modal.query_one(Input).value
        await pilot.press(key)
        await wait_until(
            pilot, lambda: isinstance(application.screen, (FileOpen, SelectDirectory))
        )
        path = (
            tmp_path / "selected.txt"
            if key == "ctrl+o" and kind == "upload"
            else tmp_path
        )
        if path != tmp_path:
            path.write_text("selected")
        application.screen.dismiss(path if selected else None)
        await application.workers.wait_for_complete()
        await pilot.pause()
        assert application.screen is modal
        if selected:
            expected = str(path) + ("/" if path.is_dir() else "")
            assert modal.query_one(Input).value == expected
            assert modal.query_one(Input).has_focus
        else:
            assert modal.query_one(Input).value == previous
        await pilot.press("escape")


@pytest.mark.parametrize("move", [False, True])
@pytest.mark.parametrize("failure", [False, True])
async def test_move_screen_operation_and_failure_recovery(monkeypatch, move, failure):
    mock_storage(monkeypatch)
    application = app()
    modal = MoveScreen("alpha", "source/", OBJECTS, move)
    file_call, folder_call = Mock(), Mock()
    if failure:
        file_call.side_effect = RuntimeError("copy failed")
    monkeypatch.setattr(S3, "move_file" if move else "copy_file", file_call)
    monkeypatch.setattr(S3, "move_directory" if move else "copy_directory", folder_call)
    results = []
    async with application.run_test(size=(120, 40)) as pilot:
        application.push_screen(modal, results.append)
        await pilot.pause()
        modal.action_confirm()
        assert not modal.is_processing
        objects = modal.query_one("ObjectList")
        objects.set_bucket("alpha")
        await wait_until(pilot, lambda: not objects.is_loading)
        objects.current_prefix = "source/"
        modal.action_confirm()
        assert not modal.is_processing
        objects.set_bucket("beta")
        await wait_until(pilot, lambda: not objects.is_loading)
        objects.current_prefix = "destination/"
        await pilot.press("ctrl+enter")
        await wait_until(pilot, lambda: not modal.is_processing)
        if failure:
            assert application.screen is modal
            assert results == []
            await pilot.press("escape")
            assert results == [False]
        else:
            await wait_until(pilot, lambda: bool(results))
            assert results == [True]
            file_call.assert_called_once_with(
                source_s3_bucket="alpha",
                source_s3_key="source/notes.txt",
                destination_s3_bucket="beta",
                destination_s3_key="destination/notes.txt",
            )
            folder_call.assert_called_once_with(
                source_s3_bucket="alpha",
                source_s3_prefix="source/docs/",
                destination_s3_bucket="beta",
                destination_s3_prefix="destination/docs/",
            )
