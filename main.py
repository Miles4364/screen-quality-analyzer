import sys

from core.video_parser import VideoParser
from exceptions.video_exception import VideoError
from utils.time_util import seconds_to_time


def print_metadata(metadata):

    print()
    print("=" * 50)

    print("智能会议设备投屏质量分析系统")

    print("技术验证版本 V0.1")

    print("=" * 50)

    print()

    print(
        f"文件名称："
        f"{metadata.filename}"
    )

    print(
        f"文件路径："
        f"{metadata.filepath}"
    )

    print(
        f"文件大小："
        f"{metadata.file_size_mb:.2f} MB"
    )

    print()

    print(
        f"视频时长："
        f"{seconds_to_time(metadata.duration)}"
    )

    print(
        f"视频分辨率："
        f"{metadata.width} × {metadata.height}"
    )

    print(
        f"平均帧率："
        f"{metadata.fps:.2f} FPS"
    )

    print(
        f"总帧数："
        f"{metadata.frame_count}"
    )

    print()

    print(
        f"视频编码："
        f"{metadata.codec}"
    )

    print(
        f"视频码率："
        f"{metadata.bitrate_mbps:.2f} Mbps"
    )

    print()

    if metadata.audio_codec:

        print(
            f"音频编码："
            f"{metadata.audio_codec}"
        )

    else:

        print(
            "音频编码：无音频流"
        )

    if metadata.sample_rate:

        print(
            f"采样率："
            f"{metadata.sample_rate} Hz"
        )

    print()

    print("=" * 50)


def main():

    if len(sys.argv) < 2:

        print(
            "用法："
            "python main.py <video_path>"
        )

        return 2

    filepath = sys.argv[1]

    parser = VideoParser()

    try:
        metadata = parser.parse(filepath)

        print_metadata(metadata)
        return 0

    except VideoError as exc:

        print(
            f"视频解析失败：{exc}"
        )

        return 1

    except Exception as exc:

        print(
            f"程序发生未知错误：{exc}"
        )


        return 1

if __name__ == "__main__":
    sys.exit(main())
