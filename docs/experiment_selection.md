# Experiment selection

Hard gates run before utility. An experiment is rejected for missing hypotheses, predictions,
decision rule, reproducible command, outputs, budget, source-policy compliance, holdout permission,
or for duplicating a non-replication experiment.

```text
U(e) = wp*P(e) + wi*I(e) + wr*R(e) + wd*D(e) - lambda*C(e)
```

Discovery uses `(0.20, 0.45, 0.20, 0.15)`, consolidation `(0.35, 0.30, 0.25, 0.10)`, and
exploitation `(0.55, 0.15, 0.25, 0.05)` with default `lambda=0.15`. Epistemic v1 is the average of
five 0–4 rubric scores. Portfolio selection greedily applies a similarity penalty against already
selected lineages, hypothesis targets, experiment types, and metrics.
