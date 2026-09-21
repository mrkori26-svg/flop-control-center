import json
from pathlib import Path


def read_runtime_loop(path):
    if not path:
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'unconfigured',
            'metrics': {},
            'latest': None,
        }
    target = Path(path)
    if not target.exists():
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'missing',
            'path': str(target),
            'metrics': {},
            'latest': None,
        }
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except Exception as exc:
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'invalid',
            'path': str(target),
            'error': str(exc),
            'metrics': {},
            'latest': None,
        }
    if data.get('schema') != 'flop.runtime-loop-state/v1':
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'invalid',
            'path': str(target),
            'error': 'unsupported_schema',
            'metrics': {},
            'latest': None,
        }
    history = data.get('history') or []
    latest = history[-1] if history else None
    metrics = data.get('metrics') or {}
    latest_status = latest.get('status') if isinstance(latest, dict) else None
    state = 'healthy'
    if latest_status in {'FAIL', 'UNKNOWN', 'DRIFT'}:
        state = 'attention'
    if metrics.get('coverageLostRuns', 0):
        state = 'attention'
    return {
        'schema': 'flop.runtime-loop-status.v1',
        'state': state,
        'target_id': data.get('targetId'),
        'test_case_id': data.get('testCaseId'),
        'updated_at': data.get('updatedAt'),
        'metrics': metrics,
        'latest': latest,
        'claim': 'Operational runtime evidence only; not normative authority.',
    }
