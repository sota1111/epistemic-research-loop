# Development progress

**Progress lives here, not in Linear.** Linear issues carry a pointer to this repository and the
scope of a single unit of work; what was built, what it is checked by, and what is still open are
recorded here and in the [capability matrix](capability_matrix.md).

## How to check the state of the work yourself

```bash
uv sync --extra dev
uv run pytest -q                       # every claim in the capability matrix has a test here
uv run pytest -q --cov=epistemic_loop  # coverage gate is 85%
uv run ruff check src tests && uv run mypy src
uv run erlctl run status --run-id $RUN  # phase, phase evidence, validation reuse, brief, budget
uv run erlctl report run --run-id $RUN  # per-run audit summary from the canonical event log
```

`git log --oneline` is the other half of this record: every change lands through a PR whose title
names its Linear issue.

## Milestones

| Date | Milestone | Evidence |
| --- | --- | --- |
| 2026-08-24 | MVP: schemas, event store, gates, utility, holdout, contamination, CLI | `tests/unit`, `tests/property` |
| 2026-08-24 | Autonomous loop and the Linear execution contract (SOT-3053) | `tests/e2e/test_autonomous_loop.py`, `docs/verification/control_plane_linear_roundtrip.md` |
| 2026-08-24 | Control-plane Linear round trip verified against the live API | `docs/verification/sot-3053/` |
| 2026-08-24 | Capability closure: derived phase evidence, exploiter hand-off, validation adaptivity, discovery-scored benchmark, local-scoring cadence | `tests/unit/test_phase_evidence.py`, `tests/integration/test_exploiter_handoff.py`, `tests/unit/test_validation_adaptivity.py`, `tests/e2e/test_local_scoring_loop.py` |
| 2026-08-24 | Live verification on IEEE-CIS Fraud Detection: 16 adaptive rounds, 21 auto-filed Linear tickets, 1 Kaggle submission, against an exploiter-only control | [ieee_cis_autonomous_loop](verification/ieee_cis_autonomous_loop.md) |
| 2026-08-25 | Selection v2 started: research-state design fixed, preregistered likelihood forecasts and belief-conditioned mechanical EIG wired through the controller | `tests/unit/test_scoring.py`, `tests/integration/test_research_loop.py` |
| 2026-08-25 | C-lite minimum implemented: four system modes, validation-world posterior, EVSI/risk, QD/evolution, independent counter-experiments, OOF diversity, locked final artifacts, four-arm benchmark | `tests/unit/test_validation_worlds.py`, `tests/unit/test_qd_archive.py`, `tests/unit/test_oof_diversity.py`, `tests/integration/test_c_lite_components.py` |
| 2026-08-25 | Specification closure: executable validation splits, lineage-enforced evolution, Monte Carlo EIG, online calibration, preferred-state allocation, cross-fitted OOF ensembles, measured resource/retry reconciliation, replay manifests, contamination variants, and strict terminal final lock | `tests/unit/test_validation_splits.py`, `tests/unit/test_oof_ensemble.py`, `tests/unit/test_calibration_and_monte_carlo.py`, `tests/e2e/test_autonomous_loop.py`, `tests/integration/test_local_executor.py`, `tests/integration/test_c_lite_components.py` |
| 2026-08-25 | IEEE-CIS branch-isolated agents: three CLI-backed System C processes selected and completed three distinct semantic experiment designs from one clean initial commit | [ieee_cis_branch_agents](verification/ieee_cis_branch_agents.md), `scripts/verify_branch_agent_diversity.py` |
| 2026-08-26 | C-lite v0.2 scaling correction: private belief islands, selective evidence, semantic collapse control, resource/artifact gates, IEEE-CIS forward/UID plugin, multi-candidate archive and final meta-selector | [v0.2 specification](c_lite_revision_v0.2.md), `tests/unit/test_c_lite_v2.py`, `tests/unit/test_ieee_cis_v2.py`, `tests/unit/test_candidate_archive_v2.py` |
| 2026-08-26 | IEEE-CIS v0.2 multi-island real-data verification: three generic branches produced three semantic candidate families, sequential resource admission, valid OOF artifacts and a locked nested ensemble | [multi-island verification](verification/ieee_cis_multi_island_v02.md), `scripts/run_ieee_cis_multi_island_validation.py`, `scripts/finalize_ieee_cis_multi_island_validation.py` |
| 2026-08-26 | IEEE-CIS v0.3 dynamic-structure verification: three no-role islands selected distinct solutions, the controller generated a maturation fork only after a high-leverage hypothesis appeared, and sequential execution produced three OOF candidates plus a locked blend | [v0.3 multi-island verification](verification/ieee_cis_multi_island_v03.md), `scripts/run_ieee_cis_multi_island_v03.py`, `scripts/finalize_ieee_cis_multi_island_v03.py` |
| 2026-08-26 | IEEE-CIS v0.3 adaptive Cycle 2--4 verification: agent-local evidence drove nine sequential candidate/ablation runs with zero semantic duplicates and zero resource failures; prediction errors nevertheless remained near one effective direction | [adaptive-cycle verification](verification/ieee_cis_adaptive_cycles_v03.md), `scripts/finalize_ieee_cis_adaptive_cycles_v03.py` |
| 2026-08-26 | IEEE-CIS v0.3.1 measurement closure: frozen four-submission Hidden endpoint, 354,324-row common OOF × 3 seeds, terminal Payment-process debt, Predictive Collapse/Stagnation split, and a 3/3 clean replay | [v0.3.1 verification](verification/ieee_cis_v031_measurement.md), [v0.3.1 specification](c_lite_revision_v0.3.1.md) |

