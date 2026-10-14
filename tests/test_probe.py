import subprocess
from types import SimpleNamespace

import pytest

from exceptions.video_exception import VideoProbeError
from utils.ffmpeg_util import probe_video


@pytest.mark.parametrize('result', [
    SimpleNamespace(returncode=1, stdout='', stderr='invalid file'),
    SimpleNamespace(returncode=0, stdout='not json', stderr=''),
])
def test_bad_output(monkeypatch, result):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: result)
    with pytest.raises(VideoProbeError):
        probe_video('test.mp4')


@pytest.mark.parametrize('error', [FileNotFoundError(), subprocess.TimeoutExpired('ffprobe', 30)])
def test_execution_error(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(VideoProbeError):
        probe_video('test.mp4')
