# Epistemic Research Loop

`epistemic-research-loop` is a hypothesis-centric experiment orchestrator for Kaggle research. It
decides **what to try next and why**; model training, feature generation, queueing, retries, and
worker selection stay in the Kaggle Solver and `ai-dev-control-plane`.

```text
observation -> hypothesis -> preregistered prediction -> experiment selection
            -> execution -> falsification -> belief update -> exploiter handoff
```

Version: **0.1.0**

- **[docs/capability_matrix.md](docs/capability_matrix.md)** — one row per capability, naming the
  code that enforces it and the test that would fail if it stopped being true, plus what is *not*
  claimed.
- **[docs/progress.md](docs/progress.md)** — milestones, how to verify them yourself, known
  limitations.
- **[docs/research_state_selection.md](docs/research_state_selection.md)** — target design for
  preferred-state gaps, measurable information gain, and multi-agent experiment portfolios.
- **[docs/verification/](docs/verification/)** — what happened when this was run against a real
  competition, including the parts that did not work.

## What is implemented

**Record.** Append-only JSONL event logs with monotonic sequence numbers and a SHA-256 hash chain.
SQLite is a disposable query projection rebuilt from those events. Every research object — runs,
hypotheses, preregistered experiments, observations, falsification records, belief updates,
decisions, artifacts, execution contracts, research briefs — is a Pydantic model with `extra=forbid`.

**Decision.** Deterministic hard gates run before any scoring. Utility is phase-weighted across
pragmatic gain, epistemic value, robustness coverage and diversity, minus cost; selection is a
greedy similarity-penalized portfolio, not a top-K list. Confidence is updated in log-odds space and
clipped to `[0.05, 0.95]`.

**Control.** A loop controller folds the event log into run state and drives
`hypothesizing -> planning -> scoring -> selecting -> executing -> parsing -> falsifying -> updating
-> phase_decision`, refusing any step invoked out of order. Phase evidence is *derived* from the log
rather than asserted, so a run advances — or refuses to advance — on its own record.

**Blindness.** `strict_blind` / `gated_binary` / debug holdout policies, budgeted public-leaderboard
feedback with an append-only query ledger, AES-GCM score sealing, a strict historical source policy,
and a validation adaptivity budget that bounds how many *selecting* experiments one split may answer.

**Evaluation.** A paired synthetic A/B benchmark scored on discovery rate, CV–private gap and
compute efficiency as well as sealed regret, with an IID negative control. `erlctl report compare`
compares two real runs on the same axes.

The LLM proposes hypotheses and experiments and judges which predictions the evidence matched.
Schema validation, gates, state transitions, utility, budgets, hashes, dispositions, belief
arithmetic, holdout access, phase decisions and event recording are all deterministic.

## Quick start

```bash
uv sync --extra dev
uv run erlctl init \
  --competition synthetic-shift \
  --config configs/benchmarks/synthetic.yaml \
  --run-id synthetic-epistemic-001

uv run erlctl run start   --run-id synthetic-epistemic-001
uv run erlctl run status  --run-id synthetic-epistemic-001
uv run erlctl report run  --run-id synthetic-epistemic-001
```

`run start --package <file.json>` seeds the world model from the competition's real schema, metric
and target. Without it the observer sees only the metric, and every structural question starts
unresolved — safe, but a worse-posed set of questions.

## Research loop

`erlctl run loop` runs the whole cycle unattended — propose, gate, select, dispatch, import,
falsify, update belief, decide the phase — appending to the canonical event log at every step:

```bash
uv sync --extra dev --extra llm
export ANTHROPIC_API_KEY='...'

uv run erlctl run loop --run-id $RUN --rounds 10 --size 1
```

The model is consulted at exactly three points, each through a validated structured-output schema:

| Step | Model decides | Deterministic code decides |
| --- | --- | --- |
| Hypotheses | what to claim, predictions, prior | schema validity, active-hypothesis cap |
| Experiments | protocol, controls, decision rule, cost | hard gates, utility, portfolio, budget |
| Falsification | which predictions the evidence matched | disposition, evidence weight, log-odds update |

A proposal that fails its schema or a gate is rejected, not repaired.

`run loop` requires `llm.adapter: claude`. With `file_bridge` it refuses and points at the step
commands below — the path to reach for when debugging a run, or when a human fills the proposal slot.

### Stepping through it by hand

