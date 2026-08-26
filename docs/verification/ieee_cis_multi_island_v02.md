# IEEE-CIS C-lite v0.2 multi-island verification

## Scope

This record covers the first real-data run of the v0.2 multi-island control plane.  It answers four
questions:

1. Were generic agent branches created from the same IEEE-CIS base state?
2. Did isolated agents independently implement semantically different candidate-producing pipelines?
3. Did the resource, semantic-duplicate and artifact gates behave as specified?
4. Which IEEE-CIS acceptance criteria remain unmet?

No Kaggle leaderboard, hidden label, private score, winner code or winner write-up was consulted by
the three implementation agents or by the controller.  Hidden/private performance, the primary
endpoint in v0.2, is therefore **not measured**.

## Immutable inputs and branches

The shared dataset snapshot was read from `.data/ieee-cis/parquet`:

- train: 590,540 rows, 434 columns
- test: 506,691 rows, 433 columns
- canonical snapshot hash:
  `sha256:7dc768c2650b5a6662bda57acae6f1e19ddb738984b8a2501373d2a24de4badb`

The hash streams `manifest.json`, `test.parquet` and `train.parquet` in filename order, including
each filename and byte size.  Every completed candidate independently recorded the same hash.

All worktrees have merge-base `ac3b46975e5da64570fb79d6e1141bc5c7525d0f` on
`initial/ieee-cis-state`.  Names encode no solution choice.

| Agent | Generic branch | Final commit | Primary / secondary niche |
| --- | --- | --- | --- |
| 04 | `agents/agent-04` | `e10040b31cd068886601683f8f4b86e71c325a48` | temporal / validation |
| 05 | `agents/agent-05` | `dd1e2029d8b80b150effa006e73eb98d65d72a0e` | entity_client / feature_representation |
| 06 | `agents/agent-06` | `aad62c08f20180755e2881e52e2edf20686d8152` | model_family / falsification |

Each branch contains its own proposal, candidate CLI and tests.  All worktrees were clean after the
run; `results/` is ignored runtime state.

## Independence and solution choices

Agents received only the dataset location, artifact/safety contract, resource boundary and their
niches.  They could not inspect another new worktree.  No result, score, posterior or global best
was routed before all proposals were admitted.

| Agent | Independently selected candidate | Forward protocol | Candidate result |
| --- | --- | --- | --- |
| 04 | causal client velocity, recency and amount-deviation history with fold-local encodings | 4 horizons, 1-day gap, LightGBM | mean AUC `0.911145` on 40k sample |
| 05 | three-resolution UID proxy memory with target-independent count/amount/recency aggregates | 3 horizons, 7-day gap, LightGBM | mean AUC `0.861893` on 200k sample |
| 06 | paired LightGBM GBDT vs bagged-RF falsification gate under a fixed representation | 3 horizons, 7-day gap | GBDT selected, mean AUC `0.864784` on 40k sample |

The normalized semantic detector produced three singleton clusters.  Pairwise similarity was
`0.1667` for every pair and semantic duplicate rate was `0`.  QD occupied temporal,
entity-client and model-family cells before the ensemble cell was added.  Cycle-one collapse was
false: effective experiment-family count was `3.0`, dominant-cluster fraction `0.333`, and mean
proposal similarity `0.167`.

This establishes different solution *representations and decisions*.  It does not establish broad
model-family diversity: every predictive candidate ultimately used LightGBM, and Agent 06's GBDT
and RF booster modes count as two algorithms within one listed model family, not LightGBM plus
CatBoost/XGBoost/logistic/neural.

## Control-plane behavior

The controller entry point is `scripts/run_ieee_cis_multi_island_validation.py`.

It created owner-only belief files, one global queue/resource state, a global evidence vault and a
score-redacted candidate archive.  At cycle 1 each agent was routed only its own evidence:

- global evidence count: 3
- routed evidence count: 1 per producer
- cross-agent broadcasts: 0

Every proposal was classified Heavy.  While Agent 04 and then Agent 05 were reserved, an admission
probe for the next Heavy candidate returned `heavy experiment concurrency limit reached`.  The
three candidates therefore ran sequentially even though code development occurred in parallel.
No `ArrowMemoryError` or other resource failure occurred.

The first 40k-row Agent 05 attempt failed before training because a 7-day embargo left zero initial
training rows.  It was recorded as `FAILED_EXECUTION`; it did not update a posterior or enter the
archive.  The failed directory and logs remain intact.  Attempt 2 restored the preregistered
200,000-row resource profile, ran under a single Heavy reservation, and completed in 115.59 s.

| Measure | Result |
| --- | ---: |
| Final candidate completion | 3 / 3 (100%) |
| Execution-attempt completion | 3 / 4 (75%) |
| Resource failure rate | 0 / 4 (0%) |
| Runtime invalid artifact rate | 0 / 3 completed (0%) |
| OOF artifact generation | 3 / 3 candidates (100%) |
| Full-test prediction rows | 506,691 per candidate |

The attempt-level completion target of 90% was not met.  The candidate-level target was met after
the resource-profile retry.  Full-candidate multi-seed reproduction was not run; deterministic
seeds, source/environment hashes and smoke replay passed, but this is weaker than the v0.2
multi-seed research acceptance criterion.

