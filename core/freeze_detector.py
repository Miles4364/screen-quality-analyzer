"""基于相邻灰度帧变化比例的疑似冻结检测。"""
import math
import cv2
import numpy as np
from core.models import DetectedIssue
from core.black_detector import BlackDetector


class FreezeDetector:
    def __init__(self, pixel_threshold=5, change_ratio_threshold=0.01,
                 duration_threshold=0.5):
        for value, low, high in [(pixel_threshold, 0, 255),
                                 (change_ratio_threshold, 0, 1)]:
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError('冻结阈值超出有效范围')
        if not math.isfinite(duration_threshold) or duration_threshold <= 0:
            raise ValueError('持续时间阈值必须大于 0')
        self.pixel_threshold = pixel_threshold
        self.change_ratio_threshold = change_ratio_threshold
        self.duration_threshold = duration_threshold
        self.reset()

    def reset(self):
        self._previous = None
        self._last_timestamp = None
        self._start = None
        self._ratio_sum = 0.0
        self._ratio_count = 0
        self._issues = []

    def process(self, frame, *, excluded=False):
        # 黑屏（包括短黑闪）切断冻结候选，避免重复告警及跨黑屏合并。
        if excluded:
            self._finish_event(frame.timestamp)
            self._previous = None
            self._last_timestamp = frame.timestamp
            return
        gray = cv2.cvtColor(cv2.resize(frame.image, (320, 180)), cv2.COLOR_BGR2GRAY)
        if self._previous is not None:
            ratio = float(np.mean(cv2.absdiff(gray, self._previous) > self.pixel_threshold))
            if ratio < self.change_ratio_threshold:
                if self._start is None:
                    self._start = self._last_timestamp
                self._ratio_sum += ratio
                self._ratio_count += 1
            else:
                self._finish_event(frame.timestamp)
        self._previous = gray
        self._last_timestamp = frame.timestamp

    def _finish_event(self, end):
        if self._start is not None:
            duration = end - self._start
            if duration + 1e-9 >= self.duration_threshold:
                self._issues.append(DetectedIssue(
                    'FREEZE', self._start, end, duration,
                    BlackDetector._get_severity(duration),
                    f'检测到持续 {duration:.3f} 秒疑似冻结，需人工复核。',
                    {'average_change_ratio': self._ratio_sum / self._ratio_count},
                ))
        self._start = None
        self._ratio_sum = 0.0
        self._ratio_count = 0

    def finish(self, end_time=None):
        if self._last_timestamp is not None:
            self._finish_event(self._last_timestamp if end_time is None else end_time)
        self._previous = None
        return list(self._issues)
