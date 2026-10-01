import unittest

from core.recovery import external_readiness


class ExternalReadinessTests(unittest.TestCase):
    def components(self, state='healthy', freshness='fresh'):
        return {
            'passport': {'state': state, 'freshness_status': freshness},
            'kibble_compliance': {'state': 'healthy', 'freshness_status': 'fresh'},
        }

    def test_current_healthy_dependencies_are_ready(self):
        self.assertEqual(external_readiness(self.components()), 'ready')

    def test_stale_evidence_is_unknown(self):
        self.assertEqual(external_readiness(self.components('stale', 'stale')), 'unknown')

    def test_missing_or_invalid_evidence_is_unknown(self):
        self.assertEqual(external_readiness(self.components('blocked', 'unknown')), 'unknown')

    def test_stale_kibble_is_unknown(self):
        data = self.components()
        data['kibble_compliance'] = {'state': 'stale', 'freshness_status': 'stale'}
        self.assertEqual(external_readiness(data), 'unknown')

    def test_current_external_block_remains_blocked(self):
        data = self.components('stale', 'stale')
        data['kibble_compliance']['state'] = 'blocked_external'
        self.assertEqual(external_readiness(data), 'blocked_external')

    def test_current_direct_gate_remains_nonblocking(self):
        self.assertEqual(external_readiness(self.components('telemetry_stale')), 'ready')

    def test_unhealthy_dependency_is_not_ready(self):
        self.assertEqual(external_readiness(self.components('degraded')), 'unknown')


if __name__ == '__main__':
    unittest.main()
