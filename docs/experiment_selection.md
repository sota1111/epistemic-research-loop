# Experiment selection

Hard gates run before utility. An experiment is rejected for missing hypotheses, predictions,
decision rule, reproducible command, outputs, budget, source-policy compliance, holdout permission,
for duplicating a non-replication experiment, or for exhausting the adaptivity budget of the
validation scheme it would be scored against.

```text
U(e) = wp*P(e) + wi*I(e) + wr*R(e) + wd*D(e) - lambda*C(e)
```

Discovery uses `(0.20, 0.45, 0.20, 0.15)`, consolidation `(0.35, 0.30, 0.25, 0.10)`, and
exploitation `(0.55, 0.15, 0.25, 0.05)` with default `lambda=0.15`. Epistemic v1 is the average of
five 0–4 rubric scores. Portfolio selection greedily applies a similarity penalty against already
selected lineages, hypothesis targets, experiment types, and metrics.

Two gates keep the search from collapsing onto one lineage: a fourth consecutive optimization
experiment is refused until a diagnostic, replication, or falsification runs, and the adaptivity
budget refuses further *selecting* experiments against a split that has already answered
`loop.max_validation_reuse` of them — see [validation adaptivity](validation_adaptivity.md).

Selection can legitimately choose nothing. When it does, the loop calls `replan`, which returns the
run to planning with a recorded reason rather than stalling in `selecting` with no work to dispatch.
