"""Simple progress widget with bouncing progress bar."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static


class ProgressWidget(Widget):
    """A simple widget that shows downloading text and a custom bouncing progress bar."""

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.progress_position = 0
        self.direction = 1
        self.timer = None
        self.progress_text = text

    def compose(self) -> ComposeResult:
        """Compose the progress widget."""
        with Vertical(classes="progress-container"):
            yield Static(self.progress_text, classes="progress-text")
            with Horizontal(classes="progress-bar-container"):
                yield Static("", id="custom-progress-bar", classes="progress-bar")

    def on_mount(self) -> None:
        """Start the bouncing animation when mounted."""
        self.timer = self.set_interval(
            0.05, self.update_progress
        )  # Increased speed (was 0.1)

    def update_progress(self) -> None:
        """Update the bouncing progress bar."""
        progress_bar = self.query_one("#custom-progress-bar", Static)

        # Create a simple bouncing bar using characters
        bar_width = 30  # Width of the progress bar in characters
        position = int(self.progress_position)

        # Create the bar with a moving segment
        bar = [" "] * bar_width
        segment_length = 8

        # Fill in the moving segment
        for i in range(segment_length):
            pos = position + i
            if 0 <= pos < bar_width:
                bar[pos] = "█"

        # Update direction when hitting edges
        if position + segment_length >= bar_width:
            self.direction = -1
        elif position <= 0:
            self.direction = 1

        # Move the position (increased speed)
        self.progress_position += self.direction * 1.0  # Increased from 0.5 to 1.0

        # Keep position in bounds
        if self.progress_position < 0:
            self.progress_position = 0
        elif self.progress_position > bar_width - segment_length:
            self.progress_position = bar_width - segment_length

        # Update the display
        progress_bar.update("".join(bar))

    def on_unmount(self) -> None:
        """Clean up timer when unmounted."""
        if self.timer:
            self.timer.stop()
