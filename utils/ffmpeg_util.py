import json
import subprocess

from exceptions.video_exception import VideoProbeError


def probe_video(filepath: str) -> dict:
    """
    使用FFprobe获取视频文件信息。

    Parameters
    ----------
    filepath:
        视频文件路径。

    Returns
    -------
    dict
        FFprobe返回的JSON数据。
    """

    command = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        filepath,
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    except FileNotFoundError as exc:
        raise VideoProbeError(
            "未找到FFprobe，请确认FFmpeg已经正确安装。"
        ) from exc

    except Exception as exc:
        raise VideoProbeError(
            f"执行FFprobe失败：{exc}"
        ) from exc

    if result.returncode != 0:
        message = result.stderr.strip()

        raise VideoProbeError(
            f"FFprobe解析视频失败：{message}"
        )

    try:
        return json.loads(result.stdout)

    except json.JSONDecodeError as exc:
        raise VideoProbeError(
            "FFprobe返回的数据不是有效JSON。"
        ) from exc
