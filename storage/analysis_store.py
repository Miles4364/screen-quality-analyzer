"""事务保存分析结果；每次操作独立连接，不跨线程共享连接。"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from core.models import AnalysisConfig, AnalysisResult, DetectedIssue, VideoMetadata

DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / 'data' / 'analysis.sqlite3'


class StorageError(Exception):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class AnalysisStore:
    def __init__(self, path=DEFAULT_DATABASE):
        self.path = Path(path).resolve()

    @contextmanager
    def connection(self):
        connection = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=.25)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys = ON')
            with connection:
                # 初始化与版本检查同处写事务，避免并发初始化的半成品结构。
                connection.execute('BEGIN IMMEDIATE')
                version = connection.execute('PRAGMA user_version').fetchone()[0]
                if version == 0:
                    tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                    if tables:
                        raise StorageError('数据库没有受支持的版本信息，请选择新的数据库文件')
                    connection.execute('''CREATE TABLE tasks (
                        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, filename TEXT NOT NULL,
                        metadata_json TEXT NOT NULL, config_json TEXT NOT NULL,
                        processing_time REAL NOT NULL, processed_frames INTEGER NOT NULL,
                        analyzed_duration REAL NOT NULL, source_mtime_ns INTEGER,
                        app_version TEXT NOT NULL)''')
                    connection.execute('''CREATE TABLE issues (
                        task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                        ordinal INTEGER NOT NULL, issue_json TEXT NOT NULL,
                        PRIMARY KEY(task_id, ordinal))''')
                    connection.execute('''CREATE TABLE screenshots (
                        id TEXT PRIMARY KEY, task_id TEXT NOT NULL, issue_ordinal INTEGER NOT NULL,
                        path TEXT NOT NULL, frame_index INTEGER NOT NULL CHECK(frame_index >= 0),
                        timestamp REAL NOT NULL, created_at TEXT NOT NULL, sha256 TEXT NOT NULL,
                        FOREIGN KEY(task_id, issue_ordinal) REFERENCES issues(task_id, ordinal),
                        UNIQUE(task_id, issue_ordinal, path))''')
                    connection.execute('CREATE INDEX tasks_created ON tasks(created_at DESC, id DESC)')
                    connection.execute('PRAGMA user_version = 1')
                elif version != 1:
                    raise StorageError(f'不支持数据库版本 {version}，请使用匹配的软件版本')
                yield connection
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
            raise StorageError(f'本地数据库操作失败：{exc}') from exc
        finally:
            if connection is not None:
                connection.close()

    def save_result(self, result, config=None):
        task_id = uuid4().hex
        source = Path(result.video_metadata.filepath)
        try:
            mtime = source.stat().st_mtime_ns
        except OSError:
            mtime = None
        with self.connection() as db:
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?)', (
                task_id, datetime.now(timezone.utc).isoformat(), result.video_metadata.filename,
                encode(asdict(result.video_metadata)), encode(asdict(config or AnalysisConfig())),
                result.processing_time, result.processed_frames, result.analyzed_duration,
                mtime, '0.4',
            ))
            db.executemany('INSERT INTO issues VALUES (?,?,?)', (
                (task_id, index, encode(asdict(issue))) for index, issue in enumerate(result.issues)
            ))
        return task_id

    def list_tasks(self, limit=50, offset=0):
        if not 1 <= limit <= 200 or offset < 0:
            raise StorageError('无效分页参数')
        with self.connection() as db:
            return [dict(row) for row in db.execute('''
                SELECT t.id, t.created_at, t.filename, t.processed_frames,
                       (SELECT count(*) FROM issues i WHERE i.task_id=t.id) AS issue_count
                FROM tasks t ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?
            ''', (limit, offset))]

    def load_task(self, task_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise StorageError('找不到该历史任务')
            issues = [DetectedIssue(**json.loads(i[0])) for i in db.execute(
                'SELECT issue_json FROM issues WHERE task_id=? ORDER BY ordinal', (task_id,))]
            result = AnalysisResult(VideoMetadata(**json.loads(row['metadata_json'])), issues,
                                    row['processing_time'], row['processed_frames'], row['analyzed_duration'])
            return {'id': task_id, 'result': result,
                    'config': AnalysisConfig(**json.loads(row['config_json'])),
                    'source_mtime_ns': row['source_mtime_ns'], 'created_at': row['created_at']}

    @staticmethod
    def source_available(task):
        try:
            stat = Path(task['result'].video_metadata.filepath).stat()
            return (stat.st_size == task['result'].video_metadata.file_size and
                    task['source_mtime_ns'] is not None and stat.st_mtime_ns == task['source_mtime_ns'])
        except OSError:
            return False

    def add_screenshot(self, task_id, ordinal, path, frame_index, timestamp):
        path = Path(path).resolve()
        if not path.is_file():
            raise StorageError('截图文件不存在，未建立关联')
        with self.connection() as db:
            db.execute('''INSERT INTO screenshots VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(task_id, issue_ordinal, path) DO UPDATE SET
                frame_index=excluded.frame_index, timestamp=excluded.timestamp,
                created_at=excluded.created_at, sha256=excluded.sha256''', (
                uuid4().hex, task_id, ordinal, str(path), frame_index, timestamp,
                datetime.now(timezone.utc).isoformat(), hashlib.sha256(path.read_bytes()).hexdigest(),
            ))

    def list_screenshots(self, task_id, ordinal=None):
        with self.connection() as db:
            sql = 'SELECT * FROM screenshots WHERE task_id=?'
            params = [task_id]
            if ordinal is not None:
                sql += ' AND issue_ordinal=?'
                params.append(ordinal)
            return [dict(row) for row in db.execute(sql + ' ORDER BY created_at', params)]
