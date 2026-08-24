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
- Local executor plus an `ai-dev-control-plane` adapter that creates idempotent Linear execution
  tickets containing a versioned `ExperimentRequest` contract.
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

`AiDevControlPlaneAdapter` creates a Linear issue with this stable marker:

```text
<!-- epistemic-research-loop:experiment-request:v1 -->
ERL-IDEMPOTENCY: <run>:<experiment>:<attempt>
```

The body contains the full JSON execution contract. `ai-dev-control-plane` verifies the Linear
webhook signature, de-duplicates the delivery, queues the issue, runs the configured worker, and
writes `ExperimentResult` to the shared result store. The research loop imports that result; it does
not reimplement worker dispatch or retry policy.

See [architecture](docs/architecture.md), [research protocol](docs/research_protocol.md),
[holdout policy](docs/holdout_policy.md), and [security](docs/security.md).
