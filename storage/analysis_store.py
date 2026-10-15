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
                    version = 1
                if version == 1:
                    self._migrate_v2(connection)
                elif version != 2:
                    raise StorageError(f'不支持数据库版本 {version}，请使用匹配的软件版本')
                yield connection
        except sqlite3.IntegrityError as exc:
            if 'projects.name' in str(exc):
                raise StorageError('保存失败：已存在同名项目，请使用其他名称') from exc
            if 'FOREIGN KEY' in str(exc):
                raise StorageError('保存失败：关联项目或任务不存在，请刷新后重试') from exc
            raise StorageError(f'数据校验失败：{exc}') from exc
        except (sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
            raise StorageError(f'本地数据库操作失败：{exc}') from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _migrate_v2(db):
        # 与调用者事务一起提交；失败时连同 DDL 和版本号整体回滚。
        db.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, created_at TEXT NOT NULL)")
        db.execute("ALTER TABLE tasks ADD COLUMN title TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT REFERENCES projects(id)")
        db.execute('UPDATE tasks SET title=filename')
        db.execute('CREATE INDEX tasks_project ON tasks(project_id, created_at DESC)')
        db.execute('PRAGMA user_version = 2')

    @staticmethod
    def _name(value, limit):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise StorageError(f'名称不能为空且最多 {limit} 个字符')
        return value.strip()

    def create_project(self, name):
        name = self._name(name, 80)
        project_id = uuid4().hex
        with self.connection() as db:
            db.execute('INSERT INTO projects VALUES (?,?,?)',
                       (project_id, name, datetime.now(timezone.utc).isoformat()))
        return project_id

    def list_projects(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute('SELECT id,name FROM projects ORDER BY name COLLATE NOCASE,id')]

    def rename_project(self, project_id, name):
        name = self._name(name, 80)
        with self.connection() as db:
            if db.execute('UPDATE projects SET name=? WHERE id=?', (name, project_id)).rowcount != 1:
                raise StorageError('项目不存在')

    def rename_task(self, task_id, title):
        title = self._name(title, 120)
        with self.connection() as db:
            if db.execute('UPDATE tasks SET title=? WHERE id=?', (title, task_id)).rowcount != 1:
                raise StorageError('任务不存在')

    def move_task(self, task_id, project_id):
        with self.connection() as db:
            if db.execute('UPDATE tasks SET project_id=? WHERE id=?', (project_id, task_id)).rowcount != 1:
                raise StorageError('任务不存在')

    def save_result(self, result, config=None, *, title=None, project_id=None):
        task_id = uuid4().hex
        source = Path(result.video_metadata.filepath)
        try:
            mtime = source.stat().st_mtime_ns
        except OSError:
            mtime = None
        with self.connection() as db:
            db.execute('''INSERT INTO tasks (id,created_at,filename,metadata_json,config_json,processing_time,processed_frames,analyzed_duration,source_mtime_ns,app_version,title,project_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (
                task_id, datetime.now(timezone.utc).isoformat(), result.video_metadata.filename,
                encode(asdict(result.video_metadata)), encode(asdict(config or AnalysisConfig())),
                result.processing_time, result.processed_frames, result.analyzed_duration,
                mtime, '0.5', self._name(title if title is not None else result.video_metadata.filename[:120], 120), project_id,
            ))
            db.executemany('INSERT INTO issues VALUES (?,?,?)', (
                (task_id, index, encode(asdict(issue))) for index, issue in enumerate(result.issues)
            ))
        return task_id

    def list_tasks(self, limit=50, offset=0, *, project_id='all', search=''):
        if not 1 <= limit <= 200 or offset < 0:
            raise StorageError('无效分页参数')
        where, params = [], []
        if project_id != 'all':
            where.append('t.project_id IS ?')
            params.append(project_id)
        if search.strip():
            # instr 使用字面子串，% 与 _ 不会成为 SQL 通配符。
            where.append('(instr(lower(t.title),lower(?))>0 OR instr(lower(t.filename),lower(?))>0)')
            params.extend([search.strip(), search.strip()])
        query = """SELECT t.id,t.created_at,t.filename,t.title,t.project_id,p.name AS project_name,
                   t.processed_frames,(SELECT count(*) FROM issues i WHERE i.task_id=t.id) AS issue_count
                   FROM tasks t LEFT JOIN projects p ON p.id=t.project_id"""
        if where:
            query += ' WHERE ' + ' AND '.join(where)
        query += ' ORDER BY t.created_at DESC,t.id DESC LIMIT ? OFFSET ?'
        with self.connection() as db:
            return [dict(row) for row in db.execute(query, [*params, limit, offset])]

    def load_task(self, task_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise StorageError('找不到该历史任务')
            issues = [DetectedIssue(**json.loads(i[0])) for i in db.execute(
                'SELECT issue_json FROM issues WHERE task_id=? ORDER BY ordinal', (task_id,))]
            result = AnalysisResult(VideoMetadata(**json.loads(row['metadata_json'])), issues,
                                    row['processing_time'], row['processed_frames'], row['analyzed_duration'])
            return {'id': task_id, 'result': result, 'title': row['title'], 'project_id': row['project_id'],
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
