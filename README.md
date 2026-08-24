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
- Local executor plus an `ai-dev-control-plane` adapter that creates idempotent Linear execution
  tickets containing a versioned `ExperimentRequest` contract.
- Budgeted public-leaderboard feedback; local cross-validation stays unrestricted and the Kaggle
  private score is never unsealed by the loop.
- Paired synthetic A/B benchmark with all final regrets sealed until finalization.
- Evaluator-only Kaggle automation with submission caps, artifact de-duplication, polling, encrypted
  score sealing, and a manual-submission fallback.
- `erlctl` for run initialization/status/replay, hypothesis and experiment inspection, holdout audit,
  benchmarks, and reports.

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
uv run erlctl run advance --run-id $RUN --validation-locked
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

The Kaggle **private** score is the objective and is never unsealed by the research loop. See
[leaderboard policy](docs/leaderboard_policy.md).

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
TARGET_REPO=/workspaces/<repo>                <- parsed to select the checkout

<!-- epistemic-research-loop:experiment-request:v1 -->
ERL-IDEMPOTENCY: <run>:<experiment>:<attempt>

## 目的 / ## 変更範囲 / ## 実装内容 / ## 検証内容 / ## 受け入れ条件
                                              <- what the worker reads

## 実行契約（機械可読・変更禁止）
    a fenced JSON block holding the full ExperimentRequest
```

The `workers:` line, the `TARGET_REPO=` line, and the section headings follow
`ai-dev-control-plane`'s ticket convention. A ticket that omits them is created but never picked up,
so they are not decoration — set them with `executor.worker`, `executor.handoff`, and
`executor.target_repo`. `executor.linear_state_id` pins the initial status when the team's default
would leave the issue out of the worker's queue.

The research loop decides *what to run and why*. It does not reimplement worker dispatch, retry
policy, or the implementation itself — those belong to the control plane, and the issue is where the
two meet.

See [architecture](docs/architecture.md), [research protocol](docs/research_protocol.md),
[holdout policy](docs/holdout_policy.md), [leaderboard policy](docs/leaderboard_policy.md), and
[security](docs/security.md).
