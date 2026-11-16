"""Seeded deterministic generator of fictional payments. Stdlib only."""
import random
from .config import FAILURE_REASONS, PERMANENT_REASONS

RAILS = ["ACH", "card", "RTP"]
RAIL_WEIGHTS = [0.45, 0.40, 0.15]

# First-attempt failure probability by rail (synthetic)
FIRST_FAIL_PROB = {"ACH": 0.18, "card": 0.15, "RTP": 0.08}
# Failure reason weights when a failure occurs
REASON_WEIGHTS = [0.45, 0.10, 0.08, 0.17, 0.20]  # aligned with FAILURE_REASONS order below
REASON_ORDER = ["insufficient_funds", "account_closed", "invalid_account", "do_not_honor", "network_timeout"]

# Recovery probability by (reason, lag_bucket) for retry attempts — synthetic
RECOVERY_PROB = {
    "insufficient_funds": {"0-1h": 0.10, "1-24h": 0.25, "24-72h": 0.55, "72h+": 0.40},
    "account_closed": {"0-1h": 0.0, "1-24h": 0.0, "24-72h": 0.0, "72h+": 0.0},
    "invalid_account": {"0-1h": 0.0, "1-24h": 0.0, "24-72h": 0.0, "72h+": 0.0},
    "do_not_honor": {"0-1h": 0.08, "1-24h": 0.12, "24-72h": 0.18, "72h+": 0.15},
    "network_timeout": {"0-1h": 0.70, "1-24h": 0.60, "24-72h": 0.50, "72h+": 0.40},
}
LAG_CHOICES_HOURS = {
    "0-1h": 0.5,
    "1-24h": 12.0,
    "24-72h": 48.0,
    "72h+": 96.0,
}
LAG_BUCKET_LIST = ["0-1h", "1-24h", "24-72h", "72h+"]

def _bucket_for_lag(h):
    if h < 1:
        return "0-1h"
    if h < 24:
        return "1-24h"
    if h < 72:
        return "24-72h"
    return "72h+"

def generate_payments(seed=42, n=1000, period=1):
    """Generate n payments. Period changes seed and id prefix — no overlap."""
    effective_seed = seed + (period - 1) * 1000
    rng = random.Random(effective_seed)
    payments = []
    for i in range(n):
        pid = f"pay_p{period}_{i+1:05d}"
        rail = rng.choices(RAILS, weights=RAIL_WEIGHTS, k=1)[0]
        amount = round(rng.uniform(10.0, 500.0), 2)
        attempts = []
        offset = 0.0
        final_state = None
        # First attempt
        attempt_no = 1
        prev_reason = None
        while True:
            if attempt_no == 1:
                lag = 0.0
                fail_prob = FIRST_FAIL_PROB[rail]
                failed = rng.random() < fail_prob
                if not failed:
                    attempts.append({"attempt_no": 1, "timestamp_offset_hours": 0.0, "lag_hours": 0.0, "outcome": "success", "failure_reason": None})
                    final_state = "settled"
                    break
                reason = rng.choices(REASON_ORDER, weights=REASON_WEIGHTS, k=1)[0]
                attempts.append({"attempt_no": 1, "timestamp_offset_hours": 0.0, "lag_hours": 0.0, "outcome": "failure", "failure_reason": reason})
                prev_reason = reason
                if reason in PERMANENT_REASONS:
                    final_state = "failed_permanent" if rng.random() < 0.8 else "written_off"
                    break
                # decide to retry: 85% retry for non-permanent
                if rng.random() > 0.85:
                    final_state = "written_off"
                    break
                attempt_no += 1
                continue
            else:
                # Retry attempt: choose lag bucket uniformly (so all buckets have data)
                bucket = rng.choice(LAG_BUCKET_LIST)
                lag = LAG_CHOICES_HOURS[bucket]
                # jitter deterministically small, keep bucket stable by using exact centre values + tiny jitter within bucket handled by fixed values
                offset += lag
                prob = RECOVERY_PROB[prev_reason][bucket]
                success = rng.random() < prob
                if success:
                    attempts.append({"attempt_no": attempt_no, "timestamp_offset_hours": round(offset, 2), "lag_hours": lag, "outcome": "success", "failure_reason": None})
                    final_state = "settled"
                    break
                # failed again — reason may stay same or become permanent occasionally
                # Keep same reason for simplicity except 5% switch to do_not_honor
                new_reason = prev_reason
                if rng.random() < 0.05:
                    new_reason = "do_not_honor"
                attempts.append({"attempt_no": attempt_no, "timestamp_offset_hours": round(offset, 2), "lag_hours": lag, "outcome": "failure", "failure_reason": new_reason})
                prev_reason = new_reason
                if attempt_no >= 4:
                    final_state = "written_off" if rng.random() < 0.5 else "failed_permanent"
                    break
                if rng.random() > 0.80:
                    final_state = "written_off"
                    break
                attempt_no += 1
                continue
        payments.append({
            "id": pid,
            "rail": rail,
            "amount": amount,
            "attempts": attempts,
            "final_state": final_state,
            "period": period,
        })
    return payments
