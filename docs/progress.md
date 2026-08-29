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

## 2026-08-28 — codex sol reasoning-effort ablation launched; GLM integrated and smoke-tested

Two follow-ups from the sandbox-fix correction. First, `build_v040_suite` gained optional
`suite_ids`/`master_seed`/`configs`/`run_ids` parameters (defaulting to the generation-1
constants, so existing callers are unaffected) so a second study can reuse the same
grammar/pack-plan machinery without duplicating it. `scripts/run_v040_agent.py` gained a
small suite-id-keyed config registry (`_resolve_config`) so the same runner serves multiple
studies. Preregistered
([v040_sol_effort_ablation_preregistration.json](v040_sol_effort_ablation_preregistration.json))
and launched a 16-run independent side-probe: codex sol at reasoning_effort
low/medium/high/xhigh (CLI/model/prompt-arm held fixed at generation 1's C5), four replicates
each on a new suite (new master seed; generation 1's suites stay unblinded and unreused). Four
replicates rather than three because the shared v0.3.7-lineage evaluator hard-requires exactly
four suites. The preregistered prediction explicitly does not assume higher effort is better:
a "narrowing" hypothesis (higher effort converges faster, reducing hypothesis diversity even if
discovery holds or improves) is tracked via secondary diversity metrics
(semantic_family_count, effective_family_count, eecr, deep_lineage_completion_rate) alongside
discovery-event counts, not just the headline number.

Second, per the user's request to make the environment fair for codex and GLM, the GLM/zai CLI
(`/home/vscode/.local/bin/glm`, GLM 5.3 via the Coding Plan endpoint, API key sourced from the
project `.env` by the wrapper script itself) was integrated into the runner and smoke-tested.
Reading zai's tool implementations found it has no OS-level sandbox whatsoever (its file-editor
tool does `path.resolve()` with no confinement check), so isolation rests entirely on
workdir-copy + prompt instructions + transcript audit -- the same posture already adopted for
codex after the sandbox fix. Headless `-p` mode auto-approves all tool calls
(`confirmationService.setSessionFlag("allOperations", true)`), so no permission-skip flag is
needed. Verified under the exact restricted subprocess environment the runner actually uses
(PATH/HOME/LANG/TERM/SHELL only): authentication, file writes, bash execution, and JSONL
transcript output all work. No GLM study is preregistered yet -- integration is ready, but
placement (which generation, how many configs/replicates) is a decision for the next
preregistration.

## 2026-08-28 — sol reasoning-effort ablation: capacity beats narrowing, first true persistent_clear discovery

The ablation's replicate count was corrected from 4 to 6 (policy's own recommended lower bound)
before unblinding, per the same-day finding that 4 was an unexamined engineering shortcut, not a
statistical choice -- generalized `evaluate_v037_runs`/`evaluate_v038_runs` with an explicit
`expected_suite_count` parameter (default 4, existing callers unaffected) rather than leaving the
hardcoded suite-count check in place. All 24 runs (4 effort levels x 6 replicates) completed, audited
clean, and unblinded.

Results were unambiguous: discovery events rose monotonically with reasoning effort (low 2 ->
medium 3 -> high 4 -> xhigh 7), and so did every diversity metric (semantic_family_count,
effective_family_count, eecr) -- directly falsifying the preregistered "narrowing" hypothesis
(that higher effort would trade discovery for reduced hypothesis diversity) in favor of the
"capacity" hypothesis. More strikingly, `persistent_clear` -- 0/24 in generation 1 and 0 in the
scaffold-ladder screen so far, the single most persistent blind spot across every configuration
tested this session -- was genuinely discovered twice, both at high or xhigh effort, never at low
or medium. This is the first positive evidence that the persistent-ladder collapse is an
evidentiary-capacity problem (can the agent accumulate enough held-out statistical support to
cross the implication-provenance bar) rather than purely a contract-lever or hypothesis-generation
problem, and it points squarely at the still-untested cycle-budget lever (4 -> 8) as the next
priority. `high`'s 5 false promotions were all concentrated in a single suite instance (same
single-outlier pattern as generation 1's terra/g03), not spread across its 6 replicates. Full
detail: [verification/v040_sol_effort_ablation_qualification.md](verification/v040_sol_effort_ablation_qualification.md).

