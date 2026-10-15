import json
import sqlite3
from dataclasses import asdict
import pytest
from storage.analysis_store import AnalysisStore, StorageError
from tests.test_storage import result


@pytest.fixture
def legacy(tmp_path, result):
    path = tmp_path / 'v04.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE tasks (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, filename TEXT NOT NULL,
                metadata_json TEXT NOT NULL,config_json TEXT NOT NULL,processing_time REAL NOT NULL,
                processed_frames INTEGER NOT NULL,analyzed_duration REAL NOT NULL,source_mtime_ns INTEGER,app_version TEXT NOT NULL);
            CREATE TABLE issues (task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL,issue_json TEXT NOT NULL,PRIMARY KEY(task_id,ordinal));
            CREATE TABLE screenshots (id TEXT PRIMARY KEY,task_id TEXT NOT NULL,issue_ordinal INTEGER NOT NULL,
                path TEXT NOT NULL,frame_index INTEGER NOT NULL CHECK(frame_index>=0),timestamp REAL NOT NULL,
                created_at TEXT NOT NULL,sha256 TEXT NOT NULL,
                FOREIGN KEY(task_id,issue_ordinal) REFERENCES issues(task_id,ordinal),UNIQUE(task_id,issue_ordinal,path));
            CREATE INDEX tasks_created ON tasks(created_at DESC,id DESC);
            PRAGMA user_version=1;
        ''')
        db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)', ('old','2026-10-14T00:00:00+00:00',result.video_metadata.filename,json.dumps(asdict(result.video_metadata)), '{}',.2,90,3,None,'0.4'))
        db.execute('INSERT INTO issues VALUES (?,?,?)', ('old',0,json.dumps(asdict(result.issues[0]))))
        db.execute('INSERT INTO screenshots VALUES (?,?,?,?,?,?,?,?)', ('shot','old',0,'old.png',30,1,'2026-10-14','digest'))
    return path


def test_upgrade_retains_result_screenshots_and_version(legacy, result):
    store = AnalysisStore(legacy)
    task = store.load_task('old')
    assert task['title'] == result.video_metadata.filename
    assert task['project_id'] is None
    assert asdict(task['result']) == asdict(result)
    assert store.list_screenshots('old')[0]['sha256'] == 'digest'
    assert len(AnalysisStore(legacy).list_tasks()) == 1
    with sqlite3.connect(legacy) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 3
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_failed_migration_rolls_back(legacy, monkeypatch):
    store = AnalysisStore(legacy)
    original = store._migrate_v2
    def fail(db):
        original(db)
        raise sqlite3.OperationalError('injected migration failure')
    monkeypatch.setattr(store, '_migrate_v2', fail)
    with pytest.raises(StorageError):
        store.list_tasks()
    with sqlite3.connect(legacy) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert 'title' not in [row[1] for row in db.execute('PRAGMA table_info(tasks)')]
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='projects'").fetchall()
        assert db.execute('SELECT count(*) FROM screenshots').fetchone()[0] == 1


def test_project_task_rename_move_filter_and_pagination(tmp_path, result):
    store = AnalysisStore(tmp_path / 'db.sqlite3')
    first = store.create_project('会议室 A')
    second = store.create_project('会议室 B')
    task = store.save_result(result, title="中文 100%_'", project_id=first)
    other = store.save_result(result, title='Other', project_id=first)
    store.save_result(result)
    assert len(store.list_tasks(project_id=None)) == 1
    assert len(store.list_tasks(project_id=first)) == 2
    assert store.list_tasks(project_id=first, search="%_'")[0]['id'] == task
    assert len(store.list_tasks(1, 1, project_id=first)) == 1
    store.rename_project(first, '改名后')
    store.rename_task(task, '新任务')
    store.move_task(task, second)
    assert store.list_tasks(project_id=first)[0]['id'] == other
    assert store.list_tasks(project_id=second)[0]['title'] == '新任务'
    assert asdict(store.load_task(task)['result']) == asdict(result)
    store.move_task(task, None)
    assert store.load_task(task)['project_id'] is None


def test_move_preserves_existing_screenshot(legacy):
    store = AnalysisStore(legacy)
    project = store.create_project('Project')
    store.move_task('old', project)
    assert store.list_screenshots('old')[0]['id'] == 'shot'
    with pytest.raises(StorageError):
        store.move_task('old', 'missing-project')
    assert store.load_task('old')['project_id'] == project


@pytest.mark.parametrize('name', ['', '  ', 'x'*81])
def test_invalid_project_names(tmp_path, name):
    with pytest.raises(StorageError):
        AnalysisStore(tmp_path / 'db.sqlite3').create_project(name)


def test_duplicates_and_missing_ids(tmp_path, result):
    store = AnalysisStore(tmp_path / 'db.sqlite3')
    store.create_project('Alpha')
    with pytest.raises(StorageError):
        store.create_project(' alpha ')
    with pytest.raises(StorageError):
        store.save_result(result, project_id='missing')
    assert store.list_tasks() == []
    for action in [lambda: store.rename_project('missing','x'), lambda: store.rename_task('missing','x'), lambda: store.move_task('missing',None)]:
        with pytest.raises(StorageError):
            action()

@pytest.mark.parametrize('title', ['', ' ', 'x'*121])
def test_invalid_task_titles(tmp_path, result, title):
    store = AnalysisStore(tmp_path / 'db.sqlite3')
    task = store.save_result(result)
    with pytest.raises(StorageError):
        store.rename_task(task, title)
    assert store.load_task(task)['title'] == result.video_metadata.filename


def test_cli_task_project_assignment(tmp_path):
    import shutil
    import subprocess
    import sys
    from tools.generate_samples import generate
    if not shutil.which('ffprobe'):
        pytest.skip('需要 FFprobe')
    store = AnalysisStore(tmp_path / 'cli.sqlite3')
    project = store.create_project('CLI 项目')
    path = generate(tmp_path / 'cli.mp4', duration=1, black=(), freeze=())
    command = [sys.executable, 'main.py', str(path), '--database', str(store.path), '--json', '--task-name', 'CLI test', '--project-id', project]
    run = subprocess.run(command, capture_output=True)
    assert run.returncode == 0, run.stderr
    task = store.load_task(json.loads(run.stdout)['task_id'])
    assert task['title'] == 'CLI test' and task['project_id'] == project
    failed = subprocess.run([sys.executable, 'main.py', str(path), '--task-name', 'requires database'], capture_output=True)
    assert failed.returncode == 2
