"""CLI 和 GUI 共用的流式分析入口；回调在调用者线程执行。"""
from time import perf_counter
from core.models import AnalysisConfig, AnalysisResult
from core.video_parser import VideoParser
from core.video_reader import VideoReader
from core.black_detector import BlackDetector
from core.freeze_detector import FreezeDetector
from exceptions.video_exception import AnalysisCancelled


class AnalysisEngine:
    def __init__(self, config=None):
        self.config = config or AnalysisConfig()

    def analyze(self, video_path, *, on_metadata=None, on_progress=None,
                should_cancel=None, on_status=None):
        """分析 CFR 视频。

        on_progress(processed, total) 至多每 100ms 调用一次，另含起点与终点。
        total=0 表示帧数未知。回调不能直接操作其他线程的 GUI 控件。
        取消协作式执行：在 FFprobe/单帧解码返回后检查，不返回部分结果。
        """
        def check_cancel():
            if should_cancel is not None and should_cancel():
                raise AnalysisCancelled('分析已取消')

        started = perf_counter()
        check_cancel()
        c = self.config
        black = BlackDetector(c.black_threshold, c.black_duration)
        freeze = FreezeDetector(c.freeze_pixel_threshold, c.freeze_change_ratio, c.freeze_duration)
        metadata = VideoParser().parse(video_path)
        check_cancel()
        if on_metadata:
            on_metadata(metadata)
        with VideoReader(metadata.filepath) as reader:
            reader.should_cancel = should_cancel
            reader.on_verify = on_status
            total = reader.frame_count
            if on_progress:
                on_progress(0, total)
            last_update = perf_counter()
            while True:
                check_cancel()
                frame = reader.read()
                check_cancel()
                if frame is None:
                    break
                is_black = black.process(frame)
                freeze.process(frame, excluded=is_black)
                now = perf_counter()
                if on_progress and now - last_update >= 0.1:
                    on_progress(reader.current_index, total)
                    last_update = now
            end = reader.current_index / reader.fps
            issues = black.finish(end) + freeze.finish(end)
            count = reader.current_index
        check_cancel()
        issues.sort(key=lambda issue: (issue.start_time, issue.issue_type))
        if on_progress:
            on_progress(count, total)
        check_cancel()
        return AnalysisResult(metadata, issues, perf_counter() - started, count, end)
