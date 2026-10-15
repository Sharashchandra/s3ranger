"""Reviewed visual baselines using the production app and stylesheet."""

import pytest
from pytest_textual_snapshot import SVGImageExtension
from textual.widgets import Button, Input, LoadingIndicator

from s3ranger.ui.modals.delete_modal import DeleteModal
from s3ranger.ui.modals.download_modal import DownloadModal
from s3ranger.ui.modals.help_modal import HelpModal
from s3ranger.ui.modals.multi_delete_modal import MultiDeleteModal
from s3ranger.ui.modals.multi_download_modal import MultiDownloadModal
from s3ranger.ui.modals.preview_modal import PreviewModal
from s3ranger.ui.modals.progress_modal import ProgressModal
from s3ranger.ui.modals.rename_modal import RenameModal
from s3ranger.ui.modals.upload_modal import UploadModal
from s3ranger.ui.screens.move_screen import MoveScreen
from s3ranger.ui.widgets.progress_widget import ProgressWidget
from helpers import app, mock_storage, open_bucket, LONG_PREVIEW_KEY, OBJECTS, URIS

# The snapshot plugin uses Syrupy's former attribute name; retain SVG filenames
# with the installed Syrupy version's public extension setting.
SVGImageExtension.file_extension = "svg"

SIZES = [(80, 24), (120, 40), (160, 50)]
SCREENS = [
    "main",
    "upload",
    "download",
    "delete",
    "rename",
    "multi-download",
    "multi-delete",
    "help",
    "preview",
    "progress",
    "copy",
    "move",
    "sort",
]


def freeze_animation(application):
    for widget in application.screen.query(ProgressWidget):
        if widget.timer:
            widget.timer.stop()
        widget.progress_position = 0
        widget.update_progress()
    for widget in application.screen.query(LoadingIndicator):
        widget.auto_refresh = None
    for widget in application.screen.query(Input):
        widget.cursor_blink = False


@pytest.mark.parametrize("size", SIZES, ids=lambda size: f"{size[0]}x{size[1]}")
@pytest.mark.parametrize("screen", SCREENS)
def test_screen_snapshots(monkeypatch, snap_compare, screen, size):
    mock_storage(monkeypatch)
    application = app()

    async def prepare(pilot):
        await open_bucket(pilot)
        modal = {
            "upload": lambda: UploadModal("s3://alpha/docs/"),
            "download": lambda: DownloadModal(
                URIS[0], download_directory="/downloads/"
            ),
            "delete": lambda: DeleteModal(URIS[0]),
            "rename": lambda: RenameModal(URIS[0], current_objects=OBJECTS),
            "multi-download": lambda: MultiDownloadModal(URIS, OBJECTS, "/downloads/"),
            "multi-delete": lambda: MultiDeleteModal(URIS, OBJECTS),
            "help": HelpModal,
            "preview": lambda: PreviewModal("alpha", "notes.txt"),
            "progress": lambda: ProgressModal("Copying 2 files…"),
            "copy": lambda: MoveScreen("alpha", "", OBJECTS, False),
            "move": lambda: MoveScreen("alpha", "", OBJECTS, True),
        }
        if screen in modal:
            application.push_screen(modal[screen]())
            await pilot.pause()
            if screen == "preview":
                await application.workers.wait_for_complete()
            if screen in ("copy", "move"):
                await open_bucket(pilot, "beta")
        elif screen == "sort":
            await pilot.press("ctrl+s")
        freeze_animation(application)
        await pilot.pause()
        # A keyboard-reachable button must actually be visible after scrolling.
        for button in application.screen.query(Button):
            if button.display:
                button.focus()
                button.scroll_visible(animate=False)
                await pilot.pause()
                assert application.screen.region.contains_region(button.region), (
                    f"Clipped control: {screen} {size} {button.id}: {button.region}"
                )
        freeze_animation(application)

    assert snap_compare(application, terminal_size=size, run_before=prepare)


def test_long_key_preview_snapshot(monkeypatch, snap_compare):
    mock_storage(monkeypatch)
    application = app()

    async def prepare(pilot):
        await open_bucket(pilot)
        application.push_screen(PreviewModal("alpha", LONG_PREVIEW_KEY))
        await application.workers.wait_for_complete()
        await pilot.pause()
        freeze_animation(application)

    assert snap_compare(application, terminal_size=(80, 24), run_before=prepare)


@pytest.mark.parametrize("theme", ["Github Dark", "Dracula", "Solarized", "Sepia"])
def test_theme_snapshots(monkeypatch, snap_compare, theme):
    mock_storage(monkeypatch)
    application = app()
    application.selected_theme = theme

    async def prepare(pilot):
        await open_bucket(pilot)
        freeze_animation(application)

    assert snap_compare(application, terminal_size=(120, 40), run_before=prepare)


@pytest.mark.parametrize(
    "state", ["empty", "selected", "loading", "validation", "error"]
)
def test_state_snapshots(monkeypatch, snap_compare, state):
    mock_storage(monkeypatch)
    application = app()

    async def prepare(pilot):
        objects = await open_bucket(pilot)
        if state == "empty":
            objects._clear_objects()
        elif state == "selected":
            await pilot.press("ctrl+a")
        elif state == "loading":
            application.push_screen(
                DownloadModal(URIS[0], download_directory="/downloads/")
            )
            await pilot.pause()
            application.screen.is_downloading = True
        elif state == "validation":
            application.push_screen(RenameModal(URIS[0], current_objects=OBJECTS))
            await pilot.pause()
        else:
            objects._on_objects_error(RuntimeError("Access denied"))
        freeze_animation(application)
        await pilot.pause()

    assert snap_compare(application, terminal_size=(120, 40), run_before=prepare)
