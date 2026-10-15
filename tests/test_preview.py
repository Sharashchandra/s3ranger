"""Run with: python -m unittest discover -s tests."""

import asyncio
import io
import threading
import unittest
from unittest.mock import Mock, patch

from textual.app import App
from textual.widgets import Input, ListView, Static, TextArea

from s3ranger.gateways.s3 import PREVIEW_LIMIT, S3
from s3ranger.ui.modals.preview_modal import PreviewModal, preview_text
from s3ranger.ui.widgets.object_list import ObjectList
from helpers import LONG_PREVIEW_KEY


class PreviewTests(unittest.TestCase):
    def test_bounded_read_and_body_cleanup(self):
        for size, data, rejected in [
            (0, b"", False),
            (3, b"abc", False),
            (PREVIEW_LIMIT - 1, b"a" * (PREVIEW_LIMIT - 1), False),
            (PREVIEW_LIMIT, b"", True),
            (PREVIEW_LIMIT + 1, b"", True),
            (1, b"a" * PREVIEW_LIMIT, True),
        ]:
            with self.subTest(size=size, actual=len(data)):
                body = Mock(wraps=io.BytesIO(data))
                client = Mock()
                client.get_object.return_value = {"ContentLength": size, "Body": body}
                if rejected:
                    with self.assertRaises(ValueError):
                        S3.read_preview(
                            client=client, bucket_name="bucket", key="dir/file?#"
                        )
                else:
                    self.assertEqual(
                        S3.read_preview(
                            client=client, bucket_name="bucket", key="dir/file?#"
                        ),
                        data,
                    )
                client.get_object.assert_called_once_with(
                    Bucket="bucket", Key="dir/file?#"
                )
                body.close.assert_called_once()
                if size >= PREVIEW_LIMIT:
                    body.read.assert_not_called()
                else:
                    body.read.assert_called_once_with(PREVIEW_LIMIT)
        body = Mock()
        body.read.side_effect = OSError("read failed")
        client.get_object.return_value = {"ContentLength": 1, "Body": body}
        with self.assertRaises(OSError):
            S3.read_preview(client=client, bucket_name="bucket", key="file")
        body.close.assert_called_once()

    def test_text_and_binary(self):
        self.assertEqual(
            preview_text(b"\xef\xbb\xbfhello\r\nworld"), ("hello\nworld", "Text")
        )
        self.assertEqual(preview_text("hello ☃".encode("utf-16")), ("hello ☃", "Text"))
        for data in (b"\x00hello", b"\xff", b"\x1b[31m"):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "only for text files"):
                preview_text(data)
        self.assertEqual(preview_text(b""), ("", "Text"))


