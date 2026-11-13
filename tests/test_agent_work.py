import json
from core.agent_work import read_agent_work


def record(metric, outcome, work_id, observed_at):
    return {
        'schema': 'flop.observation-record/v1',
        'id': f'{metric}-{work_id}',
        'observedAt': observed_at,
        'source': 'runtime',
        'metric': metric,
        'outcome': outcome,
        'numerator': 1 if outcome == 'PASS' else 0,
        'denominator': 0 if outcome == 'UNKNOWN' else 1,
        'dimensions': {'kind': 'agent-work', 'workId': work_id},
        'failure': None,
        'evidenceRefs': [f'bundle-{work_id}'],
        'observerRevision': 'abc',
        'sourceRevision': None,
        'targetFingerprint': None,
    }


def test_agent_work_observatory_summarizes_canonical_records(tmp_path):
    path = tmp_path / 'runtime.ndjson'
    rows = [
        record('runtime_availability', 'PASS', 'work-1', '2026-09-24T00:00:00Z'),
        record('conformance_drift', 'PASS', 'work-1', '2026-09-24T00:00:00Z'),
        record('runtime_availability', 'FAIL', 'work-2', '2026-09-24T00:01:00Z'),
        record('conformance_drift', 'UNKNOWN', 'work-2', '2026-09-24T00:01:00Z'),
    ]
    path.write_text('\n'.join(json.dumps(x) for x in rows) + '\n', encoding='utf-8')
    result = read_agent_work(path)
    assert result['state'] == 'attention'
    assert result['metrics'] == {
        'work_executions': 2,
        'execution_pass': 1,
        'execution_fail': 1,
        'conformance_pass': 1,
        'conformance_fail': 0,
        'unverified': 1,
        'rejected': 0,
    }
    assert result['latest']['dimensions']['workId'] == 'work-2'


def test_agent_work_observatory_fails_visible_on_malformed_lines(tmp_path):
    path = tmp_path / 'runtime.ndjson'
    path.write_text('not-json\n', encoding='utf-8')
    result = read_agent_work(path)
    assert result['state'] == 'empty'
    assert result['metrics']['rejected'] == 1

def test_stale_success_is_not_healthy(tmp_path):
    from datetime import datetime, timezone
    path = tmp_path / 'runtime.ndjson'
    path.write_text(json.dumps(record('runtime_availability','PASS','x','2026-01-01T00:00:00Z'))+'\n')
    result=read_agent_work(path, now=datetime(2026,11,13,tzinfo=timezone.utc))
    assert result['state']=='stale'
    assert result['freshness']['state']=='stale'

def test_replayed_observation_does_not_multiply_work(tmp_path):
    path=tmp_path/'runtime.ndjson'
    item=record('runtime_availability','PASS','x','2026-11-13T00:00:00Z')
    path.write_text(json.dumps(item)+'\n'+json.dumps(item)+'\n')
    assert read_agent_work(path)['metrics']['work_executions']==1

def test_nonobject_record_is_visible_instead_of_crashing(tmp_path):
    path=tmp_path/'runtime.ndjson'
    path.write_text('[]\n')
    assert read_agent_work(path)['metrics']['rejected']==1
