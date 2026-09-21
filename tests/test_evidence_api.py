import unittest
from core.evidence_api import make_record, validate_record, classify_for_operator, validate_envelope, envelope_to_record


class EvidenceApiTests(unittest.TestCase):
    def test_community_cannot_be_normative(self):
        record = {
            'source': 'peer', 'source_class': 'community', 'claim_type': 'drift',
            'observed_at': '2026-09-17T04:00:00+00:00', 'freshness': {'state': 'fresh'},
            'evidence': {'url': 'https://example.test'}, 'verification_state': 'observed',
            'authority': {'official': False, 'normative': True, 'grants_action_authority': False},
        }
        self.assertEqual(validate_record(record)['error'], 'community_cannot_be_normative')

    def test_local_source_cannot_claim_official(self):
        record = {
            'source': 'local', 'source_class': 'local', 'claim_type': 'runtime',
            'observed_at': '2026-09-17T04:00:00+00:00', 'freshness': {'state': 'fresh'},
            'evidence': {}, 'verification_state': 'observed',
            'authority': {'official': True, 'normative': False, 'grants_action_authority': False},
        }
        self.assertEqual(validate_record(record)['error'], 'non_official_source_cannot_claim_official')

    def test_community_signal_is_review_only(self):
        record = make_record(
            source='ksk7777m/flop-agent-intelligence', source_class='community', claim_type='spec_drift',
            observed_at='2026-09-17T04:00:00+00:00', freshness={'state': 'fresh', 'age_seconds': 30},
            evidence={'ref': 'example'}, summary='possible drift')
        self.assertEqual(classify_for_operator(record), 'REVIEW')
        self.assertFalse(record['authority']['grants_action_authority'])

    def test_verified_official_still_requires_review(self):
        record = make_record(
            source='flop-labs', source_class='official', claim_type='spec_revision',
            observed_at='2026-09-17T04:00:00+00:00', freshness={'state': 'fresh'},
            evidence={'revision': 'abc'}, verification_state='verified',
            authority={'official': True, 'normative': False, 'grants_action_authority': False})
        self.assertEqual(classify_for_operator(record), 'REVIEW_OFFICIAL')


    def test_portable_envelope_converts_without_action_or_normative_authority(self):
        envelope = {
            'schema': 'flop.evidence-envelope.v1',
            'subject': {'kind': 'runtime', 'id': 'reference-f1'},
            'source': {
                'uri': 'repo:retardio73-boop/flop-conformance-lab',
                'sourceClass': 'LOCAL',
                'observedAt': '2026-09-21T21:00:00Z',
            },
            'payload': {'type': 'flop.runtime-evidence-bundle/v1', 'value': {'status': 'PASS'}},
            'verification': {'state': 'VERIFIED', 'verifier': 'lab', 'checks': [{'id': 'shape', 'ok': True}]},
            'claims': [{'type': 'runtime-conformance', 'value': 'reference-only', 'normative': False}],
            'limitations': ['not a public FLOP runtime'],
            'provenance': [],
            'canonical': '{}',
            'sha256': 'a' * 64,
        }
        self.assertTrue(validate_envelope(envelope)['ok'])
        record = envelope_to_record(envelope)
        self.assertEqual(record['source_class'], 'local')
        self.assertEqual(record['verification_state'], 'verified')
        self.assertFalse(record['authority']['normative'])
        self.assertFalse(record['authority']['grants_action_authority'])
        self.assertEqual(classify_for_operator(record), 'REVIEW')

    def test_non_official_envelope_cannot_claim_normative(self):
        envelope = {
            'schema': 'flop.evidence-envelope.v1',
            'subject': {'kind': 'proposal', 'id': 'checkpoint'},
            'source': {
                'uri': 'repo:peer/example',
                'sourceClass': 'COMMUNITY',
                'observedAt': '2026-09-21T21:00:00Z',
            },
            'payload': {'type': 'proposal', 'value': {}},
            'verification': {'state': 'OBSERVED', 'verifier': 'peer'},
            'claims': [{'type': 'normative', 'value': True, 'normative': True}],
            'canonical': '{}',
            'sha256': 'b' * 64,
        }
        self.assertEqual(validate_envelope(envelope)['error'], 'non_official_envelope_cannot_be_normative')


if __name__ == '__main__':
    unittest.main()
