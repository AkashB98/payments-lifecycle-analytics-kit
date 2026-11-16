import unittest
from payments_lifecycle.generator import generate_payments

class TestGenerator(unittest.TestCase):
    def test_determinism(self):
        a = generate_payments(seed=42, n=100, period=1)
        b = generate_payments(seed=42, n=100, period=1)
        self.assertEqual(a, b)

    def test_count_and_fields(self):
        ps = generate_payments(seed=42, n=50, period=1)
        self.assertEqual(len(ps), 50)
        for p in ps:
            self.assertIn(p["rail"], ("ACH", "card", "RTP"))
            self.assertIn(p["final_state"], ("settled", "failed_permanent", "written_off"))
            self.assertGreaterEqual(len(p["attempts"]), 1)
            self.assertEqual(p["attempts"][0]["attempt_no"], 1)

    def test_period_separation(self):
        p1 = generate_payments(seed=42, n=100, period=1)
        p2 = generate_payments(seed=42, n=100, period=2)
        self.assertTrue({x["id"] for x in p1}.isdisjoint({x["id"] for x in p2}))
        self.assertTrue(all(x["period"] == 1 for x in p1))
        self.assertTrue(all(x["period"] == 2 for x in p2))
        self.assertNotEqual(p1, p2)

    def test_failure_reasons_valid(self):
        valid = {"insufficient_funds", "account_closed", "invalid_account", "do_not_honor", "network_timeout", None}
        for p in generate_payments(seed=42, n=200, period=1):
            for a in p["attempts"]:
                self.assertIn(a["failure_reason"], valid)

    def test_different_seed_differs(self):
        a = generate_payments(seed=42, n=50, period=1)
        b = generate_payments(seed=99, n=50, period=1)
        self.assertNotEqual(a, b)

if __name__ == "__main__":
    unittest.main()
