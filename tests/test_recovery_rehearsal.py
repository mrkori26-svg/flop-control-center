import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from core.recovery import snapshot
from tools.cold_boot_recovery_proof import reconstructed_local_health


class RecoveryRehearsalTests(unittest.TestCase):
    def state(self):
        return {'freshness_status': 'fresh', 'components': {
            name: {'state': 'healthy', 'freshness_status': 'fresh'}
            for name in ('operator', 'ecosystem', 'root_audit', 'probe', 'signer', 'observatory')
        }}

    def test_only_self_reference_may_be_excluded(self):
        state = self.state()
        state['components']['recovery_proof'] = {'state': 'degraded', 'freshness_status': 'fresh'}
        self.assertTrue(reconstructed_local_health(state))
        state['components']['probe']['state'] = 'stale'
        self.assertFalse(reconstructed_local_health(state))

    def test_missing_components_fail_closed(self):
        state = self.state()
        del state['components']['operator']
        self.assertFalse(reconstructed_local_health(state))
        self.assertFalse(reconstructed_local_health({}))

    def test_external_block_remains_separate(self):
        state = self.state()
        state['components']['passport'] = {'state': 'blocked_external', 'freshness_status': 'fresh'}
        self.assertTrue(reconstructed_local_health(state))
        state['components']['passport']['freshness_status'] = 'stale'
        self.assertFalse(reconstructed_local_health(state))

    def test_running_or_incomplete_proof_does_not_certify_health(self):
        for status in ('RUNNING', 'PASS'):
            def observed(path, age):
                return {'state': 'healthy', 'freshness_status': 'fresh', 'data': {
                    'status': status, 'finishedAt': datetime.now(timezone.utc).isoformat(), 'checks': {}
                }}
            with patch('core.recovery.observe', side_effect=observed):
                result = snapshot({'_root': '.'})
            self.assertEqual(result['components']['recovery_proof']['state'], 'degraded')
            self.assertEqual(result['state'], 'degraded')


if __name__ == '__main__':
    unittest.main()
