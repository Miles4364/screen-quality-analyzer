"""后台任务只发送信号，不访问界面控件。"""
from threading import Event
from PySide6.QtCore import QThread, Signal
from core.analysis_engine import AnalysisEngine
from exceptions.video_exception import AnalysisCancelled


class AnalysisWorker(QThread):
    metadata_ready = Signal(object)
    progress = Signal(int, int)
    result_ready = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, path, config=None, parent=None):
        super().__init__(parent)
        self.path = path
        self.config = config
        self._cancel = Event()

    def cancel(self):
        # 线程安全事件：不依赖被分析循环占用的线程事件队列。
        self._cancel.set()

    def run(self):
        try:
            result = AnalysisEngine(self.config).analyze(
                self.path, on_metadata=self.metadata_ready.emit,
                on_progress=self.progress.emit, should_cancel=self._cancel.is_set,
            )
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                self.result_ready.emit(result)
        except AnalysisCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)
