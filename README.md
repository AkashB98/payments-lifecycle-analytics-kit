# payments-lifecycle-analytics-kit

Synthetic payment-lifecycle analytics for lender-adjacent fintech — in pure Python 3 standard library (no third-party imports, no network required to run the analytics).

Payments move `initiated → authorized → settled`, or fail with a reason code and may be retried. This kit generates a deterministic fictional dataset across three rails (ACH, card, RTP), analyses *when* retries actually recover, prices retries with an illustrative cost table, validates retry plans against a configurable rule set, and derives a retry policy from one period and honestly scores it on a held-out second period.

## What it proves

- **Payments-rails fluency** — lifecycle state machine, attempt histories, failure reason codes, and re-presentment caps, modelled explicitly rather than hand-waved.
- **Retry analytics adjacent to collections work** — recovery rate by retry lag × failure reason is the same shape of question as retrying a failed loan payment: retry too soon and `insufficient_funds` has not cleared; wait for the right window and recovery jumps.
- **Policy derivation without leakage** — policy learned on period 1 only, scored on period 2 only, with the separation asserted in code and tests.
- **Cost-aware decision-making** — every recovery claim is paired with its retry cost, so a policy must win on cost-per-recovered, not just raw recovery.

## Headline results (seed 42, deterministic)

Rail comparison, period 1 (n=1000):

| Rail | First-attempt success | Eventual recovery | Mean attempts | Mean time-to-settle |
|------|----------------------|-------------------|---------------|---------------------|
| ACH | 0.805 | 0.881 | 1.286 | 4.63 h |
| card | 0.850 | 0.912 | 1.179 | 5.02 h |
| RTP | 0.937 | 0.958 | 1.063 | 2.56 h |

Recovery by lag (selected cells, period 1, n=1000):

- `insufficient_funds` retried at **24–72h: 0.654** recovery (17/26) — vs 0.032 immediately. Waiting matters.
- `network_timeout` retried at **0–1h: 0.769** recovery (10/13) — retry fast; the failure was transient.

Derived policy vs naive immediate-retry (derive on period 1, score on period 2, n=2000 each, min-n = 20):

- Derived policy: **0.588** simulated recovery rate
- Naive immediate-retry: **0.265**
- **Delta: +0.323** — and lower cost per recovered payment, because the same retry spend lands in better windows.

Retry costs on period 1 (n=1000, ILLUSTRATIVE fees): 1,213 attempts, $318.45 total, $0.3523 per settled payment.

## Quickstart

```bash
python3 cli.py demo                      # end-to-end demo (seed 42)
python3 cli.py generate --count 1000 --output payments.json
python3 cli.py analyze --count 1000      # rail table + recovery matrix + costs
python3 cli.py policy                    # derived vs naive on held-out period
python3 cli.py check                     # exits 0 on seeded data
python3 cli.py check --input fixtures/violating_plans.json   # exits 1 — planted violations flagged
python3 cli.py serve --port 8765         # GET http://127.0.0.1:8765/report
python3 -m unittest discover -s tests -v # 24 tests
python3 evals/run_evals.py               # 8 golden evals -> evals/eval_report.json
```

## How it works

- `payments_lifecycle/generator.py` — seeded generator (seed 42). Each payment has an id, rail, amount, attempt history (attempt number, timestamp offset in hours, lag, outcome, failure reason) and a final state (`settled` / `failed_permanent` / `written_off`). Failure reasons: `insufficient_funds`, `account_closed`, `invalid_account`, `do_not_honor`, `network_timeout`. Retry recovery probability depends on reason × lag bucket by design, which is what the analytics then rediscover.
- `payments_lifecycle/state_machine.py` — explicit allowed transitions; illegal transitions (e.g. `initiated → settled`, anything out of a terminal state) raise `IllegalTransitionError`.
- `payments_lifecycle/analytics.py` — recovery rate by lag bucket × failure reason, the rail comparison table, and retry-cost accounting.
- `payments_lifecycle/policy.py` — (a) a rule validator for retry plans, (b) policy derivation (best lag bucket per reason, minimum-n floor), (c) held-out simulation vs the naive policy.
- `payments_lifecycle/config.py` — the single source for all fee and retry-cap values.

## Retry-policy rule check

`validate_retry_plan` flags plans that violate the configured max-retries-per-reason table, including the **ACH R01/R09 re-presentment cap of 2 retries**. Both the cap and the table are **config values, labelled ILLUSTRATIVE** — see Limitations. `fixtures/violating_plans.json` plants exactly three violating payments (`fix_v1`, `fix_v2`, `fix_v3`) alongside two valid ones; tests and evals pin that exactly those three are flagged, no more, no fewer.

## POC framing

- **Problem:** Failed payments are retried on habit (usually immediately), which wastes attempt fees on failures that have not had time to clear and under-recovers money that a better-timed retry would collect.
- **Success criteria, declared up front:** (1) a derived policy must beat naive immediate retry on held-out data — not on the data it was derived from; (2) every headline number must be reproducible byte-for-byte from seed 42; (3) any retry plan the validator blesses must respect the configured caps.
- **Result:** Criteria met on the synthetic data — derived policy +0.323 recovery rate over naive on the held-out period, 8/8 golden evals pin the headline numbers, and the planted violating plans are flagged exactly. Whether the same lag windows hold on real payment data is an empirical question this POC does not claim to answer.

## Limitations — read these

- **Synthetic data only.** All payments are fictional and generated; no real payment, customer, or lender data is used anywhere.
- **Illustrative fees only.** Attempt costs in `config.py` are fictional values for demonstration. They are **not** real network fees and **not** a real interchange schedule — interchange is modelled *only* as this fee config table, by design.
- **No real rule claims.** The retry caps, including the ACH R01/R09 cap of 2, are config values in this codebase. They are **not** presented as real NACHA or card-network rules; consult the actual rulebooks before applying any of this operationally.
- **Simplified lifecycle.** Real rails have authorisation holds, partial settlements, reversals, chargebacks, and return timelines that this model omits deliberately to keep the retry question legible.
- **Simulation is expected-value.** The held-out policy score uses period-1 recovery rates as the model for period-2 retries; it is a comparison harness, not a live A/B test.

## Dev-loop honesty note

One real design error was caught by the checks during the build: the first version of the policy simulation scored the derived policy and the naive policy on *different* eligible sets — payments whose failure reason had no derived policy (below the minimum-n floor at n=1000) were silently dropped from the derived score but kept in the naive score, inflating the comparison. The fix makes both policies score the identical eligible set, with the derived policy falling back to immediate retry where no bucket clears the floor, and the demo/policy runs were moved to n=2000 so all three retryable reasons clear the floor. No bug is invented here beyond that one — it is documented because the eval harness is exactly what caught the smell (mismatched `eligible` counts in the demo output).

## Layout

```
payments_lifecycle/   generator, state machine, analytics, policy, config, CLI
cli.py                entry point
tests/                24 unittest tests (state machine, determinism, hand-checked analytics, policy, no-network guard)
evals/run_evals.py    8 golden evals -> evals/eval_report.json (byte-identical across runs)
fixtures/             planted violating / valid retry plans
```

## License

MIT — see `LICENSE`.
