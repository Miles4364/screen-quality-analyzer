"""验证引擎取消与资源释放，不依赖 GUI 或外部解码器。"""
from types import SimpleNamespace
import numpy as np
import pytest
import core.analysis_engine as module
from core.models import VideoFrame
from exceptions.video_exception import AnalysisCancelled


@pytest.fixture
def fake_reader(monkeypatch):
    readers = []
    class Reader:
        def __init__(self, path):
            self.current_index = 0
            self.frame_count = 4
            self.fps = 10
            self.closed = False
            readers.append(self)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.closed = True
        def read(self):
            if self.current_index == 4:
                return None
            frame = VideoFrame(self.current_index, self.current_index / 10,
                               np.full((16, 16, 3), 100, dtype=np.uint8))
            self.current_index += 1
            return frame
    monkeypatch.setattr(module, 'VideoReader', Reader)
    monkeypatch.setattr(module.VideoParser, 'parse', lambda *args: SimpleNamespace(filepath='test'))
    return readers


def test_progress_and_metadata(fake_reader):
    progress, metadata = [], []
    result = module.AnalysisEngine().analyze('test', on_progress=lambda *args: progress.append(args), on_metadata=metadata.append)
    assert progress[0] == (0, 4)
    assert progress[-1] == (4, 4)
    assert len(metadata) == 1
    assert result.processed_frames == 4
    assert fake_reader[0].closed


def test_cancel_before_open(fake_reader):
    with pytest.raises(AnalysisCancelled):
        module.AnalysisEngine().analyze('test', should_cancel=lambda: True)
    assert fake_reader == []


def test_cancel_during_decode_releases_reader(fake_reader):
    with pytest.raises(AnalysisCancelled):
        module.AnalysisEngine().analyze('test', should_cancel=lambda: bool(fake_reader and fake_reader[0].current_index >= 2))
    assert fake_reader[0].closed
    assert fake_reader[0].current_index == 2


def test_callback_error_releases_reader(fake_reader):
    def fail(*args):
        raise RuntimeError('callback failed')
    with pytest.raises(RuntimeError):
        module.AnalysisEngine().analyze('test', on_progress=fail)
    assert fake_reader[0].closed
