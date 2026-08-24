# ADR 0001: Event-sourced deterministic control

Status: accepted.

Canonical state is append-only JSONL with a hash chain. SQLite is rebuildable. LLMs produce typed
proposals; deterministic code validates and records transitions. This makes preregistration edits,
failed experiments, holdout violations, and every selection decision replayable and auditable.
