import cv2
import numpy as np
import pytest
from core.frame_extractor import FrameExtractor
from core.video_reader import VideoReadError
from tools.generate_samples import generate


def test_real_seek_and_reopen(tmp_path):
    path = generate(tmp_path / '中文 定位.mp4', duration=4, black=((1, 2),), freeze=((2, 3),))
    reader = FrameExtractor(path, 30, 120)
    try:
        for index in [45, 0, 119, 60, 75]:
            frame = reader.read(index)
            assert frame.index == index
            assert frame.timestamp == pytest.approx(index / 30)
            assert frame.image.shape == (360, 640, 3)
        assert np.mean(reader.read(45).image) < 2
        assert np.mean(reader.read(0).image) > 50
        assert np.mean(cv2.absdiff(reader.read(60).image, reader.read(75).image)) < 2
        reader.close()
        assert reader.capture is None
        assert reader.read(0).index == 0
    finally:
        reader.close()


@pytest.mark.parametrize('index', [-1, 120, 1.5])
def test_invalid_index(index):
    reader = FrameExtractor('unused', 30, 120)
    with pytest.raises(ValueError):
        reader.read(index)
    assert reader.capture is None


def test_missing_file(tmp_path):
    reader = FrameExtractor(tmp_path / 'missing.mp4', 30, 120)
    try:
        with pytest.raises(VideoReadError):
            reader.read(0)
    finally:
        reader.close()


@pytest.mark.parametrize('fps,count', [(0, 10), (float('nan'), 10), (30, 0)])
def test_invalid_metadata(fps, count):
    with pytest.raises(ValueError):
        FrameExtractor('unused', fps, count)
