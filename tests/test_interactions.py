import json
import tempfile
import unittest
from pathlib import Path

from core.interactions import read_interactions


class InteractionObservatoryTests(unittest.TestCase):
    def test_missing_state_is_unchecked_not_quiet(self):
        data = read_interactions('Z:/missing/state.json', 'Z:/missing/events.json')
        self.assertEqual(data['check_status'], 'UNCHECKED')
        self.assertIn('not be interpreted as quiet', data['claim'])

    def test_checked_zero_events_is_quiet(self):
        state = {
            'schema': 'flop.interaction-state.v1',
            'generatedAt': '2026-09-20T15:00:00Z',
            'checkStatus': 'CHECKED',
            'threads': [],
        }
        events = {
            'schema': 'flop.interaction-events.v1',
            'generatedAt': '2026-09-20T15:00:00Z',
            'events': [],
        }
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / 'state.json'
            ep = Path(td) / 'events.json'
            sp.write_text(json.dumps(state), encoding='utf-8')
            ep.write_text(json.dumps(events), encoding='utf-8')
            data = read_interactions(sp, ep)
        self.assertEqual(data['check_status'], 'CHECKED')
        self.assertEqual(data['events'], [])
        self.assertIn('means quiet', data['claim'])

    def test_actionable_events_are_exposed(self):
        state = {
            'schema': 'flop.interaction-state.v1',
            'generatedAt': '2026-09-20T15:00:00Z',
            'checkStatus': 'CHECKED',
            'threads': [{'threadId':'tclk-pr-166'}],
        }
        events = {
            'schema': 'flop.interaction-events.v1',
            'generatedAt': '2026-09-20T15:00:00Z',
            'events': [
                {'kind':'MAINTAINER_REPLY','action':'RUN_CONFORMANCE','threadId':'tclk-pr-166'},
                {'kind':'EXTERNAL_REPLY','action':'NONE','threadId':'x'},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / 'state.json'
            ep = Path(td) / 'events.json'
            sp.write_text(json.dumps(state), encoding='utf-8')
            ep.write_text(json.dumps(events), encoding='utf-8')
            data = read_interactions(sp, ep)
        self.assertEqual(len(data['actionable']), 1)
        self.assertEqual(data['counts']['MAINTAINER_REPLY'], 1)


if __name__ == '__main__':
    unittest.main()
