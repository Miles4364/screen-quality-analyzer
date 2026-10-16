from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest
from core.video_reader import VideoReader, VideoReadError


def capture(monkeypatch, count=2, fps=10):
    cap = MagicMock()
    cap.get.side_effect = lambda key: fps if key == cv2.CAP_PROP_FPS else count
    cap.read.side_effect = [(True, np.zeros((2, 2, 3), dtype=np.uint8))] * 2 + [(False, None)]
    monkeypatch.setattr(cv2, 'VideoCapture', lambda _: cap)
    return cap


def test_iteration_and_eof(monkeypatch):
    cap = capture(monkeypatch)
    with VideoReader('example') as reader:
        assert reader.read().timestamp == 0
        assert [f.timestamp for f in reader] == [0.1]
        assert list(reader) == []
        assert reader.read() is None
    cap.release.assert_called_once()


@pytest.mark.parametrize('fps', [0, -1, float('nan'), float('inf')])
def test_bad_fps(monkeypatch, fps):
    cap = capture(monkeypatch, fps=fps)
    with pytest.raises(VideoReadError):
        VideoReader('example').open()
    cap.release.assert_called_once()


def test_truncated(monkeypatch):
    cap = capture(monkeypatch, count=3)
    with pytest.raises(VideoReadError, match='提前结束'):
        list(VideoReader('example'))
    cap.release.assert_called_once()


def test_context_releases_on_error(monkeypatch):
    cap = capture(monkeypatch)
    with pytest.raises(RuntimeError):
        with VideoReader('example'):
            raise RuntimeError()
    cap.release.assert_called_once()


def test_not_open():
    with pytest.raises(VideoReadError):
        VideoReader('example').read()


@pytest.mark.parametrize('verified,success', [(5637,True),(5639,False),(5600,False)])
def test_tail_count_requires_independent_agreement(monkeypatch,verified,success):
    cap = capture(monkeypatch,count=5639,fps=24)
    cap.read.side_effect = [(False,None)]
    monkeypatch.setattr('core.video_reader.count_decoded_frames',lambda *args:verified)
    reader = VideoReader('test')
    reader.open()
    reader.current_index = 5637
    if success:
        assert reader.read() is None
        assert reader.read() is None
    else:
        with pytest.raises(VideoReadError):reader.read()
    cap.release.assert_called_once()


def test_large_deficit_does_not_use_verification(monkeypatch):
    cap = capture(monkeypatch,count=5639,fps=24)
    cap.read.side_effect = [(False,None)]
    def unexpected(*args):raise AssertionError('明显截断不应放行')
    monkeypatch.setattr('core.video_reader.count_decoded_frames',unexpected)
    reader=VideoReader('test');reader.open();reader.current_index=5500
    with pytest.raises(VideoReadError):reader.read()
