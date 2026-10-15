from dataclasses import asdict
import pytest
from core.models import DetectedIssue
from tests.test_storage import result
from storage.analysis_store import AnalysisStore


def issue(kind, start, end):
    return DetectedIssue(kind, start, end, end-start, 'HIGH', '测试')


@pytest.mark.parametrize('events,expected,black,freeze', [
    ([],100,0,0),
    ([('BLACK_SCREEN',0,60)],0,60,0),
    ([('FREEZE',0,60)],50,0,60),
    ([('BLACK_SCREEN',10,12),('BLACK_SCREEN',40,41),('FREEZE',25,27),('FREEZE',50,53)],90.83,3,5),
    ([('BLACK_SCREEN',0,20),('BLACK_SCREEN',10,30),('FREEZE',20,40),('FREEZE',30,40)],41.67,30,10),
    ([('BLACK_SCREEN',-5,5),('FREEZE',55,70)],87.5,5,5),
    ([('BLACK_SCREEN',70,80),('FREEZE',2,2)],100,0,0),
])
def test_score_intervals(result, events, expected, black, freeze):
    result.analyzed_duration = 60
    result.issues = [issue(*event) for event in reversed(events)]
    before = asdict(result)
    q = result.quality
    assert q.score == expected
    assert q.black_seconds == black
    assert q.freeze_seconds == freeze
    assert asdict(result) == before
    assert q.rule_version == 'duration-v1'


@pytest.mark.parametrize('duration', [0,-1,float('nan'),float('inf')])
def test_invalid_duration(result,duration):
    result.analyzed_duration = duration
    assert result.quality.score is None
    assert result.quality.reason


@pytest.mark.parametrize('event', [('FREEZE',3,2),('FREEZE',0,float('nan')),('OTHER',1,2)])
def test_invalid_event(result,event):
    result.issues = [issue(*event)]
    assert result.quality.score is None


def test_history_recomputes_without_mutation(tmp_path,result):
    store = AnalysisStore(tmp_path/'db.sqlite3')
    task_id = store.save_result(result)
    assert store.load_task(task_id)['result'].quality == result.quality
    result.processed_frames = 0
    assert result.quality.score is None
