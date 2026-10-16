import sys
from pathlib import Path
from utils.runtime import default_database, ffprobe_command


def test_frozen_database_is_user_data(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'user'))
    assert default_database() == tmp_path/'user'/'ScreenQualityAnalyzer'/'analysis.sqlite3'


def test_ffprobe_priority(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'executable',str(tmp_path/'app.exe'))
    monkeypatch.delenv('SQA_FFPROBE',raising=False)
    assert ffprobe_command() == 'ffprobe'
    (tmp_path/'tools').mkdir()
    local = tmp_path/'tools'/'ffprobe.exe'
    local.touch()
    assert ffprobe_command() == str(local)
    explicit = tmp_path/'中文 ffprobe.exe'
    monkeypatch.setenv('SQA_FFPROBE',str(explicit))
    assert ffprobe_command() == str(explicit)


def test_source_database_stays_in_project(monkeypatch):
    monkeypatch.delattr(sys,'frozen',raising=False)
    assert default_database() == Path(__file__).resolve().parents[1]/'data'/'analysis.sqlite3'
