#!/usr/bin/env python3
"""Golden evals — deterministic, stdlib only. Writes evals/eval_report.json (sorted keys, no timestamps)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from payments_lifecycle.generator import generate_payments
from payments_lifecycle.analytics import rail_comparison, recovery_rate_by_lag_and_reason, retry_cost_accounting
from payments_lifecycle.policy import validate_retry_plan, simulate_policies
from payments_lifecycle.state_machine import transition, IllegalTransitionError

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")

def main():
    checks = []
    def record(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    p1000 = generate_payments(seed=42, n=1000, period=1)

    # 1 determinism
    record("generator_determinism", generate_payments(seed=42, n=100, period=1) == generate_payments(seed=42, n=100, period=1), "seed42 n=100 identical across calls")

    # 2 rail table golden
    rails = rail_comparison(p1000)
    expected_rails = {
        "ACH": {"count": 472, "first_attempt_success_rate": 0.805085, "eventual_recovery_rate": 0.881356, "mean_attempts": 1.286017, "mean_time_to_settle_hours": 4.633413},
        "card": {"count": 386, "first_attempt_success_rate": 0.849741, "eventual_recovery_rate": 0.911917, "mean_attempts": 1.178756, "mean_time_to_settle_hours": 5.021307},
        "RTP": {"count": 142, "first_attempt_success_rate": 0.93662, "eventual_recovery_rate": 0.957746, "mean_attempts": 1.06338, "mean_time_to_settle_hours": 2.558824},
    }
    ok = all(rails[r][k] == v for r, exp in expected_rails.items() for k, v in exp.items())
    record("rail_table_golden", ok, f"ACH eventual={rails['ACH']['eventual_recovery_rate']} card eventual={rails['card']['eventual_recovery_rate']} RTP eventual={rails['RTP']['eventual_recovery_rate']}")

    # 3 recovery cells golden
    rec = recovery_rate_by_lag_and_reason(p1000)
    c1 = rec[("insufficient_funds", "24-72h")]
    c2 = rec[("network_timeout", "0-1h")]
    ok = c1 == {"attempts": 26, "successes": 17, "recovery_rate": 0.653846} and c2 == {"attempts": 13, "successes": 10, "recovery_rate": 0.769231}
    record("recovery_cells_golden", ok, f"insufficient_funds|24-72h={c1['recovery_rate']} network_timeout|0-1h={c2['recovery_rate']}")

    # 4 costs golden
    costs = retry_cost_accounting(p1000)
    ok = costs["total_attempts"] == 1213 and costs["total_cost"] == 318.45 and costs["settled_count"] == 904 and costs["cost_per_settled"] == 0.3523
    record("retry_costs_golden", ok, f"total_cost={costs['total_cost']} total_attempts={costs['total_attempts']} cost_per_settled={costs['cost_per_settled']}")

    # 5 policy vs naive golden (derive p1 n=2000, score p2 n=2000, min_n=20)
    p1 = generate_payments(seed=42, n=2000, period=1)
    p2 = generate_payments(seed=42, n=2000, period=2)
    sim = simulate_policies(p1, p2, min_n=20)
    ok = (sim["derived"]["simulated_recovery_rate"] == 0.587869 and sim["naive"]["simulated_recovery_rate"] == 0.26512
          and sim["delta_recovery_rate"] == 0.322749
          and sim["policy"]["insufficient_funds"]["best_lag_bucket"] == "24-72h"
          and sim["policy"]["network_timeout"]["best_lag_bucket"] == "0-1h")
    record("policy_vs_naive_golden", ok, f"derived={sim['derived']['simulated_recovery_rate']} naive={sim['naive']['simulated_recovery_rate']} delta={sim['delta_recovery_rate']}")

    # 6 rule-check planted exact
    with open(os.path.join(ROOT, "fixtures", "violating_plans.json")) as f:
        plan = json.load(f)
    violations = validate_retry_plan(plan)
    flagged = sorted(v["payment_id"] for v in violations)
    record("rule_check_planted_exact", flagged == ["fix_v1", "fix_v2", "fix_v3"] and len(violations) == 3, f"flagged={flagged}")

    # 7 period separation
    ok = {x["id"] for x in p1}.isdisjoint({x["id"] for x in p2})
    record("period_separation", ok, "period1 and period2 ids disjoint")

    # 8 state machine illegal rejected
    try:
        transition("initiated", "settled")
        ok = False
    except IllegalTransitionError:
        ok = True
    record("state_machine_illegal_rejected", ok, "initiated->settled raises IllegalTransitionError")

    passed = sum(1 for c in checks if c["passed"])
    report = {
        "eval_count": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "all_passed": passed == len(checks),
        "checks": sorted(checks, key=lambda c: c["name"]),
        "headline": {
            "ach_eventual_recovery_rate": rails["ACH"]["eventual_recovery_rate"],
            "derived_recovery_rate": sim["derived"]["simulated_recovery_rate"],
            "naive_recovery_rate": sim["naive"]["simulated_recovery_rate"],
            "delta_recovery_rate": sim["delta_recovery_rate"],
            "total_cost_illustrative_n1000": costs["total_cost"],
        },
    }
    out = os.path.join(HERE, "eval_report.json")
    with open(out, "w") as f:
        f.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
