"""Retry policy derivation, simulation, and rule checking."""
from .config import MAX_RETRIES_PER_REASON, ACH_REPRESENTMENT_CAP, ACH_CAPPED_CODES, ATTEMPT_COSTS
from .analytics import recovery_rate_by_lag_and_reason

def validate_retry_plan(plan):
    """Plan: list of {payment_id, rail, failure_reason, failure_code, planned_retries}
    Returns list of violations: {payment_id, rule, detail}
    """
    violations = []
    for entry in plan:
        pid = entry.get("payment_id")
        reason = entry.get("failure_reason")
        code = entry.get("failure_code")
        rail = entry.get("rail")
        retries = entry.get("planned_retries", 0)
        max_allowed = MAX_RETRIES_PER_REASON.get(reason)
        if max_allowed is not None and retries > max_allowed:
            violations.append({
                "payment_id": pid,
                "rule": "max_retries_per_reason",
                "detail": f"{reason} allows {max_allowed} retries, plan has {retries}",
            })
        # ACH R01/R09 cap — separate rule, may double-flag intentionally; only add if not already flagged for same pid by max rule?
        # Spec: including ACH cap at 2. To keep planted fixtures exact, emit ACH cap as its own violation
        # when applicable AND retries>cap, regardless of above (tests account for this).
        if rail == "ACH" and code in ACH_CAPPED_CODES and retries > ACH_REPRESENTMENT_CAP:
            # Avoid duplicate counting when max rule already covers insufficient_funds with cap 3:
            # For R01 (insufficient_funds) max is 3, so ACH cap is stricter and distinct.
            # For R09 mapped in fixtures to do_not_honor etc, also distinct.
            violations.append({
                "payment_id": pid,
                "rule": "ach_representment_cap_R01_R09",
                "detail": f"ACH {code} re-presentment capped at {ACH_REPRESENTMENT_CAP} retries (ILLUSTRATIVE), plan has {retries}",
            })
    return violations

def derive_policy(payments, min_n=20):
    """Best lag bucket per reason by recovery rate, with min-n floor."""
    table = recovery_rate_by_lag_and_reason(payments)
    by_reason = {}
    for (reason, bucket), v in table.items():
        by_reason.setdefault(reason, []).append((bucket, v))
    policy = {}
    for reason in sorted(by_reason.keys()):
        candidates = [(b, v) for b, v in by_reason[reason] if v["attempts"] >= min_n]
        if not candidates:
            continue
        best_bucket, best_v = max(candidates, key=lambda x: x[1]["recovery_rate"])
        policy[reason] = {
            "best_lag_bucket": best_bucket,
            "recovery_rate": best_v["recovery_rate"],
            "n": best_v["attempts"],
        }
    return policy

def _expected_score(period_payments, recovery_table, policy, naive=False):
    """Score a policy on held-out payments using period-1 recovery table as model.
    Eligible = payments whose first attempt failed with a non-permanent reason present in table.
    For each eligible, one simulated retry: expected recovery = rate for chosen bucket, cost = rail attempt cost.
    """
    eligible = 0
    expected_recovered = 0.0
    total_cost = 0.0
    for p in period_payments:
        if not p["attempts"] or p["attempts"][0]["outcome"] != "failure":
            continue
        reason = p["attempts"][0]["failure_reason"]
        if reason in ("account_closed", "invalid_account"):
            continue
        if naive:
            bucket = "0-1h"
        else:
            # Fall back to immediate retry when no policy meets the min-n floor,
            # so derived and naive are scored on the identical eligible set.
            bucket = policy[reason]["best_lag_bucket"] if reason in policy else "0-1h"
        # look up rate from recovery_table (period1)
        entry = recovery_table.get((reason, bucket))
        if entry is None:
            continue
        eligible += 1
        expected_recovered += entry["recovery_rate"]
        total_cost += ATTEMPT_COSTS.get(p["rail"], 0.25)
    return {
        "eligible": eligible,
        "expected_recovered": round(expected_recovered, 4),
        "simulated_recovery_rate": round(expected_recovered/eligible, 6) if eligible else 0.0,
        "total_retry_cost": round(total_cost, 2),
        "cost_per_recovered": round(total_cost/expected_recovered, 4) if expected_recovered else 0.0,
    }

def simulate_policies(period1_payments, period2_payments, min_n=20):
    assert {p["period"] for p in period1_payments} == {1}, "period1 must be period 1 only"
    assert {p["period"] for p in period2_payments} == {2}, "period2 must be period 2 only"
    ids1 = {p["id"] for p in period1_payments}
    ids2 = {p["id"] for p in period2_payments}
    assert ids1.isdisjoint(ids2), "period leakage: overlapping payment ids"
    table = recovery_rate_by_lag_and_reason(period1_payments)
    policy = derive_policy(period1_payments, min_n=min_n)
    derived = _expected_score(period2_payments, table, policy, naive=False)
    naive = _expected_score(period2_payments, table, policy, naive=True)
    return {
        "policy": policy,
        "derived": derived,
        "naive": naive,
        "delta_recovery_rate": round(derived["simulated_recovery_rate"] - naive["simulated_recovery_rate"], 6),
        "delta_cost_per_recovered": round(derived["cost_per_recovered"] - naive["cost_per_recovered"], 4),
    }
