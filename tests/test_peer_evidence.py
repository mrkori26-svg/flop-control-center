import io
import json
import unittest

from adapters.peer_evidence import collect


class _Response:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode('utf-8')
        self.headers = {'Content-Length': str(len(self._raw))}
    def read(self, size=-1):
        return self._raw[:size] if size >= 0 else self._raw
    def close(self):
        pass


class _Opener:
    def __init__(self, payloads):
        self.payloads = payloads
    def open(self, req, timeout=None):
        url = req.full_url
        if 'flop-evidence-scout' in url:
            return _Response(self.payloads['evidence_scout'])
        if 'openagentsearch' in url:
            return _Response(self.payloads['openagentsearch_liveness'])
        return _Response(self.payloads['agent_intelligence'])


class PeerEvidenceTests(unittest.TestCase):
    def test_peer_records_are_review_only(self):
        payloads = {
            'evidence_scout': {
                'checkedAt': '2026-09-14T14:05:12.334Z',
                'stale': 1,
                'artefacts': [{'id':'daemon','state':'STALE','ageMin':205.2,'duty':{'ratio':0.06,'worstGapMin':2813.6}}],
            },
            'openagentsearch_liveness': {
                'schema':'openagentsearch.liveness-compact/1',
                'generated_at':'2026-09-19T08:36:57Z',
                'window_days':7,
                'log_rows':626217,
                'ledger_generated_at':'2026-09-19T08:36:50Z',
                'counts':{
                    'rooms_by_class':{'live':2,'mixed':2,'quiet':7,'farm':15,'flood':9,'unknown':3},
                    'agents_by_tier':{'live':8,'likely_live':229,'weak':2055,'farm':4384,'unknown':11157},
                },
            },
            'agent_intelligence': {
                'schema':'technocore-observatory-status-v1',
                'reviewed_at':'2026-09-11T03:29:35Z',
                'snapshot_classification':'HISTORICAL_SNAPSHOT',
                'source_status':'OFFICIAL',
                'official_spec_status':'HISTORICAL_SNAPSHOT_NOT_CURRENT',
                'compatibility':{'action':'NO_LIVE_ACTION'},
                'warnings':['historical'],
                'external_writes':0,
            },
        }
        out = collect(opener=_Opener(payloads))
        self.assertEqual(len(out['records']), 3)
        liveness = next(r for r in out['records'] if r['source'] == 'djd39448/openagentsearch')
        self.assertEqual(liveness['claim_type'], 'liveness_observation')
        self.assertEqual(liveness['evidence']['rooms_by_class']['live'], 2)
        self.assertEqual(liveness['evidence']['agents_by_tier']['live'], 8)
        self.assertFalse(liveness['authority']['official'])
        self.assertFalse(liveness['authority']['normative'])
        self.assertFalse(liveness['authority']['grants_action_authority'])
        for record in out['records']:
            self.assertEqual(record['source_class'], 'community')
            self.assertFalse(record['authority']['official'])
            self.assertFalse(record['authority']['normative'])
            self.assertFalse(record['authority']['grants_action_authority'])
