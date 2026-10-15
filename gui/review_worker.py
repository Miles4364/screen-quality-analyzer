"""复核解码线程：只保留最新定位请求，关闭时释放独立视频句柄。"""
from threading import Condition
from PySide6.QtCore import QThread, Signal
from core.frame_extractor import FrameExtractor


class ReviewWorker(QThread):
    ready = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, path, fps, count, parent=None):
        super().__init__(parent)
        self.extractor = FrameExtractor(path, fps, count)
        self.condition = Condition()
        self.pending = None
        self.stopping = False

    def request(self, token, index):
        with self.condition:
            self.pending = (token, index)
            self.condition.notify()

    def stop(self):
        with self.condition:
            self.stopping = True
            self.pending = None
            self.condition.notify()

    def run(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.stopping or self.pending is not None)
                    if self.stopping:
                        return
                    token, index = self.pending
                    self.pending = None
                try:
                    frame = self.extractor.read(index)
                    self.ready.emit(token, frame)
                except Exception as exc:
                    self.failed.emit(token, str(exc))
        finally:
            self.extractor.close()
