from unittest.mock import MagicMock
import pytest
import utils.ffmpeg_util as util
from exceptions.video_exception import VideoProbeError, AnalysisCancelled
from tests.test_storage import result
from storage.analysis_store import AnalysisStore


@pytest.mark.parametrize('payload,error,code,expected', [
    (b'{"streams":[{"nb_read_frames":"5637"}]}',b'',0,5637),
    (b'{"streams":[{"nb_read_frames":"5637"}]}',b'decode error',0,None),
    (b'{"streams":[]}',b'',0,None),
    (b'bad json',b'',0,None),
    (b'{}',b'',1,None),
])
def test_verification_output(monkeypatch,payload,error,code,expected):
    proc=MagicMock();proc.communicate.return_value=(payload,error);proc.returncode=code;proc.poll.return_value=code
    monkeypatch.setattr(util.subprocess,'Popen',lambda *a,**k:proc)
    if expected:
        assert util.count_decoded_frames('video') == expected
    else:
        with pytest.raises(VideoProbeError):util.count_decoded_frames('video')


@pytest.mark.parametrize('cancel', [True,False])
def test_cancel_timeout_kill_process(monkeypatch,cancel):
    proc=MagicMock();proc.poll.return_value=None
    monkeypatch.setattr(util.subprocess,'Popen',lambda *a,**k:proc)
    with pytest.raises(AnalysisCancelled if cancel else VideoProbeError):
        util.count_decoded_frames('video',lambda:cancel,timeout=0)
    proc.kill.assert_called_once()
    proc.communicate.assert_called_once()


def test_warning_survives_history(tmp_path,result):
    result.video_metadata.frame_count=92
    store=AnalysisStore(tmp_path/'db.sqlite3')
    saved=store.load_task(store.save_result(result))['result']
    assert saved.warnings == result.warnings
    assert '92' in saved.warnings[0] and '90' in saved.warnings[0]
