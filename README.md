# Epistemic Research Loop

`epistemic-research-loop` is a hypothesis-centric experiment orchestrator for Kaggle research. It
decides **what to try next and why**; model training, feature generation, queueing, retries, and
worker selection stay in the Kaggle Solver and `ai-dev-control-plane`.

```text
observation -> hypothesis -> preregistered prediction -> experiment selection
            -> execution -> falsification -> belief update -> exploiter handoff
```

Version: **0.1.0** (initial MVP)

## What is implemented

- Pydantic schemas for runs, hypotheses, preregistered experiments, observations, belief updates,
  decisions, artifacts, execution contracts, and research briefs.
- Append-only JSONL event logs with monotonically increasing sequence numbers and a SHA-256 hash
  chain; SQLite is a disposable query projection rebuilt from those events.
- Deterministic hard gates, phase-weighted pragmatic/epistemic/robustness/diversity utility, and
  similarity-penalized portfolio selection.
- Operational-confidence updates in log-odds space, clipped to `[0.05, 0.95]`.
- `strict_blind`, `gated_binary`, and debug holdout policies; authenticated encrypted score sealing
  and an append-only query ledger.
- Strict historical source policy and provenance records.
- A deterministic loop controller that folds the event log into run state and drives
  `hypothesizing -> planning -> scoring -> selecting -> executing -> parsing -> falsifying ->
  updating -> phase_decision`, refusing any step invoked out of order.
- Phase evidence derived from the event log, so discovery advances to consolidation and exploitation
  on its own, and an anomaly in exploitation returns the run to research.
- An explicit researcher-to-exploiter hand-off: exploitation cannot begin until a `ResearchBrief`
  derived from the record is published as an event.
- A validation adaptivity budget that bounds how many *selecting* experiments one split may answer
  before it must be rotated or re-diagnosed.
- Local executor plus an `ai-dev-control-plane` adapter that creates idempotent Linear execution
  tickets containing a versioned `ExperimentRequest` contract.
- Budgeted public-leaderboard feedback; local cross-validation stays unrestricted and the Kaggle
  private score is never unsealed by the loop.
- Paired synthetic A/B benchmark scored on discovery rate, CV-private gap, and compute efficiency
  as well as sealed regret, with an IID negative control and all final regrets sealed until
  finalization.
- Evaluator-only Kaggle automation with submission caps, artifact de-duplication, polling, encrypted
  score sealing, and a manual-submission fallback.
- `erlctl` for run initialization/status/replay, hypothesis and experiment inspection, the exploiter
  hand-off, holdout audit, benchmarks, and reports.

**[docs/capability_matrix.md](docs/capability_matrix.md) is the index**: one row per capability,
naming the code that enforces it and the test that would fail if it stopped being true.
[docs/progress.md](docs/progress.md) carries milestones, how to verify them, and known limitations.

The LLM proposes hypotheses and experiments only. Schema validation, gates, state transitions,
utility, budgets, hashes, holdout access, and event recording remain deterministic.

## Quick start

```bash
uv sync --extra dev
uv run erlctl init \
  --competition synthetic-shift \
  --config configs/benchmarks/synthetic.yaml \
  --run-id synthetic-epistemic-001

uv run erlctl run start --run-id synthetic-epistemic-001
uv run erlctl run status --run-id synthetic-epistemic-001
uv run erlctl report run --run-id synthetic-epistemic-001
```

## Research loop

`erlctl run loop` runs the whole cycle unattended — propose, gate, select, dispatch, import,
falsify, update belief, decide the phase — appending to the canonical event log at every step:

```bash
uv sync --extra dev --extra llm
export ANTHROPIC_API_KEY='...'

uv run erlctl run loop --run-id $RUN --rounds 5 --size 1
```

The model is consulted at exactly three points, each through a validated structured-output schema:

| Step | Model decides | Deterministic code decides |
| --- | --- | --- |
| Hypotheses | what to claim, predictions, prior | schema validity, active-hypothesis cap |
| Experiments | protocol, controls, decision rule, cost | hard gates, utility, portfolio, budget |
| Falsification | which predictions the evidence matched | disposition, evidence weight, log-odds update |

A proposal that fails its schema or a gate is rejected, not repaired. Budgets, state transitions,
hashes, holdout access, and event recording never pass through the model.

### Stepping through it by hand

The same cycle is available one command at a time, which is what to reach for when debugging a run
or when `llm.adapter: file_bridge` puts a human in the proposal slot:

```bash
uv run erlctl hypotheses request --run-id $RUN    # writes prompt + context + JSON Schema
uv run erlctl hypotheses record  --run-id $RUN --from .proposals/$RUN/hypotheses.json
uv run erlctl experiments request --run-id $RUN
uv run erlctl experiments propose --run-id $RUN --from .proposals/$RUN/experiments.json
uv run erlctl experiments select  --run-id $RUN --size 1
uv run erlctl experiments dispatch --run-id $RUN --experiment-id E-SPLIT-001
uv run erlctl experiments import-result --run-id $RUN --experiment-id E-SPLIT-001
uv run erlctl beliefs update --run-id $RUN --from belief.json
uv run erlctl run advance --run-id $RUN                # evidence is derived from the event log
uv run erlctl brief create --run-id $RUN               # required before exploitation may begin
uv run erlctl run status  --run-id $RUN
```

The state machine refuses a step invoked from the wrong state, so a prediction cannot be recorded as
preregistered after its result was seen.

## Score policy

Local cross-validation is the unrestricted feedback signal. The public leaderboard is a finite-sample
proxy for the private score, so reads are budgeted and return only a preregistered threshold verdict
by default:

