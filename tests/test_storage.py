from dataclasses import asdict
import json
import sqlite3
import pytest
from core.models import AnalysisConfig, AnalysisResult, DetectedIssue, VideoMetadata
from storage.analysis_store import AnalysisStore, StorageError


@pytest.fixture
def result(tmp_path):
    source = tmp_path / "会议 '测试.mp4"
    source.write_bytes(b'source video fixture')
    metadata = VideoMetadata(source.name, str(source), source.stat().st_size,
                             3, 640, 360, 30, 90, 'mpeg4', 1000)
    return AnalysisResult(metadata, [DetectedIssue('BLACK_SCREEN', 1, 2, 1, 'MEDIUM', '黑屏', {'brightness': 0})], .2, 90, 3)


def test_roundtrip_reopen_config_and_history(tmp_path, result):
    store = AnalysisStore(tmp_path / '中文 数据.sqlite3')
    config = AnalysisConfig(black_threshold=15)
    task_id = store.save_result(result, config)
    reopened = AnalysisStore(store.path)
    task = reopened.load_task(task_id)
    assert asdict(task['result']) == asdict(result)
    assert task['config'] == config
    assert reopened.source_available(task)
    assert reopened.list_tasks()[0]['issue_count'] == 1
    assert reopened.list_tasks()[0]['filename'] == result.video_metadata.filename
    assert len(reopened.list_tasks()) == 1


def test_atomic_rollback(tmp_path, result):
    store = AnalysisStore(tmp_path / 'test.sqlite3')
    result.issues.append(DetectedIssue('FREEZE', 2, 3, 1, 'MEDIUM', 'invalid JSON', {'bad': object()}))
    with pytest.raises(StorageError):
        store.save_result(result)
    assert store.list_tasks() == []
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM issues').fetchone()[0] == 0


def test_screenshots_foreign_key_and_upsert(tmp_path, result):
    store = AnalysisStore(tmp_path / 'test.sqlite3')
    task_id = store.save_result(result)
    screenshot = tmp_path / '中文.png'
    screenshot.write_bytes(b'fixture')
    store.add_screenshot(task_id, 0, screenshot, 30, 1)
    store.add_screenshot(task_id, 0, screenshot, 31, 31/30)
    records = AnalysisStore(store.path).list_screenshots(task_id)
    assert len(records) == 1
    assert records[0]['frame_index'] == 31
    assert records[0]['path'] == str(screenshot.resolve())
    with pytest.raises(StorageError):
        store.add_screenshot(task_id, 10, screenshot, 0, 0)
    with pytest.raises(StorageError):
        store.add_screenshot(task_id, 0, tmp_path / 'missing.png', 0, 0)


def test_missing_and_changed_source(tmp_path, result):
    store = AnalysisStore(tmp_path / 'test.sqlite3')
    task = store.load_task(store.save_result(result))
    from pathlib import Path
    Path(result.video_metadata.filepath).write_bytes(b'changed')
    assert not store.source_available(task)
    Path(result.video_metadata.filepath).unlink()
    assert store.load_task(task['id'])['result'].issues
    assert not store.source_available(task)


@pytest.mark.parametrize('case', ['newer', 'corrupt', 'unversioned'])
def test_unusable_database(tmp_path, case):
    path = tmp_path / 'bad.sqlite3'
    if case == 'corrupt':
        path.write_bytes(b'not sqlite')
    else:
        with sqlite3.connect(path) as db:
            db.execute('PRAGMA user_version=99' if case == 'newer' else 'CREATE TABLE unrelated(x)')
    before = path.read_bytes()
    with pytest.raises(StorageError):
        AnalysisStore(path).list_tasks()
    assert path.read_bytes() == before


def test_locked_and_bad_path(tmp_path, result):
    store = AnalysisStore(tmp_path / 'test.sqlite3')
    store.save_result(result)
    with sqlite3.connect(store.path) as other:
        other.execute('BEGIN EXCLUSIVE')
        with pytest.raises(StorageError, match='locked'):
            store.save_result(result)
    assert len(store.list_tasks()) == 1
    with pytest.raises(StorageError):
        AnalysisStore(tmp_path).save_result(result)


def test_pagination_and_missing_task(tmp_path, result):
    store = AnalysisStore(tmp_path / 'test.sqlite3')
    ids = [store.save_result(result) for _ in range(3)]
    assert [x['id'] for x in store.list_tasks(2)] == ids[::-1][:2]
    assert store.list_tasks(2, 2)[0]['id'] == ids[0]
    with pytest.raises(StorageError):
        store.load_task('missing')


def test_cli_persistence(tmp_path):
    import shutil
    import subprocess
    import sys
    from tools.generate_samples import generate
    if not shutil.which('ffprobe'):
        pytest.skip('需要 FFprobe')
    video = generate(tmp_path / 'cli.mp4', duration=1, black=(), freeze=())
    db = tmp_path / 'cli.sqlite3'
    run = subprocess.run([sys.executable, 'main.py', str(video), '--json', '--database', str(db), '--freeze-duration', '2'], capture_output=True)
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)
    task = AnalysisStore(db).load_task(data['task_id'])
    assert task['config'].freeze_duration == 2
    assert task['result'].processed_frames == 30
    failed = subprocess.run([sys.executable, 'main.py', str(video), '--database', str(tmp_path)], capture_output=True)
    assert failed.returncode == 1
    assert b'Traceback' not in failed.stderr
