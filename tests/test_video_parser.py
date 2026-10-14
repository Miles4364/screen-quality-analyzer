from core.video_parser import VideoParser


def test_fraction_30():

    result = VideoParser._parse_fraction(
        "30/1"
    )

    assert result == 30.0


def test_fraction_2997():

    result = VideoParser._parse_fraction(
        "30000/1001"
    )

    assert abs(
        result - 29.97002997
    ) < 0.0001


def test_fraction_zero():

    result = VideoParser._parse_fraction(
        "0/0"
    )

    assert result == 0.0


def test_fraction_none():

    result = VideoParser._parse_fraction(
        None
    )

    assert result == 0.0


def test_frame_count():

    result = VideoParser._parse_frame_count(
        {},
        duration=10,
        fps=30,
    )

    assert result == 300