## Artifact contract finding

The agents' first commits generated all eleven filenames but did not satisfy the controller's
schema-level contract.  Static controller inspection showed that the smoke candidates would be
`INVALID_ARTIFACT` because identity/hash, validation, leakage, reproducibility or flat numeric
metric fields were absent.  Each agent added a second commit and a test that directly invokes
`CandidateArtifactValidator`; all now return `valid=true`, `terminal_status=COMPLETED`.

This is evidence that exit code and file presence alone no longer imply success.  It also exposed an
environment boundary: candidate ML CLIs run in the competition environment, while validator
integration tests require the controller environment because the competition environment does not
install Pydantic.  The reproducible test form is:

```bash
PYTHONPATH=/workspaces/epistemic-research-loop/src:$PWD \
  uv run --project /workspaces/epistemic-research-loop \
  python -m unittest discover -s tests -p 'test_*.py'
```

Agent test totals were 5, 3 and 3, all passing.

## OOF diversity and final meta-selection

The candidate OOF sets differ because beliefs and validation designs remained local.  The finalizer
therefore used only 1,084 row IDs for which all three candidates had honest OOF predictions, sorted
them by time into three second-level folds, and assigned one common coarse-client slice using only
rows at least seven days earlier.

| Common slice | Rows |
| --- | ---: |
| Known | 932 |
| New | 109 |
| Questionable | 43 |

This is a nested second-level comparison, **not** the required full rerun of all feature pipelines
on identical first-level folds.  `full_common_first_level_crossfit_completed` is explicitly false.

| Candidate | Mean common-fold AUC |
| --- | ---: |
| Agent 04 | `0.898788` |
| Agent 05 | `0.919536` |
| Agent 06 | `0.910569` |
| Cross-fitted simplex ensemble | `0.948746` |

Residual correlations were high (`0.8819` to `0.9306`), prediction disagreement was low
(`0.0083` to `0.0157`), and covariance effective rank was only `1.3388` for three candidates.
Thus the agents chose different semantic solutions, but their prediction errors still collapsed
toward one effective direction.

The nested simplex ensemble reduced MSE from the best single `0.0269335` to `0.0264693`, a marginal
gain of `+0.0004642`.  Average weights were:

- Agent 04: `0.36148`
- Agent 05: `0.32193`
- Agent 06: `0.31659`

The corrected common-condition meta-selector locked the ensemble.  The locked file has 506,691
rows, columns `TransactionID,isFraud`, no nulls, and SHA-256
`0f28e8d94d5c2e2c0c7131358a39275a65fe795ad6a9da07c0f7238002b58cf2`.
It was not submitted or hidden-evaluated.

The finalizer's first output is retained as an audit attempt: it mixed common OOF performance with
agent-local New-client scores in one utility and selected Agent 06.  `final-corrected/` fixes that
comparability defect by deriving both overall and client-slice utility on the same 1,084 rows.

## IEEE-CIS run acceptance

| Criterion | Result |
| --- | --- |
| at least one validated UID | **Fail** — UID proxies were explicit, but no UID-free ablation/frequency-artifact rejection proved all seven conditions |
| at least 3 forward horizons | Pass |
| at least one fold-safe UID aggregate candidate | Pass (Agent 05) |
| Known/New client slice | Pass |
| at least 2 listed model families | **Fail** — LightGBM only |
| at least 3 OOF candidates | Pass |
| at least 1 ensemble candidate | Pass |
| at least 1 locked submission | Pass |

Overall `IEEERunAcceptance.passed` is **false**.  Separately, the full common first-level cross-fit,
multi-seed reproduction and Hidden/Private primary endpoint remain unmeasured.  Consequently this
run validates the new system path and demonstrates independent candidate production; it does not
establish a fully accepted or top-performing IEEE-CIS solution.

## Reproduction and audit files

```bash
uv run python scripts/run_ieee_cis_multi_island_validation.py \
  --sample 40000 --estimators 120 --timeout-minutes 60

uv run python scripts/finalize_ieee_cis_multi_island_validation.py \
  --final-name final-corrected
```

The Agent 05 retry is recorded separately because it changes only the resource profile, not the
hypothesis or candidate code. The runner now preserves Agent 05's 200k minimum automatically; the
historical first-attempt failure remains in this audit. Reproduction requires fresh generic
worktrees (or otherwise unused result paths), because both scripts refuse to overwrite artifacts.
Generated state is ignored by Git under
`.runs/ieee-cis-v02-multi-island-20260826/` and each worktree's `results/`.

Audit hashes:

| File | SHA-256 |
| --- | --- |
| controller report | `1e5c997cd4cff37ab3313bd9211e0bc549fdcdb9fa7f0d829fa8b79db92daa32` |
| Agent 05 retry record | `a029bbde8dbad46c092740b9dca9596329fe347d7e97a454cf9209eab9ae01d4` |
| corrected final report | `c5271bd34693ee2c877ca04a4dc6306d06cbb991b2137e36cc2ed66dc179acfd` |
| locked submission | `0f28e8d94d5c2e2c0c7131358a39275a65fe795ad6a9da07c0f7238002b58cf2` |
