"""Headline analytics."""
from .config import ATTEMPT_COSTS, lag_bucket

def recovery_rate_by_lag_and_reason(payments):
    """Return dict[(reason, bucket)] = {attempts, successes, recovery_rate}
    Only retry attempts (attempt_no>1) count; reason is previous attempt's failure reason,
    bucket is lag bucket of this retry attempt.
    """
    stats = {}
    for p in payments:
        attempts = p["attempts"]
        for idx in range(1, len(attempts)):
            prev = attempts[idx-1]
            cur = attempts[idx]
            if prev["outcome"] != "failure":
                continue
            reason = prev["failure_reason"]
            bucket = lag_bucket(cur["lag_hours"])
            key = (reason, bucket)
            if key not in stats:
                stats[key] = {"attempts": 0, "successes": 0}
            stats[key]["attempts"] += 1
            if cur["outcome"] == "success":
                stats[key]["successes"] += 1
    result = {}
    for k in sorted(stats.keys()):
        a = stats[k]["attempts"]
        s = stats[k]["successes"]
        result[k] = {"attempts": a, "successes": s, "recovery_rate": round(s/a, 6) if a else 0.0}
    return result

def rail_comparison(payments):
    """Return dict rail -> metrics."""
    by_rail = {}
    for p in payments:
        rail = p["rail"]
        by_rail.setdefault(rail, []).append(p)
    result = {}
    for rail in sorted(by_rail.keys()):
        group = by_rail[rail]
        total = len(group)
        first_success = sum(1 for p in group if p["attempts"] and p["attempts"][0]["outcome"] == "success")
        settled = sum(1 for p in group if p["final_state"] == "settled")
        mean_attempts = sum(len(p["attempts"]) for p in group) / total if total else 0.0
        settle_times = [p["attempts"][-1]["timestamp_offset_hours"] for p in group if p["final_state"] == "settled"]
        mean_tts = sum(settle_times)/len(settle_times) if settle_times else 0.0
        result[rail] = {
            "count": total,
            "first_attempt_success_rate": round(first_success/total, 6) if total else 0.0,
            "eventual_recovery_rate": round(settled/total, 6) if total else 0.0,
            "settled_count": settled,
            "mean_attempts": round(mean_attempts, 6),
            "mean_time_to_settle_hours": round(mean_tts, 6),
        }
    return result

def retry_cost_accounting(payments, costs=None):
    """ILLUSTRATIVE costs from config table only."""
    if costs is None:
        costs = ATTEMPT_COSTS
    total_attempts = 0
    total_cost = 0.0
    by_rail = {}
    for p in payments:
        c = costs.get(p["rail"], 0.0)
        n = len(p["attempts"])
        total_attempts += n
        total_cost += n * c
        by_rail.setdefault(p["rail"], {"attempts": 0, "cost": 0.0})
        by_rail[p["rail"]]["attempts"] += n
        by_rail[p["rail"]]["cost"] += n * c
    settled = sum(1 for p in payments if p["final_state"] == "settled")
    for k in by_rail:
        by_rail[k]["cost"] = round(by_rail[k]["cost"], 2)
    return {
        "total_attempts": total_attempts,
        "total_cost": round(total_cost, 2),
        "cost_per_settled": round(total_cost/settled, 4) if settled else 0.0,
        "settled_count": settled,
        "by_rail": by_rail,
        "note": "ILLUSTRATIVE fees only — not real network/interchange rules",
    }
