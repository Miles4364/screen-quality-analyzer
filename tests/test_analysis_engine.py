import json
import shutil
import subprocess
import sys
import pytest
from core.analysis_engine import AnalysisEngine
from core.models import AnalysisConfig
from tools.generate_samples import generate

pytestmark = pytest.mark.skipif(not shutil.which('ffprobe'), reason='需要 FFprobe')


def test_final_validation(tmp_path):
    path = generate(tmp_path / '中文 验收.mp4')
    engine = AnalysisEngine()
    result = engine.analyze(str(path))
    expected = [('BLACK_SCREEN', 10, 12), ('FREEZE', 25, 27), ('BLACK_SCREEN', 40, 41), ('FREEZE', 50, 53)]
    assert len(result.issues) == 4
    for issue, (kind, start, end) in zip(result.issues, expected):
        assert issue.issue_type == kind
        assert issue.start_time == pytest.approx(start, abs=1/30)
        assert issue.end_time == pytest.approx(end, abs=1/30)
    assert result.processed_frames == 1800
    assert result.statistics == {'black_count': 2, 'freeze_count': 2, 'total_count': 4}
    assert result.processing_time > 0
    normal = generate(tmp_path / 'normal.mp4', duration=1, black=(), freeze=())
    assert engine.analyze(str(normal)).issues == []
    cli = subprocess.run([sys.executable, 'main.py', str(path), '--json'], capture_output=True, encoding='utf-8', env=__import__('os').environ | {'PYTHONIOENCODING': 'utf-8'})
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)['statistics'] == result.statistics


@pytest.mark.parametrize('kind,duration', [('BLACK_SCREEN', .2), ('BLACK_SCREEN', .5), ('FREEZE', .2), ('FREEZE', .5), ('FREEZE', 1), ('FREEZE', 2), ('FREEZE', 5)])
def test_encoded_boundaries(tmp_path, kind, duration):
    intervals = ((1, 1 + duration),)
    path = generate(tmp_path / 'boundary.mp4', duration=1 + duration,
                    black=intervals if kind == 'BLACK_SCREEN' else (),
                    freeze=intervals if kind == 'FREEZE' else ())
    result = AnalysisEngine().analyze(str(path))
    assert len(result.issues) == (0 if duration < .5 else 1)
    if result.issues:
        assert result.issues[0].issue_type == kind
        assert result.issues[0].duration == pytest.approx(duration, abs=1/30)


def test_configuration(tmp_path):
    path = generate(tmp_path / 'config.mp4', duration=2, black=((1, 2),), freeze=())
    assert AnalysisEngine(AnalysisConfig(black_duration=2)).analyze(str(path)).issues == []


def test_cli_errors():
    for args in [[], ['missing.mp4'], ['missing.mp4', '--freeze-duration', 'nan']]:
        result = subprocess.run([sys.executable, 'main.py', *args], capture_output=True)
        assert result.returncode != 0
        assert b'Traceback' not in result.stderr
