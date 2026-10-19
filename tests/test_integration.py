"""自动生成固定帧率素材，验证真实 FFprobe/OpenCV 链路。"""
import shutil
import subprocess
import sys
import os
import json

import pytest

from core.black_detector import BlackDetector
from core.video_parser import VideoParser
from core.video_reader import VideoReader
from exceptions.video_exception import VideoError


@pytest.mark.parametrize('fps', ['30', '30000/1001'])
@pytest.mark.parametrize('size', ['1280x720', '1920x1080'])
def test_real_video(tmp_path, fps, size):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('需要 FFmpeg 和 FFprobe')
    path = tmp_path / '投屏测试 01.mp4'
    subprocess.run([
        'ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
        f'color=white:size={size}:rate={fps}:duration=3',
        '-vf', "drawbox=color=black:t=fill:enable='gte(t,1)'",
        '-c:v', 'mpeg4', '-y', str(path),
    ], check=True, timeout=60)
    metadata = VideoParser().parse(str(path))
    assert metadata.resolution == size
    expected_fps = 30 if fps == '30' else 30000 / 1001
    assert metadata.fps == pytest.approx(expected_fps, abs=0.001)
    assert metadata.audio_codec is None
    detector = BlackDetector()
    with VideoReader(str(path)) as reader:
        first = reader.read()
        assert first.index == 0
        remaining = list(reader)
        assert remaining[0].index == 1  # 迭代不会重新打开视频
        for frame in [first, *remaining]:
            detector.process(frame)
        end = reader.current_index / reader.fps
    assert reader._capture is None
    issues = detector.finish(end)
    assert len(issues) == 1
    assert issues[0].start_time == pytest.approx(1, abs=1 / expected_fps)
    assert issues[0].end_time == pytest.approx(end)
    assert issues[0].duration == pytest.approx(2, abs=1 / expected_fps)
    assert detector.finish(end) == issues
    for script in ['main.py', 'black_test.py']:
        result = subprocess.run([sys.executable, script, str(path)], capture_output=True)
        assert result.returncode == 0, result.stderr
    # 模拟 Windows 非 UTF-8 输出环境，覆盖中文及特殊字符文件名。
    unicode_path = path.with_name('投屏测试 🎬.mp4')
    path.rename(unicode_path)
    env = dict(os.environ, PYTHONIOENCODING='gb18030', PYTHONUTF8='0')
    result = subprocess.run([sys.executable, 'main.py', str(unicode_path), '--json'],
                            capture_output=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.decode('utf-8'))['video_metadata']['filename'] == unicode_path.name
    missing = unicode_path.with_name('不存在 🎬.mp4')
    result = subprocess.run([sys.executable, 'main.py', str(missing)],
                            capture_output=True, env=env, timeout=30)
    assert result.returncode == 1
    assert '分析失败' in result.stderr.decode('utf-8')


def test_invalid_files(tmp_path):
    with pytest.raises(VideoError):
        VideoParser().parse(str(tmp_path / 'missing.mp4'))
    path = tmp_path / 'invalid.mp4'
    path.write_text('not video')
    if shutil.which('ffprobe'):
        with pytest.raises(VideoError):
            VideoParser().parse(str(path))
    for script in ['main.py', 'black_test.py']:
        result = subprocess.run([sys.executable, script, str(path)], capture_output=True)
        assert result.returncode != 0
