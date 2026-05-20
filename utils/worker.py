"""Background worker for heavy operations (QThread-based)."""
import logging

from PyQt6.QtCore import QThread, pyqtSignal

_logger = logging.getLogger(__name__)


class BackgroundWorker(QThread):
    """Run a callable in a background thread, emit result/error on completion."""

    finished_with_result = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished_with_result.emit(result)
        except Exception as e:
            _logger.exception("Background worker failed")
            self.failed.emit(str(e))
