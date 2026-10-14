def seconds_to_time(seconds: float) -> str:
    """
    将秒转换为 HH:MM:SS.mmm 格式。
    """

    if seconds is None or seconds < 0:
        seconds = 0.0

    total_milliseconds = round(seconds * 1000)

    hours = total_milliseconds // 3_600_000

    total_milliseconds %= 3_600_000

    minutes = total_milliseconds // 60_000

    total_milliseconds %= 60_000

    secs = total_milliseconds // 1000

    milliseconds = total_milliseconds % 1000

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}."
        f"{milliseconds:03d}"
    )
