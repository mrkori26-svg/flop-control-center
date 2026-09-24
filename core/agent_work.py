import json
from pathlib import Path


def read_agent_work(path, limit=100):
    if not path:
        return {
            'schema': 'flop.agent-work-status.v1',
            'state': 'unconfigured',
            'metrics': {},
            'latest': None,
            'records': [],
        }
    target = Path(path)
    if not target.exists():
        return {
            'schema': 'flop.agent-work-status.v1',
            'state': 'missing',
            'path': str(target),
            'metrics': {},
            'latest': None,
            'records': [],
        }

    records = []
    rejected = 0
    for line in target.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            rejected += 1
            continue
        if item.get('schema') != 'flop.observation-record/v1' or item.get('source') != 'flop-agent':
            rejected += 1
            continue
        records.append(item)

    retained = records[-max(1, int(limit)):]
    pass_count = sum(1 for item in records if item.get('status') == 'PASS')
    fail_count = sum(1 for item in records if item.get('status') == 'FAIL')
    unverified_count = sum(
        1 for item in records
        if not isinstance(item.get('dimensions'), dict) or item['dimensions'].get('verification') is not True
    )
    latest = records[-1] if records else None
    state = 'healthy'
    if rejected or fail_count or unverified_count or not latest:
        state = 'attention' if records else 'empty'
    return {
        'schema': 'flop.agent-work-status.v1',
        'state': state,
        'path': str(target),
        'metrics': {
            'total': len(records),
            'pass': pass_count,
            'fail': fail_count,
            'unverified': unverified_count,
            'rejected': rejected,
        },
        'latest': latest,
        'records': retained,
        'claim': 'Execution observations and independent verification status; no settlement or economic finality is inferred.',
    }
