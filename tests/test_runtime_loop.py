import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.runtime_loop import read_runtime_loop


NOW = datetime(2026, 9, 21, 23, 30, tzinfo=timezone.utc)


class RuntimeLoopTests(unittest.TestCase):
    def write_state(self, latest_status='PASS', coverage_lost=0, observed_at='2026-09-21T23:00:00Z', history=True):
        root = Path(tempfile.mkdtemp())
        path = root / 'state.json'
        entries = [{
            'runId': 'r1',
            'targetId': 'reference-f1',
            'testCaseId': 'direct-rail-f1-reference',
            'status': latest_status,
            'observedAt': observed_at,
            'attempts': 1,
            'transientErrors': 0,
            'recovered': False,
            'coverageLost': coverage_lost > 0,
            'durationMs': 10,
        }] if history else []
        state = {
            'schema': 'flop.runtime-loop-state/v1',
            'targetId': 'reference-f1',
            'testCaseId': 'direct-rail-f1-reference',
            'updatedAt': observed_at,
            'historyLimit': 168,
            'history': entries,
            'metrics': {
                'runs': len(entries),
                'pass': 1 if history and latest_status == 'PASS' else 0,
                'fail': 1 if history and latest_status == 'FAIL' else 0,
                'drift': 1 if history and latest_status == 'DRIFT' else 0,
                'unknown': 1 if history and latest_status == 'UNKNOWN' else 0,
                'attempts': len(entries),
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
        result = read_runtime_loop(self.write_state(), now=NOW)
        self.assertEqual(result['state'], 'healthy')
        self.assertEqual(result['freshness']['state'], 'fresh')
        self.assertEqual(result['metrics']['coverageRate'], 1)
        self.assertIn('not normative authority', result['claim'])

    def test_unknown_or_coverage_loss_requires_attention(self):
        self.assertEqual(read_runtime_loop(self.write_state('UNKNOWN'), now=NOW)['state'], 'attention')
        self.assertEqual(read_runtime_loop(self.write_state('PASS', 1), now=NOW)['state'], 'attention')

    def test_empty_history_is_no_data_not_healthy(self):
        result = read_runtime_loop(self.write_state(history=False), now=NOW)
        self.assertEqual(result['state'], 'no_data')
        self.assertIsNone(result['latest'])

    def test_old_latest_sample_is_stale_not_healthy(self):
        result = read_runtime_loop(self.write_state(observed_at='2026-09-21T18:00:00Z'), now=NOW)
        self.assertEqual(result['state'], 'stale')
        self.assertEqual(result['freshness']['state'], 'stale')


if __name__ == '__main__':
    unittest.main()