Separately, launched an independent scaffold-ladder screen (Opus x Sol, P1/P2/P3 crossed with both
models, 24 runs) per the user's explicit priority that Opus and Sol alone reach solution diversity
and unknown-structure discovery without depending on quota-limited fable/GLM. Wrote
`prompts/generic_research_agent/v040_p3.md` (P1 plus exactly one inserted self-critique-before-
promotion paragraph, cycle budget unchanged) and generalized `build_v040_suite`'s prompt-arm
validation to be driven by what the passed configs actually reference rather than hardcoded to
{p1, p2}. Preregistration explicitly discloses counter-evidence (the persistent-ladder collapse
already spans both prompt arms and both architectures in generation 1) and frames the goal as two
subproblems: hypothesis-generation diversity (this probe) versus evidentiary capacity (deferred to
a cycle-budget follow-up). Still running as of this entry.

Also discovered mid-session that this devcontainer's working directory is shared across concurrent,
unrelated sessions: another task performed `git checkout`/commit/PR-merge/pull in the same working
tree, silently moving this session's HEAD to `main` (which contains none of this work) while a
background batch was mid-flight. Caught and recovered (`git checkout system/c-lite-v0.3.8`) before
any subprocess spawn could fail; no commits were lost (branch refs are independent of HEAD), but
this is now a standing risk for any long-running background execution in this environment.

## 2026-08-29 — scaffold-ladder screen: P3 triples Opus's hypothesis diversity, claude finds persistent structure for the first time

All 24 runs (Opus x {P1, P2, P3} crossed with Sol x {P1, P2, P3}, 4 replicates each) completed,
audited clean, locked, and unblinded. One run (opus x P2) hit a legitimate terminal-resolution
self-consistency contract rejection after 3 repair attempts and was retried once successfully
through the batch's resumable design -- not an infrastructure failure.

Headline result: P3 (the new self-critique-before-promotion scaffold) raised Opus's mean
semantic_family_count from 3.00 (both P1 and P2) to 8.75 -- consistently across all 4 replicates
(12, 6, 9, 8 distinct families), not a single-run artifact -- while keeping false promotions at 0.
This is the most reproducible finding of the whole scaffold-ladder probe. Separately, and for the
first time across this entire session's data (generation 1, the sol-effort ablation, and this
screen), claude-family models found genuine persistent-ladder structure: opus x P1 discovered both
persistent_clear and persistent_compositional in the same suite instance, and opus x P3 discovered
persistent_noisy_proxy in a different one. P2, which had produced a 2.5x discovery-event swing for
fable in generation 1, did NOT help opus (discovery events P1=P3=9 > P2=7) and unlocked no
persistent family -- confirming the preregistered "model-dependent" outcome over "consistent
across architectures." Sol x P3's 7 false promotions were entirely concentrated in one suite
instance (the same single-outlier pattern already seen with generation 1's terra/g03 and the
sol-ablation's high/b05), not a systemic P3-plus-sol calibration problem.

Combined with the sol-effort ablation's finding that persistent_clear only appeared at high/xhigh
effort, the persistent-ladder collapse now looks less like a single uniform wall and more like a
low-probability event that several different capacity-increasing levers (high reasoning effort;
P1 or P3 scaffolds on a strong model) can each occasionally cross, while low effort and P2
specifically do not. Full detail:
[verification/v040_scaffold_ladder_qualification.md](verification/v040_scaffold_ladder_qualification.md).

## 2026-08-29 — Stage 2 confirms: persistent_delayed_history breaks for the first time, evaluator bug found and fixed

All 18 Stage 2 runs (Opus x P1, Opus x P3, Sol x P3 x xhigh, 6 replicates each) completed cleanly
in one pass -- no contract repairs needed, blindness audit clean. Unblinding first hit a genuine
latent bug: `evaluate_v037_runs`'s `agent_seed_aggregates` computed the full cross product of
observed agent ids x observed sampling seeds, which every prior study's symmetric run-id grid
happened to make identical to the actual submitted pairs, but Stage 2's asymmetric slot usage (no
agent-02-s17 configured) produced an empty group and a ZeroDivisionError. Fixed by iterating the
actual (agent_id, sampling_seed) pairs present in submissions instead of the cross product.
Verified empirically, not just argued: re-ran finalize on all three already-locked full-grid
studies (generation 1, Stage 1, the sol-effort ablation) and diffed their output JSON against what
was already committed -- byte-for-byte identical in all three cases -- before trusting the fix on
Stage 2's asymmetric data.

