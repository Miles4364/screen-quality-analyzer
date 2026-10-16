import json
import subprocess
from time import monotonic

from exceptions.video_exception import VideoProbeError
from utils.runtime import ffprobe_command
from exceptions.video_exception import AnalysisCancelled


def count_decoded_frames(filepath, should_cancel=None, timeout=180):
    """仅在近末尾计数不一致时独立核验；错误、超时和取消不能视为成功。"""
    command = [ffprobe_command(), '-v', 'error', '-select_streams', 'v:0',
               '-count_frames', '-show_entries', 'stream=nb_read_frames', '-of', 'json', filepath]
    process = None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = monotonic() + timeout
        while True:
            if should_cancel and should_cancel():
                raise AnalysisCancelled('帧数核验已取消')
            if monotonic() >= deadline:
                raise VideoProbeError('帧数核验超时，未确认视频完整性')
            try:
                stdout, stderr = process.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                pass
        if should_cancel and should_cancel():
            raise AnalysisCancelled('帧数核验已取消')
        if process.returncode != 0 or stderr.strip():
            raise VideoProbeError('独立解码核验发现错误：' + stderr.decode('utf-8',errors='replace')[:1000])
        streams = json.loads(stdout)['streams']
        count = int(streams[0]['nb_read_frames'])
        if count <= 0:
            raise ValueError('没有可解码帧')
        return count
    except (AnalysisCancelled, VideoProbeError):
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise VideoProbeError(f'帧数核验失败：{exc}') from exc
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()


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
        ffprobe_command(),
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
            "未找到 FFprobe：请设置 SQA_FFPROBE 为完整路径，或将 ffprobe.exe 放入程序旁 tools 文件夹，或安装到 PATH。"
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