```bash
uv run erlctl kaggle feedback --run-id $RUN --score-id $RUN-12345678 --threshold 0.80
```

The Kaggle **private** score is the objective and is never unsealed by the research loop.
Submissions are capped at five a day and the loop spends none of them — it reads the `metrics.json`
a worker wrote locally, so ten or more rounds a day costs nothing against Kaggle's allowance. The
working validation split is unrestricted in budget but not in statistics: `loop.max_validation_reuse`
bounds how many selecting experiments one split may answer. See
[leaderboard policy](docs/leaderboard_policy.md) and
[validation adaptivity](docs/validation_adaptivity.md).

## Benchmark

Run the sealed paired benchmark:

```bash
uv run erlctl benchmark plan \
  --profile configs/benchmarks/synthetic.yaml \
  --replicates 5

export BENCHMARK_UNSEAL_TOKEN='replace-with-an-evaluator-owned-secret'
uv run erlctl benchmark run --plan benchmark-plan.yaml
uv run erlctl benchmark finalize \
  --plan benchmark-plan.yaml \
  --unseal-token-env BENCHMARK_UNSEAL_TOKEN
```

`BENCHMARK_UNSEAL_TOKEN`, Kaggle credentials, and API keys must be evaluator/runtime secrets. They
must never enter prompts, events, artifacts, or source control.

## Kaggle final evaluation

Kaggle access belongs to the evaluator, not the Research Agent or experiment Worker. Prepare a
candidate registry (see `examples/kaggle_submission_candidates.json`) and inspect the deterministic
plan before submitting:

```bash
uv run erlctl kaggle plan \
  --competition example-slug \
  --candidates examples/kaggle_submission_candidates.json \
  --daily-cap 1

export BENCHMARK_UNSEAL_TOKEN='replace-with-an-evaluator-owned-secret'
uv run erlctl kaggle submit \
  --competition example-slug \
  --file outputs/submission.csv \
  --message 'run-001 final candidate' \
  --run-id run-001 \
  --daily-cap 1
```

The submit command rejects duplicate bytes and exhausted daily budgets. Returned leaderboard scores
are encrypted into `.sealed-scores/`; stdout contains only status and the submission reference. If
CLI submission is unavailable, `erlctl kaggle manual-packet` creates a checksummed handoff packet.

## Control-plane handoff

**The Linear issue is the entire interface.** This repository creates one; `ai-dev-control-plane`
reads that issue and implements it. There is no second channel between the two systems — no direct
API, no shared queue, no callback. Anything the worker needs must be in the issue body.

The round trip:

1. `erlctl experiments dispatch` creates the Linear issue. It is idempotent: the `ERL-IDEMPOTENCY`
   marker is searched first, so a retry reuses the existing issue instead of filing a duplicate.
2. `ai-dev-control-plane` verifies the Linear webhook signature, de-duplicates the delivery, queues
   the issue, selects the worker, and runs it.
3. The worker writes the required outputs and an `ExperimentResult` to the shared result store.
4. `erlctl experiments import-result` imports that result as an `Observation`, and the loop
   falsifies, updates belief, and decides the next phase.

`AiDevControlPlaneAdapter` renders the issue in the control plane's native ticket format:

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

**Routing is by Linear project name, not by `TARGET_REPO=`.** The control plane resolves the
checkout from the project: `config/project_repos.json`, then `config/auth/apps.json`, then by
slugifying the project name and taking `/workspaces/<slug>` if it contains a `.git`
(`src/lib/projectRepo.ts`). A project that resolves to nothing is **fail-closed**: every ticket filed
into it answers `REPO_RESOLUTION_UNAVAILABLE` and is retried indefinitely. Measured: filing 20
tickets into a project named `ERL IEEE-CIS 自動起票検証` — which slugifies to `erl-ieee-cis`, a path
that does not exist — produced 1,126 retry failures before the tickets were deleted. Name the
project after the repository.

**The execution contract must be the first fenced JSON block.** `parseExperimentRequest` takes the
first `` ```json `` block in the description, so any JSON block placed above it is parsed as the
contract and the ticket is rejected at the webhook with `request_id must be a non-empty string` —
filed successfully, then never run. `tests/integration/test_control_plane_contract.py` pins this.

The `workers:` line, the `TARGET_REPO=` line, and the section headings follow
`ai-dev-control-plane`'s ticket convention. Omitting them does **not** make the ticket inert — it
makes it run on the control plane's defaults, which is worse. A description without the
`<!-- epistemic-research-loop:experiment-request:v1 -->` marker parses as `kind: "none"`, which is
*eligible*, not rejected; the worker then comes from `config/worker_roles.json`. Set them with
`executor.worker`, `executor.handoff`, and `executor.target_repo`, and keep `target_repo` equal to
the path the project name resolves to — telling the worker one checkout while the runner hands it
another is how a ticket runs in the wrong repository. Only a ticket that *has* the marker but a
malformed contract is rejected outright.

`executor.linear_state_id` sets the status the issue is created in, and nothing more. **It does not
keep the issue out of the worker's queue.** Measured against the live control plane: an issue
created in `Backlog` was moved to `In Progress` 3.5 seconds later. Dispatching is therefore not a
dry run — every ticket this repository files is work the control plane will pick up, whatever status
it carries. There is no supported way to file a ticket here that a worker will ignore; to inspect a
contract without triggering one, render it with `AiDevControlPlaneAdapter.issue_description()` and
do not submit.

The research loop decides *what to run and why*. It does not reimplement worker dispatch, retry
policy, or the implementation itself — those belong to the control plane, and the issue is where the
two meet.

## Documentation

Progress, scope, and status are recorded in this repository, not in the issue tracker. Linear issues
point here.

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
