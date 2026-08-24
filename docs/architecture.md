# Architecture

The repository owns research decisions. It emits versioned `ExperimentRequest` contracts and
imports `ExperimentResult`; it does not own training implementations, worker selection, retries, or
submission credentials.

```text
Competition package
  -> Observer -> World model -> Hypothesis graph
  -> Generator/Falsifier/Designer -> Candidate experiments
  -> Hard gates -> Utility + portfolio selector
  -> ai-dev-control-plane adapter -> Linear issue          [the only interface]
  -> signed Linear webhook -> queue -> worker -> ExperimentResult
  -> parser -> falsification -> belief update -> phase policy -> Research brief
```

## The Linear issue is the only interface

This repository does not call `ai-dev-control-plane`, and `ai-dev-control-plane` does not call it
back. The two systems meet at exactly one artifact: **a Linear issue that this repository creates
and the control plane reads and implements.** Results return through the shared result store, which
is a file location both sides already know — not a second connection.

That constraint is what makes the boundary below enforceable. A worker cannot ask the research loop
for more context mid-run, so everything it needs — objective, command, container, seeds, mounts,
required outputs, and the machine-readable `ExperimentRequest` — is rendered into the issue body up
front. It also means the ticket must match the control plane's parsing convention (`workers:` and
`TARGET_REPO=` on the first lines); a ticket that does not is filed and then silently ignored.

The canonical state is the per-run JSONL event log. SQLite is only a query projection and may always
be deleted and rebuilt. Every event has a sequence number, prior-event hash, and its own content
hash. LLM output can propose state but cannot mutate it without deterministic validation.

## Repository boundary

| Component | Responsibility |
| --- | --- |
| epistemic-research-loop | What to try, why, preregistration, selection, falsification, belief, blind evaluation |
| Kaggle Solver | Features, training, inference, submission artifact |
| ai-dev-control-plane | Reads the Linear issue; webhook, queue, worker choice, execution, retry, implementation/test/evaluation |
| Evaluator | Final submission, sealed score aggregation, unseal |
