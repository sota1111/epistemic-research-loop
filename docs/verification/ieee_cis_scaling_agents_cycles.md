# IEEE-CIS agent/cycle scaling verification

## Preregistration

Recorded before the scaling runs at `2026-08-26T01:01:45Z`.

The question is whether additional independent agents or additional adaptive cycles can move the
system from generic diagnostics toward the structure of strong IEEE-CIS solutions. The experiment
extends the three existing branch-isolated runs from one to three completed cycles, with portfolio
size one. The same nine observations support a nested matrix:

| Cell | Interpretation | Experiment opportunities |
| --- | --- | ---: |
| 1 agent x 1 cycle | original anchor | 1 |
| 3 agents x 1 cycle | breadth without adaptation | 3 |
| 1 agent x 3 cycles | depth with adaptation | 3 |
| 3 agents x 3 cycles | combined scaling | 9 |

The equal-opportunity comparison is `3 agents x 1 cycle` against each `1 agent x 3 cycles`
trajectory. Agent branches do not share memory and there is no meta-controller, so the union across
agents measures discovery potential, not an integrated solution.

All three cycle-one logs are snapshotted by their pre-run hashes and line counts:

| Run | SHA-256 | Lines |
| --- | --- | ---: |
| `ieee-cis-workstream-01` | `f3dbc7e6fce1748567e58c76586689f26a3a372e0442a0d5d2c24b6225794bff` | 45 |
| `ieee-cis-workstream-02` | `4f7b1f11a34f156e7782b03a9da4eb4304df500d23a9a267ecbf51bf23d810a5` | 44 |
| `ieee-cis-workstream-03` | `4aad053fbc7bbb441e65de82602d01a1be1c1ce71ab4f14d8416449437fb6293` | 39 |

### Top-solution rubric

The rubric is fixed from the first-, 15th-, 17th-, and 41st-place primary write-ups before reading
the new results. A text mention earns no credit by itself. Levels are `0`, `0.25`, `0.5`, `0.75`,
and `1.0`: absent; hypothesis/code only; executed artifact without a counterfactual forward check;
one honest forward or fold-safe check; replicated and adopted in a final candidate.

| ID | Capability | Weight |
| --- | --- | ---: |
| T1 | validated client/UID reconstruction | 15 |
| T2 | multi-horizon forward validation with a time gap | 18 |
| T3 | fold-safe UID-conditioned aggregation that generalizes beyond the UID | 12 |
| T4 | known/new/questionable-client evaluation or routing | 12 |
| T5 | validated client-level post-processing or label transfer | 10 |
| T6 | distinct model families with measured OOF error complementarity | 12 |
| T7 | adversarial/time/client-consistency feature control | 10 |
| T8 | explicit D/V temporal or structural handling | 6 |
| T9 | OOF/cross-fit ensemble or stack selection | 5 |

Total is 100. Classification is: `>=85` complete top-like; `70-84` strong upper-solution
signature; `50-69` partial competition-specific; `25-49` generic/early; `<25` diagnostic-only.
"Approaching a top solution" additionally requires total `>=70`, core `T1+T3+T4+T5 >=25`,
`T2 >=13.5`, and either `T6 >=9` or `T4+T5 >=16`. A target-leaking aggregation is invalid. Without
forward fraud-label validation the score is capped at 49; without a candidate/submission pipeline
the result remains diagnostic rather than a completed solution.

### Falsifiable predictions

1. If breadth is sufficient, the three cycle-one union will cover materially more rubric items than
   any one cycle-one run and at least one agent will leave the `<25` diagnostic-only band.
2. If adaptive depth is sufficient, at least one three-cycle trajectory will enter the `>=50`
   competition-specific band and add a UID/client item (`T1`, `T3`, `T4`, or `T5`).
3. If combined scaling can reach a top solution, the nine-experiment archive will satisfy the
   top-approach gate and at least one individual branch will contain a runnable candidate pipeline.
4. If the action space is the limiting factor, more cycles may improve T1/T2/T7/T8 but T5/T6/T9
   will remain zero because the exposed solver supports neither multi-family ensembles nor
   client-level post-processing.

## Results

The three runs were continued concurrently for two requested cycles each. The campaign ran from
`2026-08-26T01:02:54Z` through `2026-08-26T01:28:23Z` (25 minutes 29 seconds wall time). No
leaderboard or sealed holdout was queried.

### Selected experiments

| Run | Cycle | Selected experiment | Terminal result | Main observation |
| --- | ---: | --- | --- | --- |
| 01 | 1 | time-aware adversarial validation | completed | adversarial AUC `0.925393` |
| 01 | 2 | adversarial validation without V | completed | adversarial AUC `0.911966` |
| 01 | 3 | adversarial validation with minimal policy | completed | adversarial AUC `0.712049` |
| 02 | 1 | univariate target-AUC scan | completed | 432 features, max AUC `0.755165` |
| 02 | 2 | per-feature identity scan | failed | command exited 0 but omitted three required artifacts |
| 02 | 3 | identity ablation under time k-fold | failed | `ArrowMemoryError` while loading parquet |
| 03 | 1 | raw-feature adversarial validation | completed | adversarial AUC `0.924344` |
| 03 | 2 | duplicate/entity overlap scan | completed | entity overlap `0.8282`, exact-row overlap `0.0` |
| 03 | 3 | repeated duplicate scan | failed | `ArrowMemoryError` while loading parquet |

The final logs are bound by these hashes:

