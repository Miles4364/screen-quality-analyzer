from utils.time_util import seconds_to_time


def test_zero_seconds():
    assert seconds_to_time(0) == "00:00:00.000"


def test_seconds():
    assert seconds_to_time(5.2) == "00:00:05.200"


def test_minutes():
    assert seconds_to_time(65.2) == "00:01:05.200"


def test_hours():
    assert seconds_to_time(3661.123) == "01:01:01.123"


def test_negative_value():
    assert seconds_to_time(-1) == "00:00:00.000"
