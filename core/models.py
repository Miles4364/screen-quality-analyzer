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

@dataclass(frozen=True)
class AnalysisConfig:
    black_threshold: float = 10.0
    black_duration: float = 0.5
    freeze_pixel_threshold: float = 5.0
    freeze_change_ratio: float = 0.01
    freeze_duration: float = 0.5


@dataclass
class AnalysisResult:
    video_metadata: VideoMetadata
    issues: list[DetectedIssue]
    processing_time: float
    processed_frames: int
    analyzed_duration: float

    @property
    def quality(self):
        from core.quality_score import calculate_quality
        return calculate_quality(self)

    @property
    def warnings(self):
        expected = self.video_metadata.frame_count
        if expected > self.processed_frames:
            return [f'帧数提示：元数据 {expected} 帧，实际解码 {self.processed_frames} 帧；结果按实际帧数统计，请复核视频末尾。']
        return []

    @property
    def statistics(self):
        return {
            'black_count': sum(i.issue_type == 'BLACK_SCREEN' for i in self.issues),
            'freeze_count': sum(i.issue_type == 'FREEZE' for i in self.issues),
            'total_count': len(self.issues),
        }
