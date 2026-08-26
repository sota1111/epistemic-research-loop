# IEEE-CIS C-lite v0.3 dynamic-structure multi-island verification

## Conclusion

Three generic agents started from the same IEEE-CIS base commit and independently produced three
different runnable solutions.  Resource admission classified all proposals as Heavy, rejected
parallel probes, and ran them sequentially.  All final candidates satisfy the eleven-file artifact
contract, contain honest OOF predictions, and contain 506,691-row test predictions and submissions.

The run validates v0.3's dynamic behavior: no agent was assigned a structural role, but island 01
self-registered a high-leverage payment-process hypothesis.  The controller created a temporary
implementation/null-skeptic/verification fork and opened generic validation debt without telling
the other agents what structure to investigate.  The hypothesis was not promoted to validated
structure because that debt remains open.

This is a control-plane and local-validation result.  No leaderboard, hidden label, private score,
winner code, or winner write-up was consulted.  Hidden/private performance is not measured, and
overall IEEE-CIS acceptance remains false.

## Immutable base and generic branches

The canonical dataset snapshot contains 590,540 train rows and 506,691 test rows.  Its hash is
`sha256:7dc768c2650b5a6662bda57acae6f1e19ddb738984b8a2501373d2a24de4badb`.

All branches descend from `initial/ieee-cis-state` at
`ac3b46975e5da64570fb79d6e1141bc5c7525d0f`.  Branch names do not encode a solution:

| Branch | Final commit | Purpose |
| --- | --- | --- |
| `agents/v03-island-01` | `bd8380098c9c80119597dd85ba6f8e68bfd79ce6` | independent agent workspace |
| `agents/v03-island-02` | `729278b25b2e27a58ff2edb57517c5ad30c58168` | independent agent workspace |
| `agents/v03-island-03` | `3e8f2b09e91639346b088f97351dc4fb4b975019` | independent agent workspace |
| `validation/multi-island-v03` | `980b17c5107fe8481a1a11916aabe210e7520685` | clean integration and verification branch |

Each agent received the same generic prompt, dataset/artifact contract, and resource limit.  It did
not receive a fixed niche, another worktree, branch history, scores, a global best, or another
agent's beliefs.  The integrated branch passes all 11 agent-authored tests.

## Independent solution choices

| Agent | Self-selected solution | Forward result on 80k train sample |
| --- | --- | ---: |
| island 01 | amount decimal quantization and payment microstructure, missingness signature, periodic time | mean AUC `0.871052` |
| island 02 | reference-day anchors formed by `TransactionDT / 86400 - D_k` | mean AUC `0.872838` |
| island 03 | contextual amount frequency, mean ratio, and z-score by product/card/address/email | mean AUC `0.882869`; preregistered context gain `-0.001162` |

The absolute means are not a model ranking because folds are agent-local.  Island 03's contextual
features failed its own preregistered baseline comparison and were excluded from the final
decision-eligible blend.

The semantic detector found three singleton clusters: duplicate rate `0`, effective family count
`3.0`, dominant fraction `0.333`, and mean pairwise similarity `0.177778`.  Collective collapse was
false.  Thus the agents selected semantically different approaches without fixed roles.

## Dynamic structure maturation

Island 01 proposed `ISLAND-01-H-AMOUNT-RAIL-001`, a latent payment-process proxy that could affect
feature generation, routing, target/metric decomposition, and the train/test generating-process
model.  It also registered raw-amount, time/product-mix, and sparse-residue-overfit alternatives.
Because structural leverage crossed the generic threshold, the controller created temporary
implementation, null/skeptic, and verification children and opened debt for:

- competing-hypothesis tests and a confounder-preserving null;
- an independent implication and fold-safety verification;
- multi-context replication and adoption into a real decision.

No promotion assessment was created, the debt is open, and the observation was not routed as a
confirmed fact.  Islands 02 and 03 explicitly declined structural status because their hypotheses
changed only feature generation.  This is the intended distinction between a useful encoding and
a validated problem structure.

## Resource and artifact audit

