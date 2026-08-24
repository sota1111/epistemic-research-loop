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

- **The fully unattended loop (`erlctl run loop`) has still never been run.** There is no
  `ANTHROPIC_API_KEY` in this environment, so both verifications filled the proposal slot by hand
  through the file bridge. Gates, selection, dispositions, belief updates, phase decisions and
  ticket filing were deterministic in both, but "autonomous" remains an untested claim about the
  proposal stage specifically.
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
- **`BudgetManager.reconcile` does not yet replace estimates with observed cost.** Usage is
  reservation-based, so a cheap experiment keeps its estimated charge.
- **Calibration is scored after the fact only** (`belief/calibration.brier_score`); nothing calibrates
  confidence during a run, and the ontology says so.
- **The local executor is a development sandbox**, not the production isolation described in
  [security](security.md).

## Where to read next

- [Capability matrix](capability_matrix.md) — requirement → code → test, one row each.
- [Architecture](architecture.md) — the repository boundary and the Linear interface.
- [Research protocol](research_protocol.md) — the per-round state machine.
- [Exploiter handoff](exploiter_handoff.md) · [Validation adaptivity](validation_adaptivity.md) ·
  [Benchmark protocol](benchmark_protocol.md) · [Holdout policy](holdout_policy.md) ·
  [Leaderboard policy](leaderboard_policy.md) · [Contamination policy](contamination_policy.md)
