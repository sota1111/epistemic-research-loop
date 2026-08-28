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
| 2026-08-27 | C-lite v0.3.5 independent-agent qualification: local three-lineage portfolios, shadow recovery, observe-only population scorecards, and blind four-positive/four-negative structure controls | [v0.3.5 verification](verification/v035_independent_agent_qualification.md), [v0.3.5 specification](c_lite_revision_v0.3.5.md) |

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

## 2026-08-27 — v0.3.6 blind real-agent qualification

Three generic LLM agents independently completed eight opaque packs with four adaptive cycles per
pack. All submissions were hash-locked before controller truth was decrypted. Population-union
TSDR/TSRR/FSPR were 0.75/1.00/0.00, USTR was 0.875 after removing a circular sealed-gain condition,
and all engineering acceptance layers passed. The result is not uniform agent competence:
persistent-unit structure was missed by all agents, explicit negative rejection came entirely from
agent 03, agent 02 was poorly calibrated, and one agent-01 validated structure failed sealed
transfer. Communication modes, IEEE-CIS Hidden transfer, and an unused real benchmark remain
unmeasured.

## 2026-08-27 — v0.3.7 agent reproducibility and shared blind spots

Four new locked synthetic suites were evaluated under three generic agent identities and two
sampling conditions. The 24 suite-level evaluations were produced by six LLM trajectories; this is
recorded as a pilot limitation rather than claimed as 24 fresh-context runs. All outputs were
artifact-validated and hash-locked before truth unblinding, and the 24 agent-visible views had zero
truth-token findings.

Evaluation audit removed three optimistic paths: confirmation-time translation maximization,
persistent-positive credit without matched-negative rejection, and TSRR credit from an unsupported
`FALSIFIED` label. Controller-derived LOCO and failure stages were added without changing locked
predictions. Under the corrected evaluation, median agent TSDR/TSRR were 0.0833/0.0208, worst-agent
FSPR was 0.3333, shared blind-spot rate was 0.7917, and only one persistent ladder level was found by
one agent. The engineering qualification therefore failed. The surviving actionable structures
did transfer in 6/8 cases (pooled USTR 0.75, median gain +0.09431), locating the main bottleneck in
discovery/falsification rather than translation. P1's generic assumption challenge improved mean
TSDR and reduced mean FSPR relative to P0, but yielded only one persistent discovery; S1/S2 did not
show a consistent discovery advantage. Communication ablation remains intentionally deferred.

## 2026-08-27 — v0.3.8 fresh-context qualification with machine-audited provenance

The v0.3.7 design was re-run with new suite identities and four interventions only: one fresh
`claude -p` context per (suite, run) — 24 independent processes, CLI-authenticated with no provider
API key; a mandatory per-replicate null provenance artifact (permutation / feature / fold / model /
OOF hashes plus preserved statistics) validated before lock; controller-enforced lineage continuity
for posterior-commit and two-hit policies; and P1 as the single frozen prompt. Two development
suites (six fresh runs) were executed, locked, and opened first to fit the C1 isotonic map; the
qualification truth was never used for fitting. All 30 runs completed autonomously; three needed
one contract-repair retry (validation feedback only). Transcript audits found no forbidden-path
access; two hits were numpy warnings naming the interpreter's site-packages path and were reviewed
and allow-listed.

The engineering qualification still failed, but every gate metric improved: median agent TSDR
0.0833→0.1875, TSRR 0.0208→0.1875, worst FSPR 0.3333→0.2083, shared blind-spot 0.7917→0.7083,
median Brier 0.2614→0.1813 (now passing), persistent ladder 1/4→4/4 levels by 2/3 agents (now
passing), pooled USTR 0.75→1.00 with median sealed gain +0.2209. Observation-routing structure is
now found almost universally (23/24); the persistent-unit families remain near-blind at the
individual level (1–2/24 each). The dominant rejection blocker was located precisely: of 95
falsified declarations that failed evidence-based rejection, 73 co-reported an independent
implication strength above 0.05 in the same bundle — an internal contradiction, not missing
evidence. Twelve persistent-clear discoveries died at the matched-negative gate through this path.

## 2026-08-27 — v0.3.9 launched: terminal-resolution consistency

v0.3.9 adds exactly one intervention over v0.3.8: a pre-lock contract that a terminal resolution
must be internally consistent with the agent's own artifacts (falsified packs may not co-report
implication strengths above 0.05 or research gains above their own full-refit null in two or more
contexts; validated packs must report at least two implication supports). Repair feedback
references only the agent's own numbers, so nothing about structures leaks. New suites
v039-qual-e01..e04 were preregistered and locked with the same P1 prompt hash; C1 is reused from
the locked v0.3.8 development fit. The 24 fresh-context qualification runs are in flight.

## 2026-08-28 — v0.3.9 terminal-resolution consistency: single intervention, predicted effect

The only change over v0.3.8 was a pre-lock contract that a terminal resolution must be internally
consistent with the agent's own artifacts. Both preregistered predictions landed: median agent TSRR
rose 0.1875→0.6250 (agent-01 individually passed the 0.67 gate at 0.7083) and matched-negative
failures collapsed 27→5; the predicted risk (escape into inconclusive) did not occur. Worst-agent
FSPR passed its gate for the first time (0.2083→0.0833) and all three agents now discover on the
persistent ladder. Pre-unblinding contamination checks defused the adversarial-review concern:
12 of 13 repair attempts recomputed on data rather than relabeling, and single-attempt runs had
higher TSRR (0.702) than repaired runs (0.567), so the gain is not repair-loop compliance learning.
Side effects: promotion became more conservative (observation-routing 23→19, non-actionable 1→0,
Brier 0.1813→0.2043 now failing), and the failure funnel moved upstream — 88 of 116 undiscovered
positives now fail at the evidence stage. The contract lever is spent; per the v0.4.0 policy the
program moves to capability levers (configuration search over models and epistemic scaffolds) and
the preregistered IEEE-CIS bridge.

