class VideoError(Exception):
    """
    视频处理基础异常。
    """

    pass


class VideoFileNotFoundError(VideoError):
    """
    视频文件不存在。
    """

    pass


class VideoProbeError(VideoError):
    """
    FFprobe执行失败。
    """

    pass


class VideoStreamNotFoundError(VideoError):
    """
    未找到视频流。
    """

    pass


class VideoMetadataError(VideoError):
    """
    视频Metadata数据异常。
    """

    pass


class AnalysisCancelled(VideoError):
    """用户取消分析；不应保存部分结果作为成功结果。"""
