from datetime import datetime, timezone
import json
from pathlib import Path


def read_buyer_evidence(path):
    if not path:
        return classify_buyer_attribution(None)
    try:
        evidence = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return {'status': 'UNKNOWN', 'reason': 'BUYER_EVIDENCE_UNAVAILABLE', 'rewardEligible': False}
    return classify_buyer_attribution(evidence)

ALLOWED_SOURCE_CLASSES = {'official', 'community', 'local'}
ALLOWED_VERIFICATION_STATES = {'verified', 'observed', 'reported', 'unknown', 'invalid'}


def classify_buyer_attribution(buyer_evidence):
    """Fail-closed consumer of Router buyer-evidence/v1; never confers a reward claim."""
    if not isinstance(buyer_evidence, dict) or buyer_evidence.get('schema') != 'flop-router/buyer-evidence/v1':
        return {'status': 'UNKNOWN', 'reason': 'UNSUPPORTED_OR_MISSING_BUYER_EVIDENCE', 'rewardEligible': False}
    assessment = buyer_evidence.get('attributionAssessment')
    if not isinstance(assessment, dict) or assessment.get('status') not in {'PASS', 'FAIL', 'UNKNOWN'}:
        return {'status': 'UNKNOWN', 'reason': 'ATTRIBUTION_ASSESSMENT_MISSING', 'rewardEligible': False}
    if assessment.get('rewardEligibility') != 'UNKNOWN' or assessment.get('economicExecutionAllowed') is not False:
        return {'status': 'UNKNOWN', 'reason': 'UNSAFE_ATTRIBUTION_CLAIM', 'rewardEligible': False}
    return {'status': assessment['status'], 'reason': 'LOCAL_PROVISIONAL_SETTLEMENT_TRIAGE', 'rewardEligible': False}


def _iso(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.astimezone(timezone.utc).isoformat()


def validate_record(record):
    required = ['source', 'source_class', 'claim_type', 'observed_at', 'freshness', 'evidence', 'verification_state', 'authority']
    missing = [key for key in required if key not in record]
    if missing:
        return {'ok': False, 'error': 'missing_fields', 'fields': missing}
    if record['source_class'] not in ALLOWED_SOURCE_CLASSES:
        return {'ok': False, 'error': 'invalid_source_class'}
    if record['verification_state'] not in ALLOWED_VERIFICATION_STATES:
        return {'ok': False, 'error': 'invalid_verification_state'}
    authority = record.get('authority') or {}
    if record['source_class'] == 'community' and authority.get('normative') is True:
        return {'ok': False, 'error': 'community_cannot_be_normative'}
    if record['source_class'] != 'official' and authority.get('official') is True:
        return {'ok': False, 'error': 'non_official_source_cannot_claim_official'}
    return {'ok': True}


def make_record(*, source, source_class, claim_type, observed_at, freshness, evidence, verification_state='observed', authority=None, summary=None, tags=None):
    record = {
        'schema': 'flop.evidence.v1',
        'source': source,
        'source_class': source_class,
        'claim_type': claim_type,
        'observed_at': _iso(observed_at),
        'freshness': freshness,
        'evidence': evidence,
        'verification_state': verification_state,
        'authority': authority or {'official': source_class == 'official', 'normative': False, 'grants_action_authority': False},
        'summary': summary,
        'tags': tags or [],
    }
    verdict = validate_record(record)
    if not verdict['ok']:
        raise ValueError(verdict['error'])
    return record


def classify_for_operator(record):
    verdict = validate_record(record)
    if not verdict['ok']:
        return 'REJECT'
    if record['source_class'] == 'official' and record['verification_state'] == 'verified':
        return 'REVIEW_OFFICIAL'
    if record['verification_state'] in {'invalid', 'unknown'}:
        return 'ATTENTION'
    return 'REVIEW'


def validate_envelope(envelope):
    required = ['schema', 'subject', 'source', 'payload', 'verification', 'canonical', 'sha256']
    missing = [key for key in required if key not in envelope]
    if missing:
        return {'ok': False, 'error': 'envelope_missing_fields', 'fields': missing}
    if envelope.get('schema') != 'flop.evidence-envelope.v1':
        return {'ok': False, 'error': 'unsupported_envelope_schema'}
    source = envelope.get('source') or {}
    source_class = str(source.get('sourceClass', '')).lower()
    if source_class not in ALLOWED_SOURCE_CLASSES:
        return {'ok': False, 'error': 'invalid_envelope_source_class'}
    verification = envelope.get('verification') or {}
    verification_state = str(verification.get('state', '')).lower()
    if verification_state not in ALLOWED_VERIFICATION_STATES:
        return {'ok': False, 'error': 'invalid_envelope_verification_state'}
    claims = envelope.get('claims') or []
    if source_class != 'official' and any(claim.get('normative') is True for claim in claims if isinstance(claim, dict)):
        return {'ok': False, 'error': 'non_official_envelope_cannot_be_normative'}
    digest = envelope.get('sha256')
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
        return {'ok': False, 'error': 'invalid_envelope_digest'}
    return {'ok': True}


def envelope_to_record(envelope, freshness=None):
    verdict = validate_envelope(envelope)
    if not verdict['ok']:
        raise ValueError(verdict['error'])
    source = envelope['source']
    payload = envelope['payload']
    verification = envelope['verification']
    source_class = source['sourceClass'].lower()
    verification_state = verification['state'].lower()
    subject = envelope.get('subject') or {}
    return make_record(
        source=source['uri'],
        source_class=source_class,
        claim_type=payload.get('type') or subject.get('kind') or 'evidence_envelope',
        observed_at=source['observedAt'],
        freshness=freshness or {'state': 'unknown', 'freshness_ms': source.get('freshnessMs')},
        evidence={
            'schema': envelope['schema'],
            'subject': subject,
            'payload': payload,
            'verification': verification,
            'claims': envelope.get('claims') or [],
            'limitations': envelope.get('limitations') or [],
            'provenance': envelope.get('provenance') or [],
            'sha256': envelope['sha256'],
        },
        verification_state=verification_state,
        authority={
            'official': source_class == 'official',
            'normative': False,
            'grants_action_authority': False,
        },
        summary='Portable evidence envelope',
        tags=['evidence-envelope-v1'],
    )