All proposals were Heavy.  With `max_concurrent_heavy_experiments=1`, each attempted parallel
admission was rejected with `heavy experiment concurrency limit reached`; execution was therefore
sequential.  There were no memory or other resource failures.

The audit retained seven attempts.  Three first attempts exposed inconsistent dataset-hash
conventions.  A post-audit gate then caught island 01 truncating the test set under its sampling
flag.  These were infrastructure/artifact failures, caused no belief update, and were repaired
without changing hypotheses or models.  The final state is:

| Measure | Result |
| --- | ---: |
| Final candidate completion | 3 / 3 |
| Valid final artifact contracts | 3 / 3 |
| OOF artifacts | 3 / 3 |
| Full test/submission rows | 506,691 per candidate |
| Resource failures | 0 / 7 attempts |
| Invalid artifact attempts | 4 / 7 attempts |

The final candidate targets pass, but the attempt-level invalid-artifact rate is well above the
5% reliability target.  This is a material reliability finding, not hidden by successful retries.

## Common OOF comparison and locked output

Because candidates used local first-level folds, the finalizer compares only honest OOF row
intersections in time-ordered second-level folds.  It does **not** claim that a full common
first-level cross-fit was completed.

For all three candidates, 6,628 common OOF rows gave mean AUCs `0.863397`, `0.845899`, and
`0.857658`; their simplex ensemble gave `0.863878`.  Residual correlations were `0.973789` to
`0.988419`, covariance effective rank was only `1.082920`, and marginal ensemble MSE gain was
`0.0000321`.  The semantic designs differ, but their errors provide little effective diversity.

The decision-eligible island 01/02 comparison used 12,535 common OOF rows:

| Candidate | Mean AUC |
| --- | ---: |
| island 01 | `0.867461` |
| island 02 | `0.861228` |
| cross-fitted blend | `0.873772` |

The average weights were `0.503451` and `0.496549`, with marginal MSE gain `0.0003356`.  The
finalizer locked the corresponding 506,691-row submission.  It was not submitted to Kaggle.

## IEEE-CIS acceptance

| Criterion | Result |
| --- | --- |
| validated behavioral client proxy | **Fail** — none was claimed or passed G1--G9 |
| three or more forward horizons | Pass |
| fold-safe UID aggregate candidate | **Fail** |
| Known/New client slices | **Fail** |
| two listed model families | **Fail** — LightGBM only |
| three OOF candidates | Pass |
| one ensemble candidate | Pass |
| one locked submission | Pass |

Overall `IEEERunAcceptance.passed` is **false**.  The run confirms branch isolation, spontaneous
solution diversity, dynamic structure-maturation triggering, sequential resource safety, candidate
production, and final selection.  It does not establish a validated client proxy, sufficient model
or error diversity, a full common cross-fit, multi-seed reproduction, or primary-endpoint gain.

## Reproduction and audit hashes

```bash
uv run python scripts/run_ieee_cis_multi_island_v03.py \
  --sample 80000 --estimators 80 --threads 2 --timeout-minutes 60

uv run python scripts/finalize_ieee_cis_multi_island_v03.py
```

The first runner output is retained as the hash-contract audit, the second as the complete run, and
the isolated third run as island 01's full-test retry.  Runtime state is ignored under `.runs/` and
the external competition worktrees' `results/` directories.

| File | SHA-256 |
| --- | --- |
| initial controller report | `ba7508bb3ccb4fd7bd55f467417e7924a6df95282d4c15d92d286c9067fb3d0b` |
| complete controller report | `178ca6bf0b6fde1c4af4f722cfb3a4155ef24c956527c9935e9360c5023c5958` |
| island 01 retry report | `dd077a836899f2a71f499216831bc48762787fb7f5226f71edfd1ff3c52fb41a` |
| final report | `67a9b2e5b06b4238e5bff3e71f10d2994550f871cd4c95af7049efbb8a93d4b11` |
| locked submission | `86634793e066bc42f788397d145fe5812e3372d71a6abe8d8c32fadf9f34f741` |
