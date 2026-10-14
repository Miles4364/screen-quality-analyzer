import os
from pathlib import Path

from core.models import VideoMetadata
from exceptions.video_exception import (
    VideoFileNotFoundError,
    VideoMetadataError,
    VideoStreamNotFoundError,
)
from utils.ffmpeg_util import probe_video


class VideoParser:

    def parse(self, filepath: str) -> VideoMetadata:
        """
        解析视频基础信息。
        """

        path = Path(filepath).resolve()

        if not path.exists():
            raise VideoFileNotFoundError(
                f"视频文件不存在：{filepath}"
            )

        if not path.is_file():
            raise VideoFileNotFoundError(
                f"目标路径不是有效文件：{filepath}"
            )

        probe_data = probe_video(str(path))

        video_stream = self._find_video_stream(probe_data)

        audio_stream = self._find_audio_stream(probe_data)

        format_info = probe_data.get("format", {})

        duration = self._parse_duration(
            video_stream,
            format_info,
        )

        fps = self._parse_fps(video_stream)

        width = self._safe_int(
            video_stream.get("width")
        )

        height = self._safe_int(
            video_stream.get("height")
        )

        codec = (
            video_stream.get("codec_name")
            or "unknown"
        )

        bitrate = self._parse_bitrate(
            video_stream,
            format_info,
        )

        frame_count = self._parse_frame_count(
            video_stream,
            duration,
            fps,
        )

        audio_codec = None
        sample_rate = None

        if audio_stream:
            audio_codec = audio_stream.get(
                "codec_name"
            )

            sample_rate = self._safe_int(
                audio_stream.get("sample_rate")
            )

        if width <= 0 or height <= 0:
            raise VideoMetadataError(
                "无法获取有效的视频分辨率。"
            )

        return VideoMetadata(
            filename=path.name,
            filepath=str(path.resolve()),
            file_size=os.path.getsize(path),
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            codec=codec,
            bitrate=bitrate,
            audio_codec=audio_codec,
            sample_rate=sample_rate,
        )

    @staticmethod
    def _find_video_stream(data: dict) -> dict:
        streams = data.get("streams", [])

        for stream in streams:
            if stream.get("codec_type") == "video":
                return stream

        raise VideoStreamNotFoundError(
            "文件中未检测到有效视频流。"
        )

    @staticmethod
    def _find_audio_stream(data: dict):
        streams = data.get("streams", [])

        for stream in streams:
            if stream.get("codec_type") == "audio":
                return stream

        return None

    @staticmethod
    def _parse_fraction(value) -> float:
        """
        将 30000/1001 形式转换成float。
        """

        if value is None:
            return 0.0

        value = str(value).strip()

        if not value:
            return 0.0

        if "/" not in value:
            try:
                return float(value)

            except ValueError:
                return 0.0

        parts = value.split("/", 1)

        try:
            numerator = float(parts[0])
            denominator = float(parts[1])

        except ValueError:
            return 0.0

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _parse_fps(self, stream: dict) -> float:
        """
        优先使用avg_frame_rate。
        """

        avg_fps = self._parse_fraction(
            stream.get("avg_frame_rate")
        )

        if avg_fps > 0:
            return avg_fps

        real_fps = self._parse_fraction(
            stream.get("r_frame_rate")
        )

        return real_fps

    @staticmethod
    def _parse_duration(
        stream: dict,
        format_info: dict,
    ) -> float:

        values = [
            format_info.get("duration"),
            stream.get("duration"),
        ]

        for value in values:

            if value is None:
                continue

            try:
                duration = float(value)

                if duration > 0:
                    return duration

            except (TypeError, ValueError):
                continue

        return 0.0

    @staticmethod
    def _parse_bitrate(
        stream: dict,
        format_info: dict,
    ) -> int:

        values = [
            stream.get("bit_rate"),
            format_info.get("bit_rate"),
        ]

        for value in values:

            try:
                bitrate = int(value)

                if bitrate > 0:
                    return bitrate

            except (TypeError, ValueError):
                continue

        return 0

    @staticmethod
    def _parse_frame_count(
        stream: dict,
        duration: float,
        fps: float,
    ) -> int:

        raw_count = stream.get("nb_frames")

        try:
            frame_count = int(raw_count)

            if frame_count > 0:
                return frame_count

        except (TypeError, ValueError):
            pass

        if duration > 0 and fps > 0:
            return round(
                duration * fps
            )

        return 0

    @staticmethod
    def _safe_int(value) -> int:

        try:
            return int(value)

        except (TypeError, ValueError):
            return 0
