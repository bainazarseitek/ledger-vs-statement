Planning document, drafted with AI assistance before the build and reviewed by me. Where it differs from the code, the code is the truth.

# ADR-0007: Evaluation and answer key

- **Status:** Proposed
- **Date:** 2026-11-01
- **Accept at:** U1 (M11), step S11.5, after `make eval` has run

## Context

1. The generator plants defects D1 to D5 and benign behaviours B1 to B3 ("Defect catalog" in `docs/specs/data_and_generator.md`).
2. One person writes the generator and the matcher, so any score is self-graded; accuracy, precision or recall would mislead.
3. The answer key must never reach the models, even by mistake.
4. A self-test tells you something only if it can fail: benign noise must sometimes cross the tolerance, and some defects must slip under it.

## Options considered

| Option | For | Against | Verdict |
|---|---|---|---|
| No answer key | no self-grading | labels never checked on planted data | Rejected |
| Key in BigQuery, read by a guarded model | all in dbt | one wrong `ref` leaks the answers | Rejected |
| Key in local files, scored by a local script | isolated by design | scoring outside dbt | **Chosen** |
| Accuracy, precision or recall | familiar | self-graded rates read as inflated | Rejected: raw counts |
| Noise always inside the tolerance | clean results | false alarms impossible | Rejected |
| A second seed as the "holdout" | cheap | same defects, nothing held out | Rejected: a held-out world (U4) |

## Decision

1. The defect catalog is committed in M0, before any matcher SQL.
2. `emit` writes the key to `landing/_truth/booking_date=YYYY-MM-DD.ndjson` (fields: "Ground truth (answer key)" in `docs/specs/data_and_generator.md`). It is never loaded into BigQuery: the loader skips it, `landing/_truth/` is gitignored, and no dbt source points at it. Only `scripts/eval.py` (U1) reads it, regenerating it from (seed, world_start) if absent. U2's CI asserts this.
3. Scoring runs as of the marts' `as_of_date`, over final lines that are not `before_scope`. Per cause it counts planted (from the generator's intent), flagged, TP, FP and FN: a flagged benign spike is an FP, a D5 within the tolerance an FN, any `date_mismatch` an FP. Raw counts go to `docs/evidence/<date>/eval.json`; the full rules are under the same heading.
4. Mistakes are possible on purpose: about 1% of settled lines without D5 get a benign spike of 1 to 1.5 times the tolerance, and D5 overcharges run from 0.8 to 10 times it.
5. The name is "seeded self-test (synthetic)": never accuracy, never the headline, shown only after U1 with its counts.
6. The held-out world (U4) comes only after tag `v1.3`: a new seed, doubled rates and unseen defects H1 to H4, in `raw_heldout` and `analytics_heldout`. Misses are published; v1.4 fixes them with failing-first unit tests.

## Consequences

**Cost.** One local script and a few SELECT queries.

**Better.** The matcher cannot read the answers; results are counts with misses and false alarms; U4 tests behaviour the matcher was never tuned for.

**Worse.** Still synthetic (README "What this does not prove"); the script can have bugs; [TP], [FP] and [FN] stay unknown until `make eval` (fill them from `eval.json`, or delete this clause).

**Revisit when.** Independently labelled data appears, a reader asks how stable the counts are (run more seeds), or U4 needs a new status (v1.4 adds `duplicate_in_statement`).

## Sources (checked 2026-11-01)

The common pattern https://github.com/sharath957/payments-reconciliation-dbt; dbt unit tests https://docs.getdbt.com/docs/build/unit-tests; reproducible streams: ADR-0010 and https://docs.python.org/3/library/random.html#notes-on-reproducibility.
