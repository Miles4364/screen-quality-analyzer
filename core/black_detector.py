from typing import List
import math

import cv2
import numpy as np

from core.models import (
    DetectedIssue,
    VideoFrame,
)


class BlackDetector:

    ISSUE_TYPE = "BLACK_SCREEN"

    def __init__(
        self,
        brightness_threshold: float = 10.0,
        duration_threshold: float = 0.5,
        resize_width: int = 320,
        resize_height: int = 180,
    ):

        if not math.isfinite(brightness_threshold) or not 0 <= brightness_threshold <= 255:
            raise ValueError("亮度阈值必须在 0 到 255 之间")
        if not math.isfinite(duration_threshold) or duration_threshold <= 0:
            raise ValueError("持续时间阈值必须大于 0")
        if resize_width <= 0 or resize_height <= 0:
            raise ValueError("分析尺寸必须大于 0")

        self.brightness_threshold = (
            brightness_threshold
        )

        self.duration_threshold = (
            duration_threshold
        )

        self.resize_width = resize_width
        self.resize_height = resize_height

        self._in_black = False

        self._black_start = None

        self._brightness_sum = 0.0
        self._brightness_count = 0

        self._last_timestamp = 0.0

        self._issues: List[
            DetectedIssue
        ] = []

    def process(
        self,
        frame: VideoFrame,
    ):

        brightness = (
            self._calculate_brightness(
                frame.image
            )
        )

        timestamp = frame.timestamp

        self._last_timestamp = timestamp

        is_black = (
            brightness
            <
            self.brightness_threshold
        )

        if is_black:

            self._handle_black_frame(
                timestamp,
                brightness,
            )

        else:

            self._handle_normal_frame(
                timestamp
            )
        return is_black

    def finish(self, end_time=None):

        if self._in_black:

            self._finish_black_event(
                self._last_timestamp if end_time is None else end_time
            )

        return list(self._issues)

    def reset(self):

        self._in_black = False

        self._black_start = None

        self._brightness_sum = 0.0
        self._brightness_count = 0

        self._last_timestamp = 0.0

        self._issues = []

    def _calculate_brightness(
        self,
        image,
    ) -> float:

        resized = cv2.resize(
            image,
            (
                self.resize_width,
                self.resize_height,
            )
        )

        gray = cv2.cvtColor(
            resized,
            cv2.COLOR_BGR2GRAY,
        )

        brightness = float(
            np.mean(gray)
        )

        return brightness

    def _handle_black_frame(
        self,
        timestamp: float,
        brightness: float,
    ):

        if not self._in_black:

            self._in_black = True

            self._black_start = timestamp

            self._brightness_sum = 0.0
            self._brightness_count = 0

        self._brightness_sum += brightness
        self._brightness_count += 1

    def _handle_normal_frame(
        self,
        timestamp: float,
    ):

        if not self._in_black:
            return

        self._finish_black_event(
            timestamp
        )

    def _finish_black_event(
        self,
        end_time: float,
    ):

        if self._black_start is None:

            self._reset_current_event()

            return

        duration = (
            end_time
            -
            self._black_start
        )

        if (
            duration
            + 1e-9 >=
            self.duration_threshold
        ):

            average_brightness = (
                self._get_average_brightness()
            )

            severity = (
                self._get_severity(
                    duration
                )
            )

            issue = DetectedIssue(
                issue_type=self.ISSUE_TYPE,

                start_time=(
                    self._black_start
                ),

                end_time=end_time,

                duration=duration,

                severity=severity,

                description=(
                    f"检测到持续"
                    f"{duration:.3f}秒黑屏。"
                ),

                extra_data={
                    "average_brightness":
                    average_brightness,
                },
            )

            self._issues.append(
                issue
            )

        self._reset_current_event()

    def _reset_current_event(self):

        self._in_black = False

        self._black_start = None

        self._brightness_sum = 0.0
        self._brightness_count = 0

    def _get_average_brightness(
        self,
    ) -> float:

        return self._brightness_sum / self._brightness_count if self._brightness_count else 0.0

    @staticmethod
    def _get_severity(
        duration: float,
    ) -> str:

        if duration < 1.0:

            return "LOW"

        if duration < 2.0:

            return "MEDIUM"

        return "HIGH"