```bash
uv run erlctl hypotheses request  --run-id $RUN          # writes prompt + context + JSON Schema
uv run erlctl hypotheses record   --run-id $RUN --from hypotheses.json
uv run erlctl experiments request --run-id $RUN
uv run erlctl experiments propose --run-id $RUN --from experiments.json
uv run erlctl experiments select  --run-id $RUN --size 1
uv run erlctl experiments dispatch --run-id $RUN --experiment-id E-SPLIT-001
uv run erlctl experiments import-result --run-id $RUN --experiment-id E-SPLIT-001
uv run erlctl beliefs update --run-id $RUN --from belief-a.json --from belief-b.json
uv run erlctl run advance    --run-id $RUN               # phase evidence derived from the log
uv run erlctl brief create   --run-id $RUN               # required before exploitation may begin
uv run erlctl run finalize   --run-id $RUN --note '...' --artifact outputs/submission.csv
```

The state machine refuses a step invoked from the wrong state, so a prediction cannot be recorded as
preregistered after its result was seen.

`beliefs update` takes `--from` more than once. One result usually bears on several hypotheses, and
the state machine allows `parsing -> falsifying -> updating` once per round, so they are recorded in
two passes — every falsification first, then every belief update.

`experiments dispatch --attempt N` retries an experiment whose hand-off died mid-flight. The state
transition is validated *before* the attempt is recorded, so a dispatch the state machine refuses
costs nothing.

## Executors

| Adapter | Files a Linear ticket | Who executes | Use |
| --- | --- | --- | --- |
| `local` | no | a subprocess on this machine | development, control arms, tests |
| `ai_dev_control_plane` | yes | the control plane's worker fleet | production |
| `linear_local_worker` | yes | a subprocess on this machine | **verification harness only** |

`linear_local_worker` files the genuine ticket and then runs it locally in place of the fleet. It
exists so the auto-filing half of the contract can be exercised where no fleet is running, and it is
never evidence that the control plane's queue, worker selection or retry policy was tested. Anything
measured under it must say so.

With `ai_dev_control_plane`, `dispatch` returns `status: queued`: the ticket is filed and the worker
writes the result asynchronously. The loop's only view of progress is the result store — it cannot
distinguish "worker running" from "worker died" — so a caller must poll and choose its own timeout.
While an experiment is in flight the run state correctly reads `executing` / `running`, and the state
machine will not start another round until the result lands or the run is explicitly replanned.

## Score policy

Local cross-validation is the unrestricted feedback signal. The public leaderboard is a
finite-sample proxy for the private score, so reads are budgeted and return only a preregistered
threshold verdict by default:

```bash
uv run erlctl kaggle feedback --run-id $RUN --score-id $RUN-12345678 --threshold 0.80
```

The Kaggle **private** score is the objective and is never unsealed by the research loop.
Submissions are capped by `Budget.max_daily_submissions` (default 5) and `--daily-cap`; the loop
spends none of them on its own, so its cadence is bounded by compute rather than by Kaggle.

The working validation split is unrestricted in budget but not in statistics: one split answers
honestly once, and `loop.max_validation_reuse` (default 8) bounds how many *selecting* experiments
may be scored against it before it must be rotated or re-diagnosed. Diagnostics, falsifications,
replications and robustness runs are exempt because they do not pick a winner.

See [leaderboard policy](docs/leaderboard_policy.md) and
[validation adaptivity](docs/validation_adaptivity.md).

## Explorer and exploiter

Phase evidence is derived from the event log, so a run moves from discovery to consolidation to
exploitation on its own — and refuses to when its findings do not support it. When exploitation is
decided and no brief exists, the run **parks in `phase_decision`** and `brief create` is the only way
forward. The brief is built from the log alone and is refused if no completed experiment established
a validation scheme. An anomaly in exploitation returns the run to consolidation and retires the
brief. See [exploiter handoff](docs/exploiter_handoff.md).

A final submission is not an experiment: it buys no information, it is the most expensive fit a run
makes, and a pragmatic selector scores it negative and refuses it. `run finalize` records it as a
finalization instead, with the artifacts, the phase reached, and what the run actually spent.

## Budgets

Gates charge the estimate a proposal declares. `BudgetManager.reconcile` does not yet replace
estimates with observed cost, so a run whose estimates are optimistic can consume several times its
nominal compute. `run status` therefore reports `observed_runtime` beside the estimate with their
ratio — a ratio far from 1.0 means the run is not operating inside the budget it believes it has.

## Benchmark

```bash
uv run erlctl benchmark plan --profile configs/benchmarks/synthetic.yaml --replicates 5
export BENCHMARK_UNSEAL_TOKEN='replace-with-an-evaluator-owned-secret'
uv run erlctl benchmark run      --plan benchmark-plan.yaml
uv run erlctl benchmark finalize --plan benchmark-plan.yaml --unseal-token-env BENCHMARK_UNSEAL_TOKEN
```

