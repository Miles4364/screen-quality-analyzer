import numpy as np

from core.models import VideoFrame


def create_black_frame(
    timestamp,
    index=0,
):

    image = np.zeros(
        (180, 320, 3),
        dtype=np.uint8,
    )

    return VideoFrame(
        index=index,
        timestamp=timestamp,
        image=image,
    )

def create_white_frame(
    timestamp,
    index=0,
):

    image = np.full(
        (180, 320, 3),
        255,
        dtype=np.uint8,
    )

    return VideoFrame(
        index=index,
        timestamp=timestamp,
        image=image,
    )

from core.black_detector import (
    BlackDetector
)


def test_short_black_should_ignore():

    detector = BlackDetector(
        duration_threshold=0.5
    )

    detector.process(
        create_white_frame(0.0)
    )

    detector.process(
        create_black_frame(1.0)
    )

    detector.process(
        create_black_frame(1.2)
    )

    detector.process(
        create_white_frame(1.3)
    )

    issues = detector.finish()

    assert len(issues) == 0

def test_one_second_black():

    detector = BlackDetector(
        duration_threshold=0.5
    )

    detector.process(
        create_white_frame(0.0)
    )

    detector.process(
        create_black_frame(1.0)
    )

    detector.process(
        create_black_frame(1.5)
    )

    detector.process(
        create_black_frame(1.9)
    )

    detector.process(
        create_white_frame(2.0)
    )

    issues = detector.finish()

    assert len(issues) == 1

    issue = issues[0]

    assert issue.issue_type == (
        "BLACK_SCREEN"
    )

    assert abs(
        issue.start_time - 1.0
    ) < 0.001

    assert abs(
        issue.end_time - 2.0
    ) < 0.001

    assert abs(
        issue.duration - 1.0
    ) < 0.001

    assert issue.severity == "MEDIUM"

def test_two_second_black():

    detector = BlackDetector()

    detector.process(
        create_black_frame(1.0)
    )

    detector.process(
        create_black_frame(2.0)
    )

    detector.process(
        create_white_frame(3.0)
    )

    issues = detector.finish()

    assert len(issues) == 1

    issue = issues[0]

    assert issue.duration == 2.0

    assert issue.severity == "HIGH"

def test_black_until_video_end():

    detector = BlackDetector()

    detector.process(
        create_white_frame(0.0)
    )

    detector.process(
        create_black_frame(1.0)
    )

    detector.process(
        create_black_frame(1.5)
    )

    detector.process(
        create_black_frame(2.0)
    )

    issues = detector.finish()

    assert len(issues) == 1

def test_two_black_events():

    detector = BlackDetector()

    detector.process(
        create_black_frame(1.0)
    )

    detector.process(
        create_white_frame(2.0)
    )

    detector.process(
        create_black_frame(3.0)
    )

    detector.process(
        create_white_frame(5.0)
    )

    issues = detector.finish()

    assert len(issues) == 2

def create_gray_frame(
    value,
    timestamp,
):

    image = np.full(
        (180, 320, 3),
        value,
        dtype=np.uint8,
    )

    return VideoFrame(
        index=0,
        timestamp=timestamp,
        image=image,
    )

def test_brightness_threshold():

    detector = BlackDetector(
        brightness_threshold=10
    )

    brightness = (
        detector._calculate_brightness(
            create_gray_frame(
                5,
                0,
            ).image
        )
    )

    assert brightness < 10

import pytest

@pytest.mark.parametrize('duration,severity', [(0.5, 'LOW'), (1, 'MEDIUM'), (2, 'HIGH')])
def test_exact_boundary_and_reset(duration, severity):
    detector = BlackDetector()
    detector.process(create_black_frame(3))
    issues = detector.finish(3 + duration)
    assert issues[0].severity == severity
    assert detector.finish(3 + duration) == issues
    detector.reset()
    assert detector.finish() == []

@pytest.mark.parametrize('kwargs', [{'brightness_threshold': -1}, {'duration_threshold': 0}, {'duration_threshold': float('nan')}])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        BlackDetector(**kwargs)
