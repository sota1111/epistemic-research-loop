# Experiment selection

The target v2 design, including preferred-state gaps, likelihood-based information gain, and
multi-agent portfolio construction, is specified in
[research-state-aware experiment selection](research_state_selection.md). This page describes the
deployed v2 policy and its legacy fallback.

Hard gates run before utility. An experiment is rejected for missing hypotheses, predictions,
decision rule, reproducible command, outputs, budget, source-policy compliance, holdout permission,
for duplicating a non-replication experiment, or for exhausting the adaptivity budget of the
validation scheme it would be scored against.

```text
U(e) = wp*P(e) + wi*I(e) + wr*R(e) + wd*D(e) - lambda*C(e) - rho*Risk(e)
```

Discovery uses `(0.20, 0.45, 0.20, 0.15)`, consolidation `(0.35, 0.30, 0.25, 0.10)`, and
exploitation `(0.55, 0.15, 0.25, 0.05)` with default `lambda=0.15`. Epistemic v1 is the average of
five 0–4 rubric scores. Explicit System C experiments use a preregistered EIG or EVSI proxy; the
rubric remains only for legacy manifests. Portfolio selection applies the phase allocation
(Exploit / QD Explore / Epistemic) and greedily applies a similarity penalty against already
selected lineages, hypothesis targets, experiment types, and metrics.

Selection v2 is wired end to end. A proposal may preregister, for
each linked binary hypothesis, mutually exclusive observable outcomes and the likelihood vectors
`p(y | H, e)` and `p(y | not H, e)`. The selector combines these with the current confidence from
the event log and computes mutual information in bits, exactly or by seeded Monte Carlo. When those forecasts are present, the v1
rubric is ignored; old proposals without them still replay through the rubric fallback. Where a
proposal declares decision-change probability and normalized action-utility difference, their
product is the auditable EVSI proxy. Every `DecisionRecord` identifies the method used.

Validation-world projection is event-sourced and updated from preregistered likelihoods. A
configurable preferred-state gap modulates the Exploit/QD/Epistemic allocation. Brier, log loss,
confidence error and 50/80/95% interval coverage are recorded by agent/category; sufficiently poor
calibration shrinks subsequently proposed priors toward 0.5. Portfolio-level information-redundancy
penalties and broader role-scoped proposal agents remain future work.

Two gates keep the search from collapsing onto one lineage: a fourth consecutive optimization
experiment is refused until a diagnostic, replication, or falsification runs, and the adaptivity
budget refuses further *selecting* experiments against a split that has already answered
`loop.max_validation_reuse` of them — see [validation adaptivity](validation_adaptivity.md).

Selection can legitimately choose nothing. When it does, the loop calls `replan`, which returns the
run to planning with a recorded reason rather than stalling in `selecting` with no work to dispatch.
