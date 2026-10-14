"""CLI 和后续 GUI 共用的单次流式分析入口。"""
from time import perf_counter
from core.models import AnalysisConfig, AnalysisResult
from core.video_parser import VideoParser
from core.video_reader import VideoReader
from core.black_detector import BlackDetector
from core.freeze_detector import FreezeDetector


class AnalysisEngine:
    def __init__(self, config=None):
        self.config = config or AnalysisConfig()

    def analyze(self, video_path):
        started = perf_counter()
        c = self.config
        black = BlackDetector(c.black_threshold, c.black_duration)
        freeze = FreezeDetector(c.freeze_pixel_threshold, c.freeze_change_ratio, c.freeze_duration)
        metadata = VideoParser().parse(video_path)
        with VideoReader(metadata.filepath) as reader:
            for frame in reader:
                is_black = black.process(frame)
                freeze.process(frame, excluded=is_black)
            # 半开区间：最后一帧也占用 1/fps 秒，不使用可能含较长音轨的容器时长。
            end = reader.current_index / reader.fps
            issues = black.finish(end) + freeze.finish(end)
            count = reader.current_index
        issues.sort(key=lambda issue: (issue.start_time, issue.issue_type))
        return AnalysisResult(metadata, issues, perf_counter() - started, count, end)
