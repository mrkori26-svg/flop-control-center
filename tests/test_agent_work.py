import json
from core.agent_work import read_agent_work


def test_agent_work_observatory_summarizes_verified_records(tmp_path):
    path = tmp_path / 'index.ndjson'
    rows = [
        {
            'schema': 'flop.observation-record/v1',
            'source': 'flop-agent',
            'subject': 'work-1',
            'status': 'PASS',
            'observedAt': '2026-09-24T00:00:00Z',
            'evidenceRef': 'bundle-1.json',
            'dimensions': {'route': True, 'execution': True, 'receipt': True, 'verification': True},
        },
        {
            'schema': 'flop.observation-record/v1',
            'source': 'flop-agent',
            'subject': 'work-2',
            'status': 'FAIL',
            'observedAt': '2026-09-24T00:01:00Z',
            'evidenceRef': 'bundle-2.json',
            'dimensions': {'route': True, 'execution': False, 'receipt': True, 'verification': False},
        },
    ]
    path.write_text('\n'.join(json.dumps(x) for x in rows) + '\n', encoding='utf-8')
    result = read_agent_work(path)
    assert result['state'] == 'attention'
    assert result['metrics'] == {'total': 2, 'pass': 1, 'fail': 1, 'rejected': 0}
    assert result['latest']['subject'] == 'work-2'


def test_agent_work_observatory_fails_visible_on_malformed_lines(tmp_path):
    path = tmp_path / 'index.ndjson'
    path.write_text('not-json\n', encoding='utf-8')
    result = read_agent_work(path)
    assert result['state'] == 'empty'
    assert result['metrics']['rejected'] == 1