The headline result: `persistent_delayed_history` -- the only family with a 0/88 discovery base
rate across every prior v0.4.0 study -- was genuinely discovered twice, by both Opus x P1 and
Opus x P3. Every persistent-ladder family has now been discovered at least once (the cumulative
discovery ledger no longer has a family stuck at zero). Opus x P3 additionally discovered
persistent_clear in the same 6 replicates -- the first instance of one configuration finding two
distinct persistent families. Sol x P3's false-promotion count, which spiked to 7 (concentrated in
one suite instance) in Stage 1's n=4 screen, dropped to 0/36 at n=6, confirming it was the
single-outlier fluke suspected rather than a systemic P3-plus-sol calibration problem. But Opus x
P3's headline diversity effect did NOT fully reproduce: mean semantic_family_count fell from 8.75
(Stage 1, n=4) to 4.33 (Stage 2, n=6, all six replicates tightly in the 3-6 range) -- the direction
held but the earlier screening estimate substantially overstated the effect size, a textbook
illustration of why the screen-then-confirm design matters. Full detail:
[verification/v040_scaffold_ladder_stage2_qualification.md](verification/v040_scaffold_ladder_stage2_qualification.md),
updated ledger: [v040_discovery_ledger.md](v040_discovery_ledger.md).

Separately, preregistered and prepared (suites built, not yet run) a cycle-budget ablation raising
`max_cycles_per_pack` from 4 to 8 for Opus x P1 and Sol x P1 x xhigh, 6 replicates each. Required
widening two hardcoded contract ceilings in `v037_agent.py` (previously fixed at 4 since v0.3.7) to
a new `MAX_CYCLES_PER_PACK = 8` module constant -- backward compatible by construction, and the
full 395-test suite passes unchanged. New prompt `v040_p1_c8.md` is P1 with exactly one word
changed ('four' -> 'eight'). Only the cycle=8 arm will be executed as new runs; each
configuration's cycle=4 baseline is read from already-unblinded prior studies rather than re-run.

## 2026-08-29 — cycle-budget ablation: capacity hypothesis rejected, effort and cycles diverge

All 12 runs completed, audited clean, and unblinded (with two operational hiccups along the way:
the suite build script and `_CONFIG_REGISTRY` registration were both forgotten after writing --
the same mistake as Stage 2, now caught by a new regression test
(`test_run_v040_agent_registers_every_study_suite_id_set`) that imports the runner and asserts
every declared suite-id constant is registered; and the batch's parent process died mid-run for an
unexplained reason (no OOM evidence, memory looked normal) while one child subprocess survived as
an orphan and ran to completion on its own -- the one truly-missing pair was launched individually,
avoiding a collision with the still-running orphan, and all 12 submissions landed cleanly with no
duplication or corruption).

