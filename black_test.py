import sys

from core.black_detector import (
    BlackDetector
)
from core.video_reader import (
    VideoReader
)
from exceptions.video_exception import (
    VideoError
)
from utils.time_util import (
    seconds_to_time
)


def print_issue(
    index,
    issue,
):

    print()

    print(
        f"#{index:03d}"
    )

    print(
        f"类型："
        f"{issue.issue_type}"
    )

    print(
        f"开始："
        f"{seconds_to_time(issue.start_time)}"
    )

    print(
        f"结束："
        f"{seconds_to_time(issue.end_time)}"
    )

    print(
        f"持续："
        f"{issue.duration:.3f} 秒"
    )

    print(
        f"等级："
        f"{issue.severity}"
    )

    if issue.extra_data:

        brightness = (
            issue.extra_data.get(
                "average_brightness"
            )
        )

        if brightness is not None:

            print(
                f"平均亮度："
                f"{brightness:.2f}"
            )


def main():

    if len(sys.argv) < 2:

        print(
            "用法："
            "python black_test.py "
            "<video_path>"
        )

        return 1

    filepath = sys.argv[1]

    detector = BlackDetector(
        brightness_threshold=10,
        duration_threshold=0.5,
    )

    try:

        with VideoReader(filepath) as reader:
            for frame in reader:
                detector.process(frame)
            issues = detector.finish(reader.current_index / reader.fps)

    except VideoError as exc:

        print(
            f"视频处理失败：{exc}"
        )

        return 1

    print()

    print("=" * 40)

    print("黑屏检测结果")

    print("=" * 40)

    print()

    print(
        f"检测到黑屏："
        f"{len(issues)}"
    )

    for index, issue in enumerate(
        issues,
        start=1,
    ):

        print_issue(
            index,
            issue,
        )


if __name__ == "__main__":
    sys.exit(main())
