import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.ecosystem import snapshot


class EcosystemSnapshotTests(unittest.TestCase):
    def test_missing_and_invalid_fail_closed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = snapshot(root)
            self.assertEqual(missing['state'], 'missing')
            self.assertEqual(missing['opportunities'], [])

            source = root / 'useful-work-operator' / 'ecosystem' / 'ecosystem-status.json'
            source.parent.mkdir(parents=True)
            source.write_text('{not-json', encoding='utf-8')
            invalid = snapshot(root)
            self.assertEqual(invalid['state'], 'invalid')

    def test_ready_snapshot_is_bounded_and_preserves_program_state(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            eco = root / 'useful-work-operator' / 'ecosystem'
            eco.mkdir(parents=True)
            source = {
                'generatedAt':'2026-09-27T00:00:00Z',
                'counts':{'offers':61},
                'programs':{'blockrewards':{'state':'active'}},
                'opportunities':[{'id':str(i)} for i in range(61)],
                'discovery':{'interestingRooms':[f'r{i}' for i in range(130)]},
            }
            (eco / 'ecosystem-status.json').write_text(json.dumps(source), encoding='utf-8')
            lane = root / 'useful-work-operator' / 'state-blockrewards-0-of-2'
            lane.mkdir(parents=True)
            (lane / 'status.json').write_text(json.dumps({'healthy':True}), encoding='utf-8')

            result = snapshot(root)
            self.assertEqual(result['state'], 'ready')
            self.assertEqual(result['counts']['offers'], 61)
            self.assertEqual(len(result['top_opportunities']), 50)
            self.assertEqual(len(result['interesting_rooms']), 100)
            self.assertTrue(result['blockrewards']['lanes'][0]['healthy'])
            self.assertEqual(result['blockrewards']['lanes'][1]['state'], 'missing')
            self.assertIn('observations', result['claim_boundary'])


if __name__ == '__main__':
    unittest.main()
