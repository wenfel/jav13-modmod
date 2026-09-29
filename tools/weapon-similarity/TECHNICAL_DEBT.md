# Weapon similarity technical debt ledger

This file is the durable handoff for known non-blocking limitations and deferred work in
`tools/weapon-similarity`. It complements `README.md`, `ANALYSIS_REPORT.md`, and
`BENCHMARK_CASES.md`; it is not a substitute for those design documents.

## Baseline

PR #5 (`feature/weapon-similarity-analysis`) was audited and merged into
`country-filter`.

- approved feature head: `d880e44c0f030e91fc6f99feed349797d9527d20`
- merge commit: `8c471fef2c52f77bfe70f3b8d420afa7d7b1c0b8`
- checked-in snapshot blob: `ab7baacacb2aba8e7d320f9bd6ef651f986edfd3`
- merge-time CI: snapshot regeneration, Python syntax, analyzer runtime smoke, data-case,
  JA2 build, and JA2UB build all green
- PR #5 changed only the workflow and `tools/weapon-similarity/*`; no game-data files

Do not reopen resolved PR #5 findings merely because an older handoff or report mentions
them. Verify the current branch first.

## Open debt

### WS-D001 — analysis dependency reproducibility

**Status:** open, non-blocking.

`requirements.txt` currently uses lower bounds only:

- `numpy>=1.24`
- `pandas>=2.0`
- `scikit-learn>=1.3`

The deterministic snapshot generator is standard-library-only and is not affected.
However, PCA, k-means, and analyzer CI may execute against different dependency versions
over time.

**Follow-up:** decide whether to add upper bounds, a constraints file, or a lock file and
pin the Python version used for analysis CI. Treat this as reproducibility policy, not a
current correctness defect.

### WS-D002 — reload-reduction clamp differs from literal runtime expression

**Status:** open, non-blocking parity question.

The extractor computes intrinsic reload reduction with
`max(0, 100 - percent_reload)`. The audited C++ `GetAPsToReload()` expression does not
contain that explicit clamp.

For normal 0–100 percentage-reduction values the arithmetic is equivalent. At the PR #5
baseline, firearm data contains no nonzero intrinsic reload-AP reduction, so this does not
affect the checked-in snapshot or current rankings.

**Follow-up:** when strict parity for unusual/out-of-range data matters, decide whether the
Python model should remove the defensive clamp or deliberately retain it and document the
difference. Add a synthetic regression if this behavior is changed.

### WS-D003 — NCTH effective-intrinsic calibration remains incomplete

**Status:** open, already documented in `README.md` and `ANALYSIS_REPORT.md`.

The active checked-in model is OCTH. Stance-specific NCTH item modifiers do not yet have a
finalized aggregation policy because the intrinsic model intentionally excludes soldier
stance.

**Follow-up:** do not claim NCTH runtime equivalence until a stance-aware or otherwise
explicit aggregation policy is designed, benchmarked, and tested.

## Deferred scope, not defects

These are intentionally outside PR #5 and should not be mistaken for regressions:

- runtime C++ filtering/replacement implementation;
- historical-status data population/stress testing;
- production-year completeness work where the relevant metadata branch has not yet been
  integrated;
- broader family assertions beyond the explicitly benchmarked replacement families.

## Resolved audit findings

The following were fixed before PR #5 merge and should remain closed unless new evidence
shows a regression:

- **WS-R001:** analyzer `load_dataset()` now carries `tactical_role` and
  `replacement_family`; CI also executes a real nearest-neighbour analyzer smoke test.
- **WS-R002:** cross-type replacement-family policy and calibre policy are finalized for
  the active OCTH model: explicit audited families, strict fire-mode preservation, and a
  bounded same-calibre near-tie preference.
- **WS-R003:** sparse OCTH `ToHitBonus` / `AimBonus` scaling uses 10-point minimum
  replacement-distance scales; nominal weights were not changed.
- **WS-R004:** runtime autofire integer semantics for automatic shotguns are mirrored.
- **WS-R005:** the stale P90 report example was corrected from `7 -> 2` to `7 -> 5`.
- **WS-R006:** reload AP modifier/reduction arithmetic now retains the raw value through
  multiplication and performs one final `int()` conversion, avoiding the audited
  double-truncation discrepancy.

## Re-entry checklist

Before changing the model in a later session:

1. verify the live `country-filter` head and whether newer PRs changed the source XML or
   configuration inputs;
2. run `python tools/weapon-similarity/check_weapon_features.py`;
3. run the analyzer smoke/benchmark cases relevant to the proposed change;
4. distinguish semantic-policy changes from numeric-weight/normalization changes;
5. update this ledger when debt is added, resolved, or invalidated by later repository
   changes.