class PreviewUITests(unittest.IsolatedAsyncioTestCase):
    async def test_long_key_and_errors_keep_preview_usable(self):
        self.assertEqual(len(LONG_PREVIEW_KEY.encode()), 1024)
        content = b"first needle\n" + b"line\n" * 50 + b"last NEEDLE\n"
        for size in ((80, 24), (120, 40), (160, 50)):
            for failure in (False, True):
                with self.subTest(size=size, failure=failure), patch.object(
                    S3,
                    "read_preview",
                    return_value=content,
                    side_effect=(
                        OSError("Access denied: " + LONG_PREVIEW_KEY) if failure else None
                    ),
                ) as read:
                    app = App()
                    async with app.run_test(size=size) as pilot:
                        modal = PreviewModal("bucket", LONG_PREVIEW_KEY)
                        app.push_screen(modal)
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        area = modal.query_one(TextArea)
                        dialog = modal.query_one("#preview-dialog")
                        self.assertGreaterEqual(
                            area.scrollable_content_region.height, 3
                        )
                        self.assertEqual(
                            modal.query_one("#preview-title").region.height, 1
                        )
                        self.assertLessEqual(
                            modal.query_one("#preview-status").region.height, 3
                        )
                        for widget in (
                            area, modal.query_one(Input), modal.query_one("#preview-help")
                        ):
                            self.assertTrue(dialog.region.contains_region(widget.region))
                        read.assert_called_once_with(
                            bucket_name="bucket", key=LONG_PREVIEW_KEY
                        )
                        if failure:
                            self.assertTrue(modal.query_one(Input).disabled)
                            await pilot.press("ctrl+f")
                            self.assertTrue(area.has_focus)
                        else:
                            self.assertEqual(area.text, content.decode())
                            await pilot.press("ctrl+f", *"needle", "enter")
                            self.assertEqual(area.selected_text, "needle")
                        await pilot.press("escape")
                        self.assertIsNot(app.screen, modal)

    async def test_preview_flow(self):
        class Browser(App):
            def compose(self):
                yield ObjectList()

        content = (
            "First needle\r\n"
            + "long line " * 30
            + "\r\n"
            + "line\r\n" * 80
            + "last NEEDLE"
        )
        with (
            patch.object(ObjectList, "_load_bucket_objects"),
            patch.object(S3, "read_preview", return_value=content.encode()) as read,
        ):
            app = Browser()
            async with app.run_test(size=(100, 30)) as pilot:
                objects = app.query_one(ObjectList)
                objects.current_bucket = "bucket"
                objects.current_prefix = "dir/"
                objects.objects = [
                    {"key": "folder", "is_folder": True},
                    {"key": "file?#.txt", "is_folder": False, "size_bytes": 500},
                    {"key": "big.txt", "is_folder": False, "size_bytes": PREVIEW_LIMIT},
                ]
                objects.is_loading = False
                await pilot.pause()
                listing = objects.query_one(ListView)
                listing.index = 1
                listing.focus()
                await pilot.press("p")
                self.assertNotIsInstance(app.screen, PreviewModal)
                read.assert_not_called()
                await pilot.press("space")
                listing.index = 0
                await pilot.press("p")
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertIsInstance(app.screen, PreviewModal)
                read.assert_called_once_with(bucket_name="bucket", key="dir/file?#.txt")
                area = app.screen.query_one(TextArea)
                self.assertTrue(area.has_focus)
                for key in ("enter", "f3", "shift+f3"):
                    await pilot.press(key)
                    self.assertTrue(area.has_focus)
                    self.assertIsNone(app.screen.match)
                await pilot.press("ctrl+f", "enter")
                self.assertTrue(app.screen.query_one(Input).has_focus)
                await pilot.press("escape")
                self.assertTrue(area.has_focus)
                await pilot.press("down", "right")
                await pilot.pause()
                self.assertGreater(area.scroll_y, 0)
                self.assertGreater(area.scroll_x, 0)
                await pilot.press("ctrl+f")
                self.assertTrue(app.screen.query_one(Input).has_focus)
                await pilot.press(*"needle", "enter")
                self.assertEqual(area.selected_text, "needle")
                self.assertEqual(area.selection.start, (0, 6))
                await pilot.press("enter")
                self.assertEqual(area.selected_text, "NEEDLE")
                self.assertGreater(area.scroll_y, 50)
                await pilot.press("f3")
                self.assertEqual(area.selection.start, (0, 6))
                await pilot.press("shift+f3")
                self.assertEqual(area.selected_text, "NEEDLE")
                await pilot.press("ctrl+f")
                app.screen.query_one(Input).value = "[missing]"
                await pilot.pause()
                await pilot.press("enter")
                self.assertEqual(
                    str(app.screen.query_one("#preview-status", Static).content),
                    "No matches",
                )
                await pilot.press("ctrl+f", "escape")
                self.assertIsInstance(app.screen, PreviewModal)
                self.assertTrue(area.has_focus)
                await pilot.press("x")
                self.assertEqual(area.text, content.replace("\r\n", "\n"))
                await pilot.press("escape")
                self.assertTrue(listing.has_focus)
                self.assertEqual(listing.index, 0)
                self.assertEqual(objects._selected_keys, {"file?#.txt"})
                self.assertEqual(objects.selected_count, 1)
                self.assertEqual(read.call_count, 1)
                self.assertFalse(
                    ObjectList(folders_only=True).check_action("preview", ())
                )

    async def test_preview_selection_and_file_types(self):
        class Browser(App):
            def compose(self):
                yield ObjectList()

        with (
            patch.object(ObjectList, "_load_bucket_objects"),
            patch.object(S3, "read_preview") as read,
        ):
            app = Browser()
            async with app.run_test() as pilot:
                objects = app.query_one(ObjectList)
                objects.current_bucket = "bucket"
                objects.objects = [
                    {"key": "first.txt", "is_folder": False, "size_bytes": 10},
                    {"key": "second.txt", "is_folder": False, "size_bytes": 10},
                    {"key": "folder", "is_folder": True},
                    {"key": "big.txt", "is_folder": False, "size_bytes": PREVIEW_LIMIT},
                    {"key": "image.png", "is_folder": False, "size_bytes": 10},
                    {"key": "README", "is_folder": False, "size_bytes": 10},
                    {"key": "archive.txt.gz", "is_folder": False, "size_bytes": 10},
                ]
                objects.is_loading = False
                await pilot.pause()
                listing = objects.query_one(ListView)
                listing.index = 0
                listing.focus()
                await pilot.press("space", "down", "space", "p")
                self.assertEqual(objects.selected_count, 2)
                self.assertFalse(objects.check_action("preview", ()))
                self.assertNotIsInstance(app.screen, PreviewModal)
                objects.action_preview()
                objects.action_clear_selection()
                for index in range(2, len(objects.objects)):
                    listing.index = index
                    await pilot.press("space", "p")
                    self.assertNotIsInstance(app.screen, PreviewModal)
                    await pilot.press("space")
                read.assert_not_called()

                listing.index = 0
                await pilot.press("space")
                with patch.object(app, "push_screen") as push:
                    objects.is_loading = True
                    objects.action_preview()
                    objects.is_loading = False
                    objects.current_bucket = ""
                    objects.action_preview()
                    push.assert_not_called()
                    objects.current_bucket = "bucket"
                    objects.is_loading = False
                    objects.selected_count = 1
                    for key in ("notes.TXT", "data.CsV", "script.py", "app.swift"):
                        objects.objects[0]["key"] = key
                        objects._selected_keys = {key}
                        objects.action_preview()
                        self.assertEqual(push.call_args.args[0].key, key)
                    self.assertEqual(push.call_count, 4)
                read.assert_not_called()

    async def test_binary_content_is_rejected(self):
        app = App()
        with patch.object(S3, "read_preview", return_value=b"\x00binary"):
            async with app.run_test() as pilot:
                app.push_screen(PreviewModal("bucket", "disguised.txt"))
                await app.workers.wait_for_complete()
                await pilot.pause()
                self.assertEqual(app.screen.query_one(TextArea).text, "")
                self.assertTrue(app.screen.query_one(Input).disabled)
                self.assertIn(
                    "Preview is available only for text files",
                    str(app.screen.query_one("#preview-status", Static).content),
                )
                await pilot.press("ctrl+f")
                self.assertTrue(app.screen.query_one(TextArea).has_focus)

    async def test_error_and_close_while_loading(self):
        app = App()
        with patch.object(S3, "read_preview", side_effect=OSError("Access denied")):
            async with app.run_test() as pilot:
                app.push_screen(PreviewModal("bucket", "file"))
                await pilot.pause()
                await app.workers.wait_for_complete()
                self.assertIn(
                    "Access denied",
                    str(app.screen.query_one("#preview-status", Static).content),
                )
                await pilot.press("escape")
                self.assertNotIsInstance(app.screen, PreviewModal)

        release = threading.Event()
        started = threading.Event()

        def slow_read(**kwargs):
            started.set()
            release.wait(3)
            return b"late result"

        app = App()
        with patch.object(S3, "read_preview", side_effect=slow_read):
            async with app.run_test() as pilot:
                app.push_screen(PreviewModal("bucket", "file"))
                await asyncio.to_thread(started.wait, 1)
                try:
                    await pilot.press("escape")
                    self.assertNotIsInstance(app.screen, PreviewModal)
                finally:
                    release.set()
                await pilot.pause()


if __name__ == "__main__":
    unittest.main()