The preregistered capacity hypothesis -- that raising `max_cycles_per_pack` from 4 to 8 would
increase discovery the way raising reasoning effort did -- was not supported. Discovery-event
rates were roughly flat once normalized by replicate count (opus 2.0 -> 1.83 events/replicate, sol
1.17 -> 1.33). But diversity metrics moved in the OPPOSITE direction from the effort ablation:
mean semantic_family_count fell for both models (opus 3.75 -> 2.67, sol 1.67 -> 1.17). The
working interpretation: more cycles per pack let an agent go deeper on fewer lineages rather than
broader across more hypotheses -- cycle budget and reasoning effort are not interchangeable
"evidentiary capacity" levers; they pull in different directions on the depth/breadth axis. Sol's
false-promotion count rose from 1 (cycle=4 baseline) to 4 (cycle=8), but all 4 were concentrated in
a single suite instance -- the same single-outlier pattern already seen repeatedly across the
session (generation 1's terra/g03, the effort ablation's high/b05, Stage 1's sol x P3), now also
showing up for cycle=8, suggesting a recurring "some suite instances trigger a runaway-validation
mode regardless of model/scaffold/effort/cycles" phenomenon worth investigating on its own.
`persistent_delayed_history` was discovered once more (opus x P1 x cycle8), at the same ~1-in-6
rate already seen at cycle=4 in Stage 2 -- cycle budget did not clearly raise the persistent-ladder
discovery rate either. Full detail:
[verification/v040_cycle_budget_ablation_qualification.md](verification/v040_cycle_budget_ablation_qualification.md).

Updated the cross-study discovery ledger (now 102 runs across 5 completed studies):
[v040_discovery_ledger.md](v040_discovery_ledger.md). persistent_delayed_history now stands at 3
discoveries (2 from Stage 2, 1 from this ablation); every persistent-ladder family has been broken
at least once, none more than 6 times out of 102 runs.

This closes out v0.4.0's generation-1 side-probe program (sol-effort ablation, scaffold-ladder
Stage 1/2, cycle-budget ablation all complete). Next: synthesize all of it into a v0.4.1
specification.

## 2026-08-29 — v0.4.1 policy: P1 declared achieved, pivot to Track B

Synthesized all five completed v0.4.0 studies (78 side-probe runs plus generation 1) into
[c_lite_v041_policy.md](c_lite_v041_policy.md). The headline finding, checked precisely against
the diagnostics data rather than asserted: the single execution configuration opus x P1 x cycle=4
achieved genuine persistent-ladder discovery with zero false promotions across three independent
studies and 14 total replicates (generation 1's C3: persistent_compositional in one suite; Stage
1's L-opus-P1: persistent_compositional and persistent_clear together in one suite; Stage 2's
T2-opus-P1: persistent_delayed_history in one suite) -- three different persistent families, three
different suite instances (different master seeds, none reused), zero contamination. This meets
v0.4.0 policy's stated P1 bar (persistent-family discovery in >= 2 independent runs of the same
configuration with clean matched-negative rejection) with room to spare, and triggers that policy's
own stopping rule 2: "once a configuration achieves P1, move immediately to Track B."

v0.4.1 therefore does not chase a further Track A generation. It consolidates what Track A
established (reasoning effort raises both discovery and diversity; cycle budget raises neither and
lowers diversity -- the two are not interchangeable "evidentiary capacity" levers; scaffold P3 is
the strongest cross-model lever found; P2 is model-dependent and does not help opus; a recurring
single-suite-instance false-promotion pattern has now appeared four times independently and
warrants its own investigation) and sets three configurations (opus x P1, opus x P3, sol x P3 x
xhigh) to carry into Track B, the IEEE-CIS blind bridge that has been designed but not built since
v0.4.0's original policy. Track B's suite build touches real data and is flagged in the policy
document itself as requiring explicit user confirmation before execution, consistent with this
project's practice of pausing at the synthetic-to-real-data boundary.
