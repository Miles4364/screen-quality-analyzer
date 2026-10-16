import math

import cv2

from core.models import VideoFrame
from exceptions.video_exception import VideoError
from utils.ffmpeg_util import count_decoded_frames


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
        self._eof = False
        self.should_cancel = None
        self.on_verify = None

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

        count = self._capture.get(cv2.CAP_PROP_FRAME_COUNT)
        self.frame_count = int(count) if math.isfinite(count) and count > 0 else 0

        if not math.isfinite(self.fps) or self.fps <= 0:
            self.close()

            raise VideoReadError(
                "无法获取有效视频帧率。"
            )

        self.current_index = 0
        self._eof = False

    def read(self):

        if self._eof:
            return None

        if self._capture is None:

            raise VideoReadError(
                "VideoReader尚未打开。"
            )

        try:
            success, image = self._capture.read()
        except cv2.error as exc:
            self.close()
            raise VideoReadError(f"解码失败：{exc}") from exc

        if not success:
            self.close()
            self._eof = True
            if self.current_index == 0 or (self.frame_count and self.current_index < self.frame_count):
                missing = self.frame_count - self.current_index
                # 只核验极小的近末尾差异；明显截断仍直接报错。
                if (self.current_index > 0 and 0 < missing <= min(10, max(2, math.ceil(self.fps * .1)))
                        and missing / self.frame_count <= .001):
                    if self.on_verify:
                        self.on_verify('帧数存在少量偏差，正在独立解码核验，可取消…')
                    verified = count_decoded_frames(self.filepath, self.should_cancel)
                    if verified == self.current_index:
                        return None
                raise VideoReadError(f"视频提前结束：已读取 {self.current_index}/{self.frame_count} 帧")
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

        if self._capture is None and not self._eof:
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
