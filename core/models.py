from dataclasses import dataclass
from typing import Optional


@dataclass
class VideoMetadata:
    """
    视频基础信息数据模型。
    """

    filename: str
    filepath: str
    file_size: int

    duration: float

    width: int
    height: int

    fps: float
    frame_count: int

    codec: str
    bitrate: int

    audio_codec: Optional[str] = None
    sample_rate: Optional[int] = None

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def file_size_mb(self) -> float:
        return self.file_size / 1024 / 1024

    @property
    def bitrate_mbps(self) -> float:
        return self.bitrate / 1_000_000

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VideoFrame:
    """
    视频帧。
    """

    index: int
    timestamp: float
    image: Any


@dataclass
class DetectedIssue:
    """
    视频分析检测到的问题。
    """

    issue_type: str

    start_time: float
    end_time: float

    duration: float

    severity: str

    description: str

    extra_data: Optional[dict] = None
