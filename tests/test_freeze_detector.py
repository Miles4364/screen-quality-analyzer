import pytest
from core.freeze_detector import FreezeDetector
from tests.test_black_detector import create_gray_frame

@pytest.mark.parametrize('duration,count', [(0.2, 0), (0.5, 1), (1, 1), (2, 1), (5, 1)])
def test_duration_and_eof(duration, count):
    d = FreezeDetector()
    d.process(create_gray_frame(100, 3))
    d.process(create_gray_frame(100, 3 + duration / 2))
    result = d.finish(3 + duration)
    assert len(result) == count
    if count:
        assert result[0].start_time == 3
        assert result[0].duration == pytest.approx(duration)
    assert d.finish(3 + duration) == result
    d.reset()
    assert d.finish() == []


def test_motion_and_multiple_events():
    d = FreezeDetector()
    for t, value in enumerate([50, 100, 100, 200, 200, 50]):
        d.process(create_gray_frame(value, t))
    assert [(i.start_time, i.end_time) for i in d.finish()] == [(1, 3), (3, 5)]


def test_black_exclusion():
    d = FreezeDetector()
    for t in range(5):
        d.process(create_gray_frame(0, t), excluded=True)
    assert d.finish(5) == []


def test_unsigned_difference_and_pixel_boundary():
    d = FreezeDetector()
    for t, value in enumerate([250, 10, 250, 10]):
        d.process(create_gray_frame(value, t))
    assert d.finish(4) == []
    d.reset()
    d.process(create_gray_frame(100, 0))
    d.process(create_gray_frame(105, 0.1))
    assert len(d.finish(0.5)) == 1

@pytest.mark.parametrize('kwargs', [{'pixel_threshold': -1}, {'change_ratio_threshold': 2}, {'duration_threshold': 0}, {'pixel_threshold': float('nan')}])
def test_invalid(kwargs):
    with pytest.raises(ValueError):
        FreezeDetector(**kwargs)
