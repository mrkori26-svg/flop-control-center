import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from core.evidence_api import make_record

MAX_BYTES = 256_000
TIMEOUT_SECONDS = 4

PEERS = {
    'evidence_scout': {
        'project': 'FLOP Evidence Scout',
        'author': 'Mariukasfak',
        'url': 'https://raw.githubusercontent.com/Mariukasfak/flop-evidence-scout/main/docs/freshness.json',
        'adapter': 'freshness',
    },
    'openagentsearch_liveness': {
        'project': 'OpenAgentSearch Liveness',
        'author': 'djd39448',
        'url': 'https://openagentsearch.trustcoresystems.workers.dev/liveness',
        'adapter': 'openagentsearch_liveness',
    },
    'agent_intelligence': {
        'project': 'FLOP Agent Intelligence',
        'author': 'ksk7777m',
        'url': 'https://raw.githubusercontent.com/ksk7777m/flop-agent-intelligence/main/api/status.json',
        'adapter': 'status',
    },
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, 'redirect blocked', headers, fp)

def _fetch_json(name, opener=None):
    if name not in PEERS:
        raise ValueError('unknown_peer')
    peer = PEERS[name]
    client = opener or build_opener(NoRedirect())
    req = Request(peer['url'], headers={
        'Accept': 'application/json',
        'User-Agent': 'flop-control-center/peer-evidence-v1',
    })
    response = client.open(req, timeout=TIMEOUT_SECONDS)
    try:
        length = response.headers.get('Content-Length')
        if length and int(length) > MAX_BYTES:
            raise ValueError('peer_payload_too_large')
        raw = response.read(MAX_BYTES + 1)
    finally:
        response.close()
    if len(raw) > MAX_BYTES:
        raise ValueError('peer_payload_too_large')
    return json.loads(raw.decode('utf-8'))


def _authority():
    return {'official': False, 'normative': False, 'grants_action_authority': False}

def _evidence_scout_record(data):
    checked = data.get('checkedAt')
    artefacts = data.get('artefacts') or []
    stale = int(data.get('stale') or 0)
    evidence = {
        'schema': 'flop-evidence-scout/freshness.json',
        'stale_count': stale,
        'artefacts': [
            {
                'id': item.get('id'),
                'state': item.get('state'),
                'age_min': item.get('ageMin'),
                'duty_ratio': (item.get('duty') or {}).get('ratio'),
                'worst_gap_min': (item.get('duty') or {}).get('worstGapMin'),
            }
            for item in artefacts[:16]
        ],
    }
    return make_record(
        source='Mariukasfak/flop-evidence-scout', source_class='community',
        claim_type='continuity_observation', observed_at=checked,
        freshness={'state': 'reported', 'stale_count': stale}, evidence=evidence,
        verification_state='reported', authority=_authority(),
        summary='Peer-reported freshness and duty-cycle evidence; requires independent review.',
        tags=['peer', 'continuity', 'credit:Mariukasfak'])


def _openagentsearch_liveness_record(data):
    counts = data.get('counts') or {}
    rooms = counts.get('rooms_by_class') or {}
    agents = counts.get('agents_by_tier') or {}
    evidence = {
        'schema': data.get('schema'),
        'generated_at': data.get('generated_at'),
        'window_days': data.get('window_days'),
        'log_rows': data.get('log_rows'),
        'ledger_generated_at': data.get('ledger_generated_at'),
        'rooms_by_class': {
            key: rooms.get(key)
            for key in ('live', 'mixed', 'quiet', 'farm', 'flood', 'unknown')
            if key in rooms
        },
        'agents_by_tier': {
            key: agents.get(key)
            for key in ('live', 'likely_live', 'weak', 'farm', 'unknown')
            if key in agents
        },
    }
    return make_record(
        source='djd39448/openagentsearch', source_class='community',
        claim_type='liveness_observation', observed_at=data.get('generated_at'),
        freshness={'state': 'reported'}, evidence=evidence,
        verification_state='reported', authority=_authority(),
        summary='OpenAgentSearch public liveness classification; observational only and never an assurance, identity, eligibility, or ranking upgrade.',
        tags=['peer', 'liveness', 'observational-only', 'credit:djd39448'])


def _agent_intelligence_record(data):
    observed = data.get('reviewed_at') or data.get('generated_at')
    warnings = [str(x) for x in (data.get('warnings') or [])[:12]]
    evidence = {
        'schema': data.get('schema'),
        'snapshot_classification': data.get('snapshot_classification'),
        'source_status': data.get('source_status'),
        'official_spec_status': data.get('official_spec_status'),
        'compatibility': data.get('compatibility') or {},
        'warnings': warnings,
        'external_writes': data.get('external_writes'),
    }
    return make_record(
        source='ksk7777m/flop-agent-intelligence', source_class='community',
        claim_type='observatory_status', observed_at=observed,
        freshness={'state': 'reported'}, evidence=evidence,
        verification_state='reported', authority=_authority(),
        summary='Peer observatory status; historical/currentness caveats are preserved.',
        tags=['peer', 'observatory', 'credit:ksk7777m'])

def collect(names=None, opener=None):
    selected = names or list(PEERS)
    records, errors = [], []
    for name in selected:
        try:
            data = _fetch_json(name, opener=opener)
            if PEERS[name]['adapter'] == 'freshness':
                records.append(_evidence_scout_record(data))
            elif PEERS[name]['adapter'] == 'openagentsearch_liveness':
                records.append(_openagentsearch_liveness_record(data))
            elif PEERS[name]['adapter'] == 'status':
                records.append(_agent_intelligence_record(data))
            else:
                raise ValueError('unsupported_peer_adapter')
        except (ValueError, json.JSONDecodeError, HTTPError, URLError, TimeoutError) as exc:
            errors.append({
                'peer': name,
                'project': PEERS.get(name, {}).get('project'),
                'error': type(exc).__name__,
                'detail': str(exc)[:160],
            })
    return {
        'records': records,
        'errors': errors,
        'claim': 'Peer records are read-only community evidence and never grant protocol or action authority.',
    }
