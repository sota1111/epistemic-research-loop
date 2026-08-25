# Experiment selection

The target v2 design, including preferred-state gaps, likelihood-based information gain, and
multi-agent portfolio construction, is specified in
[research-state-aware experiment selection](research_state_selection.md). This page describes the
currently deployed v1 policy and its migration fallback.

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

Selection v2 has begun with a backwards-compatible vertical slice. A proposal may preregister, for
each linked binary hypothesis, mutually exclusive observable outcomes and the likelihood vectors
`p(y | H, e)` and `p(y | not H, e)`. The selector combines these with the current confidence from
the event log and computes mutual information in bits. When those forecasts are present, the v1
rubric is ignored; old proposals without them still replay through the rubric fallback. Every
`DecisionRecord` identifies the method as `expected_information_gain_v2` or `rubric_v1`.

This is not yet the complete v2 policy. Validation-world projection, state-gap weighting,
forecast-calibration feedback, information-redundancy penalties, and role-scoped multi-agent
proposals remain in the delivery sequence documented in
[research-state-aware experiment selection](research_state_selection.md).

Two gates keep the search from collapsing onto one lineage: a fourth consecutive optimization
experiment is refused until a diagnostic, replication, or falsification runs, and the adaptivity
budget refuses further *selecting* experiments against a split that has already answered
`loop.max_validation_reuse` of them — see [validation adaptivity](validation_adaptivity.md).

Selection can legitimately choose nothing. When it does, the loop calls `replan`, which returns the
run to planning with a recorded reason rather than stalling in `selecting` with no work to dispatch.
