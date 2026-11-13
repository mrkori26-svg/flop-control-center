import json
from pathlib import Path
from datetime import datetime, timezone
from .runtime_loop import _freshness


def read_agent_work(path, limit=100, now=None, max_age_seconds=10800):
    now = now or datetime.now(timezone.utc)
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
    seen = {}
    for line in target.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            rejected += 1
            continue
        if not isinstance(item, dict) or item.get('schema') != 'flop.observation-record/v1':
            rejected += 1
            continue
        dimensions = item.get('dimensions')
        if item.get('source') != 'runtime' or not isinstance(dimensions, dict) or dimensions.get('kind') != 'agent-work':
            continue
        identity = item.get('id')
        if not isinstance(identity, str) or not identity:
            rejected += 1
            continue
        if identity in seen:
            if seen[identity] != item:
                rejected += 1
            continue
        seen[identity] = item
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

    freshness = _freshness(latest.get('observedAt') if latest else None, now, max_age_seconds)
    if state == 'healthy' and freshness['state'] != 'fresh':
        state = 'stale' if freshness['state'] == 'stale' else 'attention'

    retained = sorted(
        records,
        key=lambda item: (item.get('observedAt') or '', item.get('id') or ''),
    )[-max(1, int(limit)):]
    return {
        'schema': 'flop.agent-work-status.v1',
        'state': state,
        'freshness': freshness,
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