## What the last milestone changed

Five capabilities were specified and partly modelled but not reachable end to end. Each is now
wired, defaulted, and covered:

1. **Phase transitions were never automatic.** The unattended loop passed an empty `PhaseEvidence`
   every round, so a run stayed in discovery forever and the anomaly return path was unreachable.
   `controller/phase_evidence.py` now derives all six flags from the event log.
2. **The exploiter hand-off was unreachable.** `synthesize_research_brief` existed and was never
   called; `ResearchBriefCreated` was never emitted. `derive_brief`, `handoff_to_exploiter`, and
   `erlctl brief` close it, and exploitation cannot begin without it.
3. **Nothing bounded adaptive reuse of the working validation split.** `holdout/adaptivity.py` plus a
   `hard_gate` check now bound selecting queries per split — see
   [validation adaptivity](validation_adaptivity.md).
4. **The benchmark scored rank only.** `GoldFinding` and `concept_match` were dead code. The
   evaluator now reports discovery rate, CV–private gap, and regret removed per extra CPU-hour, with
   `iid_easy` as an explicit negative control.
5. **A round that selected nothing stalled the loop.** `replan` returns it to planning with a
   recorded reason, which is what makes a 10+ round unattended run survivable.

## What the IEEE-CIS verification changed

Running the loop against real data surfaced five defects that no unit test had caught, each fixed
with a regression test: `dispatch` recorded an attempt before validating the transition;
`kaggle submit` wrote its ledger only after waiting for a score, so a timeout lost a spent
submission; the Kaggle reference was parsed out of upload chatter; the configurable
`max_consecutive_optimization_experiments` knob was never read by the gate, which stalled the
exploiter control arm at round four; and `beliefs update` could judge only one hypothesis per round.
See the [verification record](verification/ieee_cis_autonomous_loop.md) for the measurements, and for
what it did **not** establish.

## Known limitations

These are deliberate and unfinished, not oversights:

- **The IEEE-CIS primary endpoint and common first-level cross-fit are now measured, but they failed their research gates.**
  The frozen v0.3 candidate did not beat the canonical Private AUC; 354,324 common OOF rows across
  three seeds confirmed Predictive Collapse. Matched-budget v0.2/v0.3, Comm-0/S/F and a second
  competition remain open, so the result is not a general system comparison.
- **The Research-to-Exploitation transition has not been observed in a real run.** It is implemented
  and unit-tested; the IEEE-CIS run stayed in discovery because its findings kept failing
  replication, which is the policy working rather than failing. The arithmetic is in the record.
- **`uncertainty_threshold` is a `decide_phase` argument default, not a config field.** The phase
  policy's single most consequential number cannot currently be set per competition.
- **The synthetic benchmark is a harness test.** Its regrets are stipulated. It shows the selection
  policy prefers informative actions; it is not evidence about a real competition. The IEEE-CIS
  profile in `configs/benchmarks/` is superseded by `configs/verification/`; AMEX, H&M and Optiver
  have not been run.
- **The adaptivity guard bounds queries, it does not de-bias the estimates already taken.**
- **`normalized_cost` scales are stipulated defaults**, not fitted to a real worker fleet.
- **Preferred-state targets are configured, not learned across competitions.** System C now derives
  the current gap and uses it in allocation, but leave-one-competition/domain-out learning of a
  target distribution remains outside C-lite.
- **Forecast calibration is online but data-hungry.** It records categorical and interval metrics
  and shrinks future priors for poorly calibrated agents/categories; it does not fit a non-parametric
  calibration map from a handful of early-run observations.
- **Portfolio-level information redundancy and broader role-scoped proposal agents remain open**; see
  [research-state-aware experiment selection](research_state_selection.md).
- **The local executor is a bounded Linux development sandbox**, with CPU affinity/time, RAM and
  Python-network enforcement. Read-only mounts and language-agnostic network namespaces remain the
  production control plane's responsibility; see [security](security.md).

## Where to read next

- [Capability matrix](capability_matrix.md) — requirement → code → test, one row each.
- [Architecture](architecture.md) — the repository boundary and the Linear interface.
- [Research protocol](research_protocol.md) — the per-round state machine.
- [Exploiter handoff](exploiter_handoff.md) · [Validation adaptivity](validation_adaptivity.md) ·
  [Benchmark protocol](benchmark_protocol.md) · [Holdout policy](holdout_policy.md) ·
  [Leaderboard policy](leaderboard_policy.md) · [Contamination policy](contamination_policy.md)

