"""Read-only integration of existing runtime owners; never starts workers."""
import json
from datetime import datetime, timezone
from pathlib import Path
from core.runtime_loop import _freshness


def _load_json(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def observe(path, max_age=10800):
    path = Path(path)
    result = {'source': str(path), 'state': 'blocked', 'freshness_age': None,
              'last_success': None, 'last_error': None}
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('SOURCE_TOO_LARGE')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise ValueError('EXPECTED_OBJECT')
        stamp = next((data.get(k) for k in ('at', 'checkedAt', 'generatedAt', 'updatedAt') if data.get(k)), None)
        fresh = _freshness(stamp, datetime.now(timezone.utc), max_age)
        status = data.get('status', data.get('state'))
        failed = data.get('healthy') is False or status in ('DEGRADED', 'FAIL', 'SEARCH_UNAVAILABLE', 'PARTIAL') or bool(data.get('error'))
        result.update(state='healthy' if fresh['state'] == 'fresh' and not failed else 'degraded',
                      freshness_age=fresh['age_seconds'], freshness=fresh['state'],
                      last_success=data.get('last_success', data.get('lastSuccess')),
                      last_error=data.get('last_error', data.get('lastError', data.get('error'))),
                      data=data)
        if result['state'] == 'healthy' and status in ('HEALTHY', 'COMPLETE'):
            result['last_success'] = result['last_success'] or stamp
        if failed and not result['last_error']:
            result['last_error'] = status or 'REPORTED_UNHEALTHY'
    except (OSError, ValueError, TypeError) as exc:
        result['last_error'] = type(exc).__name__ + ': ' + str(exc)
    return result


def snapshot(cfg):
    root = Path(cfg['_root'])
    live = Path(cfg.get('runtime_root', root))
    worker = live / 'useful-work-operator'
    lab = live / 'flop-conformance-lab'
    sources = {
        'operator': (worker / 'state/operator-supervisor-heartbeat.json', 180),
        'ecosystem': (worker / 'ecosystem/ecosystem-supervisor-heartbeat.json', 180),
        'blockrewards': (worker / 'state-blockrewards-0-of-1/status.json', 180),
        'harness': (worker / 'state-harness-0-of-1/status.json', 180),
        'kibble': (worker / 'state/status.json', 180),
        'passport': (worker / 'ecosystem/harness/state/qualification.json', 600),
        'observatory': (lab / '.runtime/observatory-supervisor.json', 10800),
        'runtime_evidence': (lab / '.runtime/runtime-health.json', 10800),
        'adoption_watch': (Path.home() / 'AppData/Local/FLOP/adoption/latest.json', 10800),
        'longitudinal': (live / '_publish/longitudinal-evidence-v1/runtime-public/longitudinal/latest.json', 10800),
    }
    components = {name: observe(path, age) for name, (path, age) in sources.items()}

    qualification = components['passport'].get('data', {})
    published = qualification.get('published', {})
    passport_ok = bool(
        published.get('upstreamFresh') is True
        and published.get('passportPresent') is True
        and published.get('provisional') is False
        and isinstance(published.get('passes'), (int, float))
        and published['passes'] >= 3
    )
    if components['passport']['state'] == 'healthy' and not passport_ok:
        components['passport']['state'] = 'blocked_external'
        components['passport']['last_error'] = 'PASSPORT_NOT_CURRENTLY_PUBLISHED'
        components['passport']['blocker'] = {
            'type': 'EXTERNAL_PUBLICATION',
            'upstreamFresh': published.get('upstreamFresh'),
            'passportPresent': published.get('passportPresent'),
            'publishedPasses': published.get('passes'),
            'passportAsOf': published.get('passportAsOf'),
            'tapeAsOf': published.get('tapeAsOf'),
        }

    kibble_state_path = worker / 'state/kibble-handled.json'
    kibble_state = _load_json(kibble_state_path) or {}
    counts = {}
    for entry in kibble_state.values():
        status = str(entry.get('status', 'UNKNOWN')) if isinstance(entry, dict) else 'UNKNOWN'
        counts[status] = counts.get(status, 0) + 1
    legacy_unverified = counts.get('SUBMITTED_LEGACY_UNVERIFIED', 0)
    submitted_unverified = counts.get('SUBMITTED', 0) + counts.get('SUBMITTED_CONFIRMED', 0)
    delivery_retry = counts.get('DELIVERY_RETRY', 0)
    components['kibble']['submission_integrity'] = {
        'stateFile': str(kibble_state_path),
        'counts': counts,
        'legacyUnverified': legacy_unverified,
        'submittedWithoutAcceptanceEvidence': submitted_unverified,
        'activeDeliveryRetries': delivery_retry,
        'warning': 'Historical/unaccepted submissions are retained as evidence and never promoted to DELIVERED/PASS.',
        'rule': 'A posted RESULT is submission evidence, not proof of artifact creation, acceptance, receipt, or PASS.'
    }
    if components['kibble']['state'] == 'healthy' and delivery_retry > 0:
        components['kibble']['state'] = 'attention'
        components['kibble']['last_error'] = 'KIBBLE_DELIVERY_RETRY_ACTIVE'

    metrics = {}
    for name in ('blockrewards', 'harness'):
        tracker = components[name].get('data', {}).get('passTracker', {})
        for key in ('pass', 'fail', 'pending', 'receipts'):
            metrics[f'{name}.locally_observed_payer.{key}'] = tracker.get(key)
    metrics['passport.externally_published.pass'] = published.get('passes')
    metrics['passport.externally_accepted'] = passport_ok
    metrics['kibble.legacy_unverified'] = legacy_unverified
    metrics['kibble.submitted_without_acceptance'] = submitted_unverified
    adoption = components['adoption_watch'].get('data', {})
    metrics['adoption.independent_verified'] = bool(adoption.get('classification') == 'VERIFIED_EXTERNAL_ADOPTION')

    internal_problem = any(v['state'] in {'degraded', 'blocked', 'attention'} for v in components.values())
    external_block = any(v['state'] == 'blocked_external' for v in components.values())
    overall = 'degraded' if internal_problem else ('blocked_external' if external_block else 'healthy')
    manifest = _load_json(live / 'STACK_MANIFEST.json') or {}
    inventory = {
        name: {
            'lifecycle': spec.get('lifecycle', 'UNKNOWN'),
            **({'path': spec['path']} if isinstance(spec, dict) and spec.get('path') else {}),
            **({'lane': spec['lane']} if isinstance(spec, dict) and spec.get('lane') else {}),
            **({'checkoutMode': spec['checkoutMode']} if isinstance(spec, dict) and spec.get('checkoutMode') else {}),
            **({'pinnedCommit': spec['pinnedCommit']} if isinstance(spec, dict) and spec.get('pinnedCommit') else {}),
        }
        for name, spec in (manifest.get('components') or {}).items()
        if isinstance(spec, dict)
    }
    return {
        'schema': 'flop.stack-recovery-live/v2',
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'state': overall,
        'authority': 'flop-control-center',
        'read_only': True,
        'components': components,
        'inventory': inventory,
        'metrics': metrics,
        'eligibility': {
            'local_evidence': qualification.get('effective'),
            'externally_published': published,
            'externally_accepted': passport_ok,
            'claim_boundary': 'Local payer observations do not establish current external passport eligibility or settlement.'
        },
        'failure_taxonomy': [
            'SOURCE_MISSING', 'SOURCE_INVALID', 'SOURCE_STALE', 'DEPENDENCY_UNAVAILABLE',
            'EXTERNAL_PUBLICATION_BLOCKED', 'INELIGIBLE', 'UNSOLVABLE', 'PREBUILD_FAILED',
            'CLAIM_REJECTED', 'DELIVERY_FAILED', 'ACCEPTANCE_UNCONFIRMED', 'RECEIPT_MISSING'
        ],
    }
