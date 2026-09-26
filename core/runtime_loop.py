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


def read_runtime_index(path):
    result = {
        'schema': 'flop.runtime-public-index-status.v1',
        'state': 'unconfigured',
        'generated_at': None,
        'targets': [],
        'claim': 'Runtime status windows are operational evidence, not normative authority.',
    }
    if not path:
        return result
    target = Path(path)
    if not target.exists():
        return {**result, 'state': 'missing', 'path': str(target)}
    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except Exception as exc:
        return {**result, 'state': 'invalid', 'path': str(target), 'error': str(exc)}
    if data.get('schema') != 'flop.runtime-public-index/v1':
        return {**result, 'state': 'invalid', 'path': str(target), 'error': 'unsupported_schema'}
    targets = []
    attention = False
    for item in data.get('targets') or []:
        if not isinstance(item, dict):
            continue
        status = item.get('currentStatus')
        if status in {'FAIL', 'UNKNOWN', 'DRIFT'}:
            attention = True
        windows = {w.get('label'): w.get('metrics', {}) for w in (item.get('windows') or []) if isinstance(w, dict)}
        targets.append({
            'target_id': item.get('targetId'),
            'test_case_id': item.get('testCaseId'),
            'updated_at': item.get('updatedAt'),
            'status': status,
            'trust_level': item.get('trustLevel'),
            'claim_boundary': item.get('claimBoundary'),
            'overall': item.get('overall') or {},
            'windows': windows,
            'open_incidents': sum(1 for x in (item.get('incidents') or []) if isinstance(x, dict) and not x.get('resolvedAt')),
        })
    return {
        **result,
        'state': 'attention' if attention else 'healthy',
        'generated_at': data.get('generatedAt'),
        'targets': targets,
    }
