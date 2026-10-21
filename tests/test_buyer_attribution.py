import unittest
from core.evidence_api import classify_buyer_attribution

class BuyerAttributionTests(unittest.TestCase):
    def test_missing_assessment_never_passes(self):
        self.assertEqual(classify_buyer_attribution({'schema': 'flop-router/buyer-evidence/v1'})['status'], 'UNKNOWN')
    def test_unknown_remains_unknown(self):
        data = {'schema': 'flop-router/buyer-evidence/v1', 'attributionAssessment': {'status': 'UNKNOWN', 'rewardEligibility': 'UNKNOWN', 'economicExecutionAllowed': False}}
        self.assertEqual(classify_buyer_attribution(data)['status'], 'UNKNOWN')
        self.assertFalse(classify_buyer_attribution(data)['rewardEligible'])
    def test_malicious_reward_claim_fails_closed(self):
        data = {'schema': 'flop-router/buyer-evidence/v1', 'attributionAssessment': {'status': 'PASS', 'rewardEligibility': 'ELIGIBLE', 'economicExecutionAllowed': True}}
        self.assertEqual(classify_buyer_attribution(data)['status'], 'UNKNOWN')
    def test_local_pass_never_grants_reward(self):
        data = {'schema': 'flop-router/buyer-evidence/v1', 'attributionAssessment': {'status': 'PASS', 'rewardEligibility': 'UNKNOWN', 'economicExecutionAllowed': False}}
        self.assertFalse(classify_buyer_attribution(data)['rewardEligible'])

if __name__ == '__main__':
    unittest.main()