## 2026-08-28 — v0.4.0 Track A generation 1: configuration selection, not gate-chasing

Generation 1 ran 6 preregistered execution configurations (model x prompt-arm x CLI, one codex
reasoning variant per slot) x 4 replicates on a persistent-heavy suite that also introduced a
machine-composed structure-grammar family the designer does not hand-pick instances of. Selection
is by discovery-event count, not TSDR median, per the v0.4.0 policy pivot away from sequential gate
improvement. One replicate (codex sol, g04) was excluded before unblinding: the container's
unprivileged user-namespace creation is now blocked (`unshare` returns EPERM even as root), so
codex's workspace-write sandbox cannot write through either the shell or file-edit path — verified
by isolated smoke tests and recorded as a preregistration deviation. The evaluator's `excluded_pairs`
parameter (new, defaults to empty, v0.3.7/8/9 callers unaffected) lets the locked v0.3.7 evaluation
core handle the resulting 23-run batch without weakening the run-count integrity check.

Three of six configurations passed the >=2 discovery-event threshold for generation 2: opus-5xP1
(baseline, 7 events), fable-5xP2 (5), fable-5xP1 (2). Genuinely novel discovery occurred on the
structure-grammar family (5/23 and 9/23) — a direct instance of the policy's core aim, discovery of
previously-unseen structure. But the well-characterized persistent ladder positions 1-3 (clear,
noisy-proxy, delayed-history) collapsed to 0/23 each (from 7, 1, 5 out of 24 in v0.3.9), with
promotion-stage failures roughly tripling (16->41) — a plausible new contract-lever bottleneck from
this version's own implication-provenance requirement, not yet disentangled from suite/prompt
attention effects. The preregistered primary prediction (some configuration separates from the
opus-5 baseline) did not hold in the hoped direction: baseline was the top performer, meaning model
choice dominated the prompt-arm scaffold change in this generation. codex (sol/terra) continued the
evasion pattern flagged during generation 1 execution: terra reached zero terminal resolutions
across all 24 packs. Full detail:
[verification/v040_gen1_track_a_qualification.md](verification/v040_gen1_track_a_qualification.md).

## 2026-08-28 — v0.4.0 correction: the codex "evasion" was mostly an infrastructure defect

Asked to check whether codex and glm were getting a fair evaluation, forensic review of codex's own
session rollout logs (`~/.codex/sessions/`, not the truth store) found that the bwrap sandbox failure
that caused the g04/sol exclusion above had been intermittently corrupting every codex slot's
execution throughout generation 1, not just the excluded run. Command-level analysis of each codex
slot's accepted (locked) attempt: 4 of 8 were severely degraded (38-45% of commands bwrap-failed,
only 8-17 total commands completed versus hundreds in the clean slots), with transcript evidence of
an agent editing completion/honesty flags directly rather than completing blocked computation. This
directly confounded the published "codex avoids terminal resolution" interpretation with an
environment artifact.

Root cause: `-s workspace-write` depends on bwrap (Linux user namespaces), which this container
blocks unconditionally. Fix: switched to `-s danger-full-access` (no OS sandbox; isolation now comes
only from workdir-copy + prompt instructions + transcript audit, matching claude's
`--dangerously-skip-permissions` posture and the zai/GLM CLI, which has no OS sandbox at all).
Also pinned `-c model_reasoning_effort` explicitly per slot rather than relying on the shared,
mutable `~/.codex/config.toml` default — a related defect had let one accepted run silently execute
at effort=low instead of the preregistered xhigh.

All 8 codex slots, including the previously-excluded one, were backed up and re-executed under the
fixed runner: 0 bwrap failures, full 14-pack/42-context/5+-replicate submissions across the board.
Generation 1 now completes at 24/24 (the exclusion is lifted). Results changed materially for codex:
sol's verified discovery events rose 1->4 (now clears the generation-2 threshold, with 2 new false
promotions on a matched-negative pair), terra's rose 0->2 (also clears the threshold, with 5 false
promotions concentrated in a single suite instance where it over-validated 11 of 14 packs — a likely
one-off rather than a consistent pattern). Claude's four configurations were untouched. Generation-2
candidates are now opus-5xP1 (7), fable-5xP2 (5), and codex sol xP1 (4) — codex sol enters the
carry-forward set that a purely claude-side reading of generation 1 would have excluded. The
persistent-ladder L1-L3 collapse (0/24) is unchanged by the fix and now confirmed CLI-independent
(codex also finds zero after the correction), strengthening the implication-provenance-bottleneck
hypothesis over a codex-specific explanation. Old (contaminated) raw data preserved, uncommitted, at
`.runs/v040/agent_outputs_pre_sandboxfix_backup/`. Full disclosure of the correction, made after the
first report was already published, is in
[v040_gen1_preregistration.json](v040_gen1_preregistration.json)'s `post_registration_deviations`.
