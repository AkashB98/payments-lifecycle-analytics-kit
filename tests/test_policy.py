import unittest, json, os
from payments_lifecycle.policy import validate_retry_plan, derive_policy, simulate_policies
from payments_lifecycle.generator import generate_payments

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "fixtures", "violating_plans.json")

class TestPolicyValidator(unittest.TestCase):
    def test_planted_violations_exact(self):
        with open(FIXTURES) as f:
            plan = json.load(f)
        violations = validate_retry_plan(plan)
        flagged = sorted(v["payment_id"] for v in violations)
        self.assertEqual(flagged, ["fix_v1", "fix_v2", "fix_v3"])
        self.assertEqual(len(violations), 3)

    def test_valid_plan_no_violations(self):
        plan = [{"payment_id": "ok1", "rail": "ACH", "failure_reason": "insufficient_funds", "failure_code": "R01", "planned_retries": 2}]
        self.assertEqual(validate_retry_plan(plan), [])

    def test_ach_cap_rule_name(self):
        plan = [{"payment_id": "x", "rail": "ACH", "failure_reason": "insufficient_funds", "failure_code": "R09", "planned_retries": 3}]
        v = validate_retry_plan(plan)
        self.assertTrue(any(x["rule"] == "ach_representment_cap_R01_R09" for x in v))

    def test_derive_and_simulate_no_leakage(self):
        p1 = generate_payments(seed=42, n=1000, period=1)
        p2 = generate_payments(seed=42, n=1000, period=2)
        result = simulate_policies(p1, p2, min_n=20)
        self.assertIn("insufficient_funds", result["policy"])
        # Derived should beat naive on recovery rate in this synthetic design
        self.assertGreater(result["derived"]["simulated_recovery_rate"], result["naive"]["simulated_recovery_rate"])
        self.assertGreater(result["delta_recovery_rate"], 0)

    def test_period_leakage_asserts(self):
        p1 = generate_payments(seed=42, n=100, period=1)
        with self.assertRaises(AssertionError):
            simulate_policies(p1, p1, min_n=5)

    def test_min_n_floor(self):
        p1 = generate_payments(seed=42, n=1000, period=1)
        policy = derive_policy(p1, min_n=100000)
        self.assertEqual(policy, {})

if __name__ == "__main__":
    unittest.main()
