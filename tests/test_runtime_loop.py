import json
import tempfile
import unittest
from pathlib import Path

from core.runtime_loop import read_runtime_loop


class RuntimeLoopTests(unittest.TestCase):
    def write_state(self, latest_status='PASS', coverage_lost=0):
        root = Path(tempfile.mkdtemp())
        path = root / 'state.json'
        state = {
            'schema': 'flop.runtime-loop-state/v1',
            'targetId': 'reference-f1',
            'testCaseId': 'direct-rail-f1-reference',
            'updatedAt': '2026-09-21T23:00:00Z',
            'historyLimit': 168,
            'history': [{
                'runId': 'r1',
                'targetId': 'reference-f1',
                'testCaseId': 'direct-rail-f1-reference',
                'status': latest_status,
                'observedAt': '2026-09-21T23:00:00Z',
                'attempts': 1,
                'transientErrors': 0,
                'recovered': False,
                'coverageLost': coverage_lost > 0,
                'durationMs': 10,
            }],
            'metrics': {
                'runs': 1,
                'pass': 1 if latest_status == 'PASS' else 0,
                'fail': 1 if latest_status == 'FAIL' else 0,
                'drift': 1 if latest_status == 'DRIFT' else 0,
                'unknown': 1 if latest_status == 'UNKNOWN' else 0,
                'attempts': 1,
                'transientErrors': 0,
                'recoveredRuns': 0,
                'coverageLostRuns': coverage_lost,
                'recoveryRate': None,
                'coverageRate': 0 if coverage_lost else 1,
                'currentFailureStreak': 0 if latest_status == 'PASS' else 1,
                'maxFailureStreak': 0 if latest_status == 'PASS' else 1,
            },
        }
        path.write_text(json.dumps(state), encoding='utf-8')
        return path

    def test_pass_without_coverage_loss_is_healthy(self):
        result = read_runtime_loop(self.write_state())
        self.assertEqual(result['state'], 'healthy')
        self.assertEqual(result['metrics']['coverageRate'], 1)
        self.assertIn('not normative authority', result['claim'])

    def test_unknown_or_coverage_loss_requires_attention(self):
        self.assertEqual(read_runtime_loop(self.write_state('UNKNOWN'))['state'], 'attention')
        self.assertEqual(read_runtime_loop(self.write_state('PASS', 1))['state'], 'attention')


if __name__ == '__main__':
    unittest.main()
