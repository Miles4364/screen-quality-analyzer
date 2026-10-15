"""报告后台生成；取消在发布目标文件前生效。"""
from threading import Event
from PySide6.QtCore import QThread, Signal
from reporting.excel_report import export_report, ReportCancelled


class ReportWorker(QThread):
    ready = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, result, path, options, parent=None):
        super().__init__(parent)
        self.result = result
        self.path = path
        self.options = options
        self._cancel = Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            path = export_report(self.result, self.path, should_cancel=self._cancel.is_set, **self.options)
            # 文件一旦发布成功，就报告成功，不将迟到的取消误报为未生成。
            self.ready.emit(str(path))
        except ReportCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
