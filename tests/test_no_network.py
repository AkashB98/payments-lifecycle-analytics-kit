import unittest, os, re
ROOT = os.path.join(os.path.dirname(__file__), "..", "payments_lifecycle")
FORBIDDEN = ["import requests", "import urllib", "from urllib", "import socket", "import http.client"]

class TestNoNetwork(unittest.TestCase):
    def test_core_modules_no_network_imports(self):
        # cli.py is exempt for serve (http.server on localhost only); check other modules
        for fname in ("generator.py", "analytics.py", "policy.py", "state_machine.py", "config.py"):
            with open(os.path.join(ROOT, fname)) as f:
                text = f.read()
            for pat in FORBIDDEN:
                self.assertNotIn(pat, text, f"{fname} contains forbidden network import {pat}")

    def test_analytics_runs_offline(self):
        # If this runs at all without network, guard passes; also check no env credentials needed
        from payments_lifecycle.generator import generate_payments
        from payments_lifecycle.analytics import rail_comparison
        result = rail_comparison(generate_payments(seed=42, n=10, period=1))
        self.assertTrue(len(result) >= 1)

if __name__ == "__main__":
    unittest.main()
