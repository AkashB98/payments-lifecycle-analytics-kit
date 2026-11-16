"""Configuration — all fee / retry values are ILLUSTRATIVE.

These are fictional, illustrative values for a synthetic demo.
They are NOT real network rules, NOT real NACHA rules, and NOT
real interchange schedules. Interchange is modelled ONLY as this
fee config table, per project scope.
"""
# ILLUSTRATIVE attempt costs (USD) — fictional, not real network fees
ATTEMPT_COSTS = {
    "ACH": 0.25,
    "card": 0.30,
    "RTP": 0.20,
}

# ILLUSTRATIVE max retries per failure reason
MAX_RETRIES_PER_REASON = {
    "insufficient_funds": 3,
    "account_closed": 0,
    "invalid_account": 0,
    "do_not_honor": 1,
    "network_timeout": 3,
}

# ILLUSTRATIVE: ACH returns R01 / R09 re-presentment cap (config value)
ACH_REPRESENTMENT_CAP = 2
ACH_CAPPED_CODES = {"R01", "R09"}

# Mapping reason -> illustrative ACH return code (for fixtures / validator demo)
REASON_TO_ACH_CODE = {
    "insufficient_funds": "R01",
    "account_closed": "R02",
    "invalid_account": "R03",
    "do_not_honor": "R09",
    "network_timeout": None,
}

FAILURE_REASONS = [
    "insufficient_funds",
    "account_closed",
    "invalid_account",
    "do_not_honor",
    "network_timeout",
]

PERMANENT_REASONS = {"account_closed", "invalid_account"}

LAG_BUCKETS = ["0-1h", "1-24h", "24-72h", "72h+"]

def lag_bucket(lag_hours):
    if lag_hours < 1:
        return "0-1h"
    if lag_hours < 24:
        return "1-24h"
    if lag_hours < 72:
        return "24-72h"
    return "72h+"