Scenarios plant a temporal shift, a spurious feature and a search-space wall, plus an IID **negative
control** where research is supposed to earn nothing and is charged for trying. Both arms are
credited for whatever finding the action they picked exposes, so the discovery gap is a consequence
of what each system chose to run. **These scenarios are a harness test** — their gains and regrets
are stipulated, so the benchmark shows the selection policy prefers informative actions, not that
the loop beats an exploiter on a real competition. See
[benchmark protocol](docs/benchmark_protocol.md).

To compare two *real* runs:

```bash
uv run erlctl report compare \
  --epistemic $EPISTEMIC_RUN --exploiter $EXPLOITER_RUN \
  --epistemic-steering-estimate 0.9101 --epistemic-public-score 0.934969 \
  --exploiter-steering-estimate 0.9721 --exploiter-public-score 0.938967 \
  --note 'N=1; this describes what each arm did, not which method is better' \
  --out comparison.md
```

The steering estimate must be supplied, not inferred: an arm that deliberately measures pessimistic
schemes has a best-ever number that is not its belief about itself. The report refuses to present the
two arms' local scores as comparable, and reports the **sign** of each calibration gap — believing
you are better than you are is the direction that costs rank.

## Kaggle

Kaggle access belongs to the evaluator, not the Research Agent or the Worker.

```bash
uv run erlctl kaggle plan --competition example-slug \
  --candidates examples/kaggle_submission_candidates.json --daily-cap 5

export BENCHMARK_UNSEAL_TOKEN='replace-with-an-evaluator-owned-secret'
uv run erlctl kaggle submit --competition example-slug \
  --file outputs/submission.csv --message 'run-001 final candidate' \
  --run-id run-001 --daily-cap 5
```

Submit rejects duplicate bytes and exhausted daily budgets. The ledger entry is written **the moment
Kaggle accepts**, before waiting for the score: a submission is gone from the allowance as soon as it
is accepted, and a wait that times out must not leave it unrecorded. If a score arrives late, or a
submission was made outside the loop:

```bash
uv run erlctl kaggle reconcile --competition example-slug --run-id run-001
```

Returned scores are encrypted into `.sealed-scores/`; stdout carries only status and the reference.
`erlctl kaggle manual-packet` creates a checksummed handoff packet when CLI submission is unavailable.

Note that the raw `kaggle competitions submissions` command prints the private score. The loop's own
path (submit → seal → feedback) redacts it; the Kaggle CLI does not.

## Control-plane handoff

**The Linear issue is the entire interface.** This repository creates one; `ai-dev-control-plane`
reads that issue and implements it. There is no second channel — no direct API, no shared queue, no
callback. Anything the worker needs must be in the issue body, and results come back through the
shared result store.

1. `erlctl experiments dispatch` creates the Linear issue. It is idempotent: the `ERL-IDEMPOTENCY`
   marker is searched first, so a retry reuses the existing issue instead of filing a duplicate.
2. `ai-dev-control-plane` verifies the webhook signature, de-duplicates the delivery, resolves the
   repository, queues the issue, selects the worker, and runs it.
3. The worker writes the required outputs and an `ExperimentResult` to the shared result store.
4. `erlctl experiments import-result` imports that result as an `Observation`, and the loop
   falsifies, updates belief, and decides the next phase.

`AiDevControlPlaneAdapter` renders the ticket in the control plane's native format:

```text
workers: solo=claude:opus, handoff=off        <- parsed to select the worker
TARGET_REPO=/workspaces/<repo>                <- the checkout the worker is told to use

<!-- epistemic-research-loop:experiment-request:v1 -->
ERL-IDEMPOTENCY: <run>:<experiment>:<attempt>

## 目的 / ## 変更範囲 / ## 実装内容 / ## 検証内容 / ## 受け入れ条件
                                              <- what the worker reads

## 実行契約（機械可読・変更禁止）
    a fenced JSON block holding the full ExperimentRequest
                                              <- MUST be the first ```json block

## 結果の書き戻し（必須）
    the exact result path and an ExperimentResult template
