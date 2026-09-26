import unittest
from pathlib import Path


class HumanUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (Path(__file__).parents[1] / 'ui' / 'public' / 'index.html').read_text(encoding='utf-8')

    def test_human_first_sections_exist(self):
        for label in ('Overall state', 'Needs attention', 'ROUTE / RUN / PROVE / OBSERVE', 'What changed', 'Adoption & integrate', 'Continuity', 'Conformance handoff', 'Evidence', 'Technical detail'):
            self.assertIn(label, self.html)

    def test_operator_actions_are_preserved(self):
        for token in ('checkRepo(', 'openRepo(', 'task(task,action)', '/api/check', '/api/open', '/api/task'):
            self.assertIn(token, self.html)

    def test_no_known_mojibake(self):
        self.assertNotIn('â€”', self.html)
        self.assertNotIn('Ã', self.html)


if __name__ == '__main__':
    unittest.main()
