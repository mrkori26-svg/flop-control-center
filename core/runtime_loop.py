import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MAX_AGE_SECONDS = 3 * 60 * 60
MAX_FUTURE_SKEW_SECONDS = 5 * 60


def _utc_now():
    return datetime.now(timezone.utc)


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _freshness(value, now, max_age_seconds):
    parsed = _parse_time(value)
    if parsed is None:
        return {"state": "invalid", "age_seconds": None}
    age = (now - parsed).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return {"state": "invalid", "age_seconds": age}
    if age > max_age_seconds:
        return {"state": "stale", "age_seconds": age}
    return {"state": "fresh", "age_seconds": max(0, age)}


def read_runtime_loop(path, now=None, max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
    now = now or _utc_now()
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

    history = data.get('history')
    if not isinstance(history, list):
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'invalid',
            'path': str(target),
            'error': 'invalid_history',
            'metrics': {},
            'latest': None,
        }

    metrics = data.get('metrics') or {}
    if not isinstance(metrics, dict):
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'invalid',
            'path': str(target),
            'error': 'invalid_metrics',
            'metrics': {},
            'latest': None,
        }

    if not history:
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'no_data',
            'target_id': data.get('targetId'),
            'test_case_id': data.get('testCaseId'),
            'updated_at': data.get('updatedAt'),
            'freshness': {'state': 'no_data', 'age_seconds': None},
            'metrics': metrics,
            'latest': None,
            'claim': 'Operational runtime evidence only; not normative authority.',
        }

    latest = history[-1]
    if not isinstance(latest, dict):
        return {
            'schema': 'flop.runtime-loop-status.v1',
            'state': 'invalid',
            'path': str(target),
            'error': 'invalid_latest_record',
            'metrics': metrics,
            'latest': None,
        }

    freshness = _freshness(latest.get('observedAt'), now, max_age_seconds)
    latest_status = latest.get('status')
    if freshness['state'] == 'invalid':
        state = 'invalid'
    elif freshness['state'] == 'stale':
        state = 'stale'
    elif latest_status in {'FAIL', 'UNKNOWN', 'DRIFT'} or metrics.get('coverageLostRuns', 0):
        state = 'attention'
    elif latest_status == 'PASS':
        state = 'healthy'
    else:
        state = 'invalid'

    return {
        'schema': 'flop.runtime-loop-status.v1',
        'state': state,
        'target_id': data.get('targetId'),
        'test_case_id': data.get('testCaseId'),
        'updated_at': data.get('updatedAt'),
        'freshness': freshness,
        'metrics': metrics,
        'latest': latest,
        'claim': 'Operational runtime evidence only; not normative authority.',
    }


def read_runtime_index(path, now=None, max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
    now = now or _utc_now()
    result = {
        'schema': 'flop.runtime-public-index-status.v1',
        'state': 'unconfigured',
        'generated_at': None,
        'freshness': {'state': 'unconfigured', 'age_seconds': None},
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

    generated_freshness = _freshness(data.get('generatedAt'), now, max_age_seconds)
    raw_targets = data.get('targets')
    if not isinstance(raw_targets, list):
        return {**result, 'state': 'invalid', 'generated_at': data.get('generatedAt'), 'freshness': generated_freshness, 'error': 'invalid_targets'}

    targets = []
    attention = False
    invalid = False
    stale = False
    for item in raw_targets:
        if not isinstance(item, dict):
            invalid = True
            continue
        status = item.get('currentStatus')
        if status in {'FAIL', 'UNKNOWN', 'DRIFT'}:
            attention = True
        elif status != 'PASS':
            invalid = True
        item_freshness = _freshness(item.get('updatedAt'), now, max_age_seconds)
        if item_freshness['state'] == 'invalid':
            invalid = True
        elif item_freshness['state'] == 'stale':
            stale = True
        windows = {w.get('label'): w.get('metrics', {}) for w in (item.get('windows') or []) if isinstance(w, dict)}
        targets.append({
            'target_id': item.get('targetId'),
            'test_case_id': item.get('testCaseId'),
            'updated_at': item.get('updatedAt'),
            'freshness': item_freshness,
            'status': status,
            'trust_level': item.get('trustLevel'),
            'claim_boundary': item.get('claimBoundary'),
            'overall': item.get('overall') or {},
            'windows': windows,
            'open_incidents': sum(1 for x in (item.get('incidents') or []) if isinstance(x, dict) and not x.get('resolvedAt')),
        })

    if generated_freshness['state'] == 'invalid' or invalid:
        state = 'invalid'
    elif generated_freshness['state'] == 'stale' or stale:
        state = 'stale'
    elif not targets:
        state = 'no_data'
    elif attention:
        state = 'attention'
    else:
        state = 'healthy'

    return {
        **result,
        'state': state,
        'generated_at': data.get('generatedAt'),
        'freshness': generated_freshness,
        'targets': targets,
    }