| Run | Final SHA-256 | Events |
| --- | --- | ---: |
| `ieee-cis-workstream-01` | `2aa533b796fc96e3795a60a853841632b256dd9a7f2da991e50d07a5216e4626` | 93 |
| `ieee-cis-workstream-02` | `6752c0f9241aeadb0d273a22f5cf34279fd9bdd64a65865243b7a38409425d26` | 74 |
| `ieee-cis-workstream-03` | `dfb615c0c4adf9e8b11510a5bcc401a66718838528fdd9b3d6215b49ed1aec37` | 75 |

Across all nine selections, six completed and three failed. For the six newly requested cycles the
completion rate was only `3/6 = 50%`; the original three cycle-one experiments were all complete.
Two failures were concurrent-memory failures, so this campaign measures the operational cost of
parallel scaling as configured, not an intrinsic failure rate under resource-isolated execution.

The additional cycles recorded 229,193 output tokens and 880,587 cache tokens. They expanded the
four command-level experiment families to adversarial validation, feature AUC, feature comparison,
and duplicate scan. Four of nine selections were adversarial validation, two were feature AUC, and
two were duplicate scans, so nominally distinct experiment IDs still contained substantial
semantic repetition.

### Rubric result

| Archive or trajectory | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | Total | Band |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| WS01, cycle 1 | 0 | 0 | 0 | 0 | 0 | 0 | 5.0 | 1.5 | 0 | 6.5 | diagnostic-only |
| WS02, cycle 1 | 0 | 0 | 0 | 0 | 0 | 0 | 2.5 | 0 | 0 | 2.5 | diagnostic-only |
| WS03, cycle 1 | 0 | 0 | 0 | 0 | 0 | 0 | 5.0 | 1.5 | 0 | 6.5 | diagnostic-only |
| 3 agents x 1 cycle, union | 0 | 0 | 0 | 0 | 0 | 0 | 5.0 | 1.5 | 0 | 6.5 | diagnostic-only |
| WS01, 3 cycles | 0 | 0 | 0 | 0 | 0 | 0 | 7.5 | 3.0 | 0 | 10.5 | diagnostic-only |
| WS02, 3 cycles | 0 | 0 | 0 | 0 | 0 | 0 | 2.5 | 0 | 0 | 2.5 | diagnostic-only |
| WS03, 3 cycles | 3.75 | 0 | 0 | 0 | 0 | 0 | 5.0 | 1.5 | 0 | 10.25 | diagnostic-only |
| 3 agents x 3 cycles, union | 3.75 | 0 | 0 | 0 | 0 | 0 | 7.5 | 3.0 | 0 | 14.25 | diagnostic-only |

WS03 receives only hypothesis/code-level T1 credit: the coarse UID's overlap was measured, but its
precision as a client identity and its fraud-label generalization were not. No completed experiment
used forward fraud-label validation, UID-conditioned aggregation, known/new-client scoring, a
second predictive model family, OOF predictions, an ensemble, or client post-processing.

The preregistered breadth prediction failed: pooling three one-cycle agents did not move the archive
out of diagnostic-only. The depth prediction also failed: no three-cycle trajectory reached 25,
much less the predicted competition-specific threshold of 50, and no selected experiment executed
UID aggregation. The combined top-approach prediction failed at `14.25/100`; the mandatory core,
forward-validation, and ensemble/client-specialization gates all failed.

### Structural ceiling

The negative result is not evidence that an unlimited, code-writing agent could never rediscover a
top solution. It is stronger and narrower: with this system's current shell execution contract,
the reachable action space cannot express the top pipeline.

- The client key is fixed to `card1 + addr1 + P_emaildomain`; the agent cannot invent and implement
  the first-place UID search or D/reference-date alternatives.
- The only UID aggregate exposed is TransactionAmt mean/std/count plus three frequency encodings.
- Predictive models are restricted to LightGBM and logistic regression. There is no CatBoost,
  XGBoost, model-complementarity measurement, stack, or ensemble.
- The runner has no known/new/questionable-client routing and no client-level post-processing.
- The experiment prompt explicitly forbids inline code and scripts that do not already exist.

Under the most generous evidence levels the current runner can plausibly earn T1 `0.75`, T2 `0.75`,
T3 `0.75`, T4 `0.5`, T7 `1.0`, and T8 `1.0`, but T5/T6/T9 remain zero. That ceiling is
`55.75/100`, below the 70-point approach threshold, and it also fails the mandatory T6-or-client
specialization gate. More agents and cycles can search this fixed vocabulary more thoroughly; they
cannot cross that expressivity boundary.

### Corroborating longer-run evidence

The earlier IEEE-CIS verification reached 20 completed epistemic experiments and still performed no
optimization, stayed in discovery, and submitted an untuned baseline. Its matched 20-experiment
exploiter obtained public AUC `0.938967` versus `0.934969` for the epistemic arm, while the prior
report records that the epistemic arm never transitioned to exploitation. This is not an independent
replicate, but it agrees with the three-cycle result: additional cycles improve structural diagnosis
without automatically producing a competitive final pipeline.

## Conclusion

Increasing agents or cycles has a non-zero chance of discovering more *reachable* structure: in
this campaign the union score rose from `6.5` to `14.25`, the V/time/identity ablations became more
specific, and entity overlap was measured. It did not approach a top solution. Under the current
fixed solver, reaching the preregistered top-solution state is impossible regardless of agent or
cycle count. A meaningful next experiment must first add a code-development/exploitation contract,
cross-agent memory and a final meta-selector, then repeat a matched-budget multi-seed scaling matrix.