```

Three properties of this are load-bearing, and each was learned by getting it wrong.

**Routing is by Linear project name, not by `TARGET_REPO=`.** The control plane resolves the checkout
from the project: `config/project_repos.json`, then `config/auth/apps.json`, then by slugifying the
project name and taking `/workspaces/<slug>` if it contains a `.git` (`src/lib/projectRepo.ts`). A
project that resolves to nothing is **fail-closed**: every ticket filed into it answers
`REPO_RESOLUTION_UNAVAILABLE` and is retried indefinitely. Measured: 20 tickets filed into a project
named `ERL IEEE-CIS 自動起票検証` — which slugifies to `erl-ieee-cis`, a path that does not exist —
produced 2,252 retry failures before the tickets were deleted. **Name the project after the
repository**, and keep `executor.target_repo` equal to the path that name resolves to.

**The execution contract must be the first fenced JSON block.** `parseExperimentRequest` takes the
first `` ```json `` block, so a block above it is parsed as the contract and the ticket is rejected at
the webhook with `request_id must be a non-empty string` — filed successfully, then silently never
run. `tests/integration/test_control_plane_contract.py` pins the ordering.

**The ticket must say where the result goes and in what shape.** "Write an `ExperimentResult`" is not
a contract a fresh worker can satisfy; it has to guess the path and the fields. The body carries the
absolute result path and a filled template, and tells the worker to write it on failure too.

Omitting `workers:` or `TARGET_REPO=` does **not** make the ticket inert — it makes it run on the
control plane's defaults, which is worse. Only a ticket that has the marker but a malformed contract
is rejected outright.

`executor.linear_state_id` sets the status the issue is created in and nothing more. It does **not**
keep the issue out of the worker's queue: measured, an issue created in `Backlog` was moved to
`In Progress` 3.5 seconds later. Dispatching is never a dry run.

## Example worker

`examples/ieee_cis/` is a complete solver-side worker for IEEE-CIS Fraud Detection: five validation
schemes, five feature policies, two model families, and four diagnostics that produce information
without optimizing a score. It offers *capabilities*, not a solution — which of them matter is what
the research has to find out.

```bash
uv sync --extra dev --extra solver          # pandas / scikit-learn / lightgbm, worker only
uv run python examples/ieee_cis/prepare.py  # CSV -> parquet, once
uv run python examples/ieee_cis/run_experiment.py --mode split_comparison \
  --baseline-split random_kfold --contrast-split group_time --sample 200000
```

The orchestrator imports none of these; training belongs to the solver repository, and the `solver`
extra exists so a verification run has a real worker.

## Documentation

Progress, scope and status are recorded here, not in the issue tracker.

| Document | What it answers |
| --- | --- |
| [capability matrix](docs/capability_matrix.md) | what is claimed, where it is enforced, which test proves it |
| [progress](docs/progress.md) | milestones, how to verify them, known limitations |
| [architecture](docs/architecture.md) | the repository boundary and the Linear interface |
| [research protocol](docs/research_protocol.md) | the per-round state machine and preregistration rules |
| [hypothesis ontology](docs/hypothesis_ontology.md) | hypothesis types, confidence semantics, retained refutations |
| [experiment selection](docs/experiment_selection.md) | gates, utility, portfolio diversity |
| [exploiter handoff](docs/exploiter_handoff.md) | phase evidence, the research brief, returning from an anomaly |
| [validation adaptivity](docs/validation_adaptivity.md) | bounding adaptive reuse of the working split |
| [holdout policy](docs/holdout_policy.md) | the sealed internal holdout |
| [leaderboard policy](docs/leaderboard_policy.md) | public leaderboard budget and the daily submission cap |
| [contamination policy](docs/contamination_policy.md) | source policy for historical benchmarks |
| [benchmark protocol](docs/benchmark_protocol.md) | paired A/B design and what is scored |
| [security](docs/security.md) | secrets, sandboxing, untrusted data |

### Verification records

| Record | What was measured |
| --- | --- |
| [IEEE-CIS autonomous loop](docs/verification/ieee_cis_autonomous_loop.md) | 16 adaptive rounds on real data, and the defects that only appeared there |
| [IEEE-CIS arm comparison](docs/verification/ieee_cis_arm_comparison.md) | epistemic against an exploiter-only control at matched budget |
| [control-plane Linear round trip](docs/verification/control_plane_linear_roundtrip.md) | ticket creation and idempotency against the live Linear API |
| [worker experiment execution](docs/verification/worker_experiment_execution.md) | a fleet worker consuming a real ticket and writing back a result |

**What has not been verified:** the fully unattended loop (`run loop`) has never run — there has been
no `ANTHROPIC_API_KEY` in any verification environment, so the proposal slot was filled by hand
through the file bridge every time. The Research-to-Exploitation transition is implemented and
unit-tested but has not been observed in a real run. Both are recorded in
[progress](docs/progress.md) rather than glossed.
