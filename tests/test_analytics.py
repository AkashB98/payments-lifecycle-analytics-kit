import unittest
from payments_lifecycle.analytics import rail_comparison, recovery_rate_by_lag_and_reason, retry_cost_accounting

def fixture_payments():
    return [
        {"id": "a1", "rail": "ACH", "amount": 100.0, "period": 1, "final_state": "settled",
         "attempts": [
             {"attempt_no": 1, "timestamp_offset_hours": 0.0, "lag_hours": 0.0, "outcome": "failure", "failure_reason": "insufficient_funds"},
             {"attempt_no": 2, "timestamp_offset_hours": 48.0, "lag_hours": 48.0, "outcome": "success", "failure_reason": None},
         ]},
        {"id": "a2", "rail": "ACH", "amount": 50.0, "period": 1, "final_state": "failed_permanent",
         "attempts": [
             {"attempt_no": 1, "timestamp_offset_hours": 0.0, "lag_hours": 0.0, "outcome": "failure", "failure_reason": "insufficient_funds"},
             {"attempt_no": 2, "timestamp_offset_hours": 48.0, "lag_hours": 48.0, "outcome": "failure", "failure_reason": "insufficient_funds"},
         ]},
        {"id": "c1", "rail": "card", "amount": 20.0, "period": 1, "final_state": "settled",
         "attempts": [
             {"attempt_no": 1, "timestamp_offset_hours": 0.0, "lag_hours": 0.0, "outcome": "success", "failure_reason": None},
         ]},
    ]

class TestAnalytics(unittest.TestCase):
    def test_recovery_hand_checked(self):
        rec = recovery_rate_by_lag_and_reason(fixture_payments())
        entry = rec[("insufficient_funds", "24-72h")]
        self.assertEqual(entry["attempts"], 2)
        self.assertEqual(entry["successes"], 1)
        self.assertEqual(entry["recovery_rate"], 0.5)

    def test_rail_hand_checked(self):
        rails = rail_comparison(fixture_payments())
        self.assertEqual(rails["ACH"]["count"], 2)
        self.assertEqual(rails["ACH"]["first_attempt_success_rate"], 0.0)
        self.assertEqual(rails["ACH"]["eventual_recovery_rate"], 0.5)
        self.assertEqual(rails["ACH"]["mean_attempts"], 2.0)
        self.assertEqual(rails["ACH"]["mean_time_to_settle_hours"], 48.0)
        self.assertEqual(rails["card"]["first_attempt_success_rate"], 1.0)
        self.assertEqual(rails["card"]["mean_attempts"], 1.0)

    def test_costs_hand_checked(self):
        # ACH 4 attempts *0.25=1.0, card 1*0.30=0.30 total 1.30, settled 2
        costs = retry_cost_accounting(fixture_payments())
        self.assertEqual(costs["total_attempts"], 5)
        self.assertEqual(costs["total_cost"], 1.3)
        self.assertEqual(costs["settled_count"], 2)

    def test_empty(self):
        self.assertEqual(rail_comparison([]), {})
        self.assertEqual(recovery_rate_by_lag_and_reason([]), {})

if __name__ == "__main__":
    unittest.main()
