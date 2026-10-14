import math

import cv2

from core.models import VideoFrame
from exceptions.video_exception import VideoError


class VideoReadError(VideoError):
    """
    视频读取失败。
    """

    pass


class VideoReader:
    """
    使用OpenCV逐帧读取视频。
    """

    def __init__(self, filepath: str):

        self.filepath = filepath

        self._capture = None

        self.fps = 0.0
        self.frame_count = 0

        self.current_index = 0

    def open(self):
        self.close()

        self._capture = cv2.VideoCapture(
            self.filepath
        )

        if not self._capture.isOpened():

            self.close()
            raise VideoReadError(
                f"无法打开视频：{self.filepath}"
            )

        self.fps = self._capture.get(
            cv2.CAP_PROP_FPS
        )

        self.frame_count = int(
            self._capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        if not math.isfinite(self.fps) or self.fps <= 0:
            self.close()

            raise VideoReadError(
                "无法获取有效视频帧率。"
            )

        self.current_index = 0

    def read(self):

        if self._capture is None:

            raise VideoReadError(
                "VideoReader尚未打开。"
            )

        success, image = self._capture.read()

        if not success:

            return None

        timestamp = (
            self.current_index
            /
            self.fps
        )

        frame = VideoFrame(
            index=self.current_index,
            timestamp=timestamp,
            image=image,
        )

        self.current_index += 1

        return frame

    def close(self):

        if self._capture is not None:

            self._capture.release()

            self._capture = None

    def __iter__(self):

        if self._capture is None:
            self.open()

        return self

    def __next__(self):

        frame = self.read()

        if frame is None:

            self.close()

            raise StopIteration

        return frame

    def __enter__(self):

        self.open()

        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):

        self.close()
