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
        if item.get('schema') != 'flop.observation-record/v1':
            rejected += 1
            continue
        dimensions = item.get('dimensions')
        if item.get('source') != 'runtime' or not isinstance(dimensions, dict) or dimensions.get('kind') != 'agent-work':
            continue
        records.append(item)

    executions = [item for item in records if item.get('metric') == 'runtime_availability']
    conformance = [item for item in records if item.get('metric') == 'conformance_drift']
    pass_count = sum(1 for item in executions if item.get('outcome') == 'PASS')
    fail_count = sum(1 for item in executions if item.get('outcome') == 'FAIL')
    conformance_fail = sum(1 for item in conformance if item.get('outcome') == 'FAIL')
    unverified_count = sum(1 for item in conformance if item.get('outcome') == 'UNKNOWN')
    latest = max(records, key=lambda item: (item.get('observedAt') or '', item.get('id') or '')) if records else None

    if not executions:
        state = 'empty'
    elif rejected or fail_count or conformance_fail or unverified_count:
        state = 'attention'
    else:
        state = 'healthy'

    retained = sorted(
        records,
        key=lambda item: (item.get('observedAt') or '', item.get('id') or ''),
    )[-max(1, int(limit)):]
    return {
        'schema': 'flop.agent-work-status.v1',
        'state': state,
        'path': str(target),
        'metrics': {
            'work_executions': len(executions),
            'execution_pass': pass_count,
            'execution_fail': fail_count,
            'conformance_pass': sum(1 for item in conformance if item.get('outcome') == 'PASS'),
            'conformance_fail': conformance_fail,
            'unverified': unverified_count,
            'rejected': rejected,
        },
        'latest': latest,
        'records': retained,
        'claim': 'Canonical longitudinal runtime/conformance observations for agent work; no settlement or economic finality is inferred.',
    }
