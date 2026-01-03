"""Progress modal for showing operation progress in S3Ranger."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen

from s3ranger.ui.widgets.progress_widget import ProgressWidget


class ProgressModal(ModalScreen[bool]):
    """Modal screen displaying a progress indicator."""

    def __init__(self, message: str = "Processing...") -> None:
        """Initialize the progress modal.

        Args:
            message: The message to display
        """
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Container(id="progress-modal-dialog"):
            yield ProgressWidget(text=self.message, id="progress-modal-widget")
