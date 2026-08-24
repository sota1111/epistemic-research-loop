# Architecture

The repository owns research decisions. It emits versioned `ExperimentRequest` contracts and
imports `ExperimentResult`; it does not own training implementations, worker selection, retries, or
submission credentials.

```text
Competition package
  -> Observer -> World model -> Hypothesis graph
  -> Generator/Falsifier/Designer -> Candidate experiments
  -> Hard gates -> Utility + portfolio selector
  -> ai-dev-control-plane adapter -> Linear issue
  -> signed Linear webhook -> queue -> worker -> ExperimentResult
  -> parser -> falsification -> belief update -> phase policy -> Research brief
```

The canonical state is the per-run JSONL event log. SQLite is only a query projection and may always
be deleted and rebuilt. Every event has a sequence number, prior-event hash, and its own content
hash. LLM output can propose state but cannot mutate it without deterministic validation.

## Repository boundary

| Component | Responsibility |
| --- | --- |
| epistemic-research-loop | What to try, why, preregistration, selection, falsification, belief, blind evaluation |
| Kaggle Solver | Features, training, inference, submission artifact |
| ai-dev-control-plane | Linear webhook, queue, worker choice, execution, retry, implementation/test/evaluation |
| Evaluator | Final submission, sealed score aggregation, unseal |