## 2026-08-25 — cycle retrospective

[`verification/cycle_retrospective.md`](verification/cycle_retrospective.md) reviews runs 001–009
and all seven Kaggle submissions against the now-visible private leaderboard. Three findings worth
carrying forward:

- Local CV had **no** rank correlation with the public leaderboard (tau +0.00) and slightly negative
  with the private one (tau −0.20). The candidate local CV ranked last won the private board.
- The unattended loop changed its own research question from a number it had measured two rounds
  earlier, and separately diagnosed and repaired a tooling defect from a failure message four
  minutes before the operator fixed the same thing.
- Eight of the nine defects fixed this cycle were one defect: a constraint enforced in code that the
  party expected to satisfy it never reads.

## 2026-08-25 — ROGII late-submission run stood up

New competition substrate: `rogii-late` (`sota1111/rogii-late`, Linear project `rogii-late`,
`configs/verification/rogii_late.yaml`). The competition closed 2026-08-05 but still accepts
scored submissions, five a day, notebook-only.

Three findings from standing it up, all recorded in that repository's `docs/`:

- **The advertised metric is wrong.** The Kaggle API reports `Mean Squared Error`; the organiser's
  task deck says RMSE, and an all-zero submission scores 11551.955 — the scale of TVT, not its
  square. `metric_direction: minimize`, `primary_metric: rmse`.
- **The apparent leak is not one.** All three test wells appear under `train/` with every shared
  input column identical, and the train copy carries TVT for the withheld rows. It cannot be the
  graded answer: the smallest absolute TVT in those copies is 11587.05, and no subset of values
  that large has an RMS of 11551.955. Cost of checking: zero submissions.
- **A single-well method interface would have made the task's own stated signal inexpressible.**
  The deck says neighbouring wells share geological dip. The first harness fitted nothing and saw
  one well at a time, which showed up as `rmse_split_gap: 0.0` — a split comparison that could not
  ever differ. The interface now has a fit stage over the fold's complement.

The private score is sealed on arrival (`.sealed-scores-rogii`, `public_feedback: numeric`), since
a late submission returns it unasked. `rogii-late/scripts/submissions.sh` redacts it from the
submission listing.

Still open, unchanged from the cycle retrospective: the `competition_repo` executor writes no
`result.json`, so `run loop` cannot yet close the Linear round trip; `metric_direction` is read
only into the world model and never reaches scoring; and submission timing is still a static
priority list rather than a decision.

### The three gaps, closed

**The Linear round trip.** `run loop` polled `.results/<run>/<experiment>/result.json` for every
executor, and only the local one writes there — so the `competition_repo` executor timed out on
every round it ever ran, which is why no unattended run had completed a round trip. The round now
asks the executor. `RunState` remembers the dispatch attempt so the request can be rebuilt after a
restart without opening a second ticket, and a task the tracker closed without writing metrics
comes back as a failure carrying the state that ended it instead of as silence.

**Metric direction.** `higher_is_better` had no caller in `src/`. `arm_summary` read `roc_auc` and
took a maximum, so on a minimised competition it reported an arm's worst result as its best and
reversed the sign of the calibration gap. It now takes the metric and direction from the run
config. The proposer's exposure is different in kind — `mean_gain` is an expected improvement
whose sign the model chooses, and utility is maximised over it — so the convention is stated on
the field's own schema, which is what the model reads.

**When to submit.** `plan_submission` was a duplicate guard dressed as a decision. The new policy
(`controller/submission_policy.py`, `erlctl kaggle decide`) starts from the measured fact that a
local estimate need not order the leaderboard: before the relationship is measured, a submission
buys it and spread beats quality; once measured and holding, only an improvement larger than the
local noise is worth spending on; once measured and absent, being locally best is not a reason at
all. Candidates are read from the event log so the artifact and its number cannot drift apart, and
the command submits nothing — it prints a recommendation whose refusals are as legible as its
spends.

`rogii-late-2026-08` is initialised and in `hypothesizing`, with the world model carrying the
solver interface and its accepted argument values.

### Defect 10, found on the first ROGII round

The same shape as the nine before it: *a constraint enforced in code that the party expected to
satisfy it never reads.*

`CompetitionRepoAdapter.submit` requires `implementation_request.brief` with four fields. It said
so nowhere else. The designer was handed `allowed_command_prefixes` — a shell executor's
vocabulary — and wrote a command. Design, the hard gate and selection all passed; the round died
at dispatch on a requirement any of them could have checked.

What makes it the tenth rather than a new kind: the requirement lived at the point of use, not at
the point of authorship. The fix is the same shape too — `ExecutionContract` moves it to both
places that need it, the gate and the designer. Adding the check without also telling the designer
would have converted a dispatch failure into a selection failure and kept the round lost.

The proposals themselves were sound — `duplicate_scan` over the full parquet, `baseline --method
zero` to re-derive the harness calibration against the known public all-zero score,
`split_comparison` of random against spatial folds. Only their shape was wrong, which is the
signature of this defect class: the research is fine and the plumbing loses it.
