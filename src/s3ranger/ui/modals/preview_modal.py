"""Read-only object preview with literal, case-insensitive search."""

import asyncio
import re

from rich.cells import cell_len
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Static, TextArea
from textual.widgets.text_area import Selection

from s3ranger.gateways.s3 import S3


def preview_text(data: bytes) -> tuple[str, str]:
    """Decode Unicode text, rejecting binary content."""
    try:
        encoding = (
            "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        )
        text = data.decode(encoding)
        if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
            raise ValueError("Binary control characters")
        return text.replace("\r\n", "\n").replace("\r", "\n"), "Text"
    except (UnicodeError, ValueError) as error:
        raise ValueError("Preview is available only for text files") from error


class PreviewModal(ModalScreen[None]):
    DEFAULT_CSS = """
    PreviewModal { align: center middle; background: $background 70%; }
    #preview-dialog {
        width: 90%; height: 90%; border: solid $primary;
        background: $surface; padding: 0 1;
    }
    #preview-title { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }
    #preview-status { height: auto; max-height: 3; overflow-y: auto; }
    #preview-help { height: auto; }
    #preview-content { height: 1fr; min-height: 5; }
    #preview-search { height: 3; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("ctrl+f", "search", "Search", priority=True),
        Binding("f3", "find_next", "Next match", priority=True),
        Binding("enter", "find_next", "Next match", show=False),
        Binding("shift+f3", "find_previous", "Previous match", priority=True),
    ]

    def __init__(self, bucket: str, key: str) -> None:
        super().__init__()
        self.bucket = bucket
        self.key = key
        self.match: tuple[int, int] | None = None

    def compose(self) -> ComposeResult:
        with Container(id="preview-dialog"):
            yield Static(
                f"s3://{self.bucket}/{self.key}", id="preview-title", markup=False
            )
            yield Static("Loading preview…", id="preview-status", markup=False)
            yield TextArea(
                read_only=True,
                show_cursor=False,
                soft_wrap=False,
                show_line_numbers=True,
                id="preview-content",
            )
            yield Input(
                placeholder="Search text (case-insensitive) · Enter: next",
                id="preview-search",
                disabled=True,
            )
            yield Static(
                "Arrows / PgUp / PgDn: scroll · Ctrl+f: search · F3 / Shift+F3: next / previous · Esc: close",
                id="preview-help",
                markup=False,
            )

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()
        self.load_preview()

    @work(exclusive=True)
    async def load_preview(self) -> None:
        try:

            def fetch() -> tuple[str, str]:
                return preview_text(
                    S3.read_preview(bucket_name=self.bucket, key=self.key)
                )

            text, mode = await asyncio.to_thread(fetch)
            self.query_one(TextArea).load_text(text)
            self.query_one("#preview-status", Static).update(
                f"{mode}" + (" · Empty file" if not text else "")
            )
            self.query_one(Input).disabled = False
        except Exception as error:
            self.query_one("#preview-status", Static).update(
                f"Unable to preview: {error}"
            )

    def action_close(self) -> None:
        if self.query_one(Input).has_focus:
            self.query_one(TextArea).focus()
        else:
            self.dismiss(None)

    def action_search(self) -> None:
        self.query_one(Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.match = None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_find_next()

    def action_find_next(self) -> None:
        self.find_match(previous=False)

    def action_find_previous(self) -> None:
        self.find_match(previous=True)

    def find_match(self, *, previous: bool) -> None:
        query = self.query_one(Input).value
        if not query:
            return
        area = self.query_one(TextArea)
        text = area.text
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        if previous:
            end = self.match[0] if self.match else len(text)
            match = None
            for candidate in pattern.finditer(text, 0, end):
                match = candidate
            if match is None:
                for candidate in pattern.finditer(text):
                    match = candidate
        else:
            start = self.match[1] if self.match else 0
            match = pattern.search(text, start) or pattern.search(text)
        status = self.query_one("#preview-status", Static)
        if match is None:
            status.update("No matches")
            return
        self.match = match.span()

        def location(offset: int) -> tuple[int, int]:
            return text.count("\n", 0, offset), offset - text.rfind("\n", 0, offset) - 1

        area.selection = Selection(location(match.start()), location(match.end()))
        row, column = area.selection.start
        prefix = area.document.get_line(row)[:column].expandtabs(area.indent_width)
        area.scroll_to(x=cell_len(prefix), y=row, animate=False)
        area.focus()
        status.update(f"Match on line {area.selection.start[0] + 1} · Search wraps")
