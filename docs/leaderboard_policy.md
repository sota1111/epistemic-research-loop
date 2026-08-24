# Leaderboard policy

The objective is the Kaggle **private** score. Two signals are available before it is known, and they
are not interchangeable.

**Local cross-validation is the unrestricted signal.** `ExperimentResult.metrics` and the
`fold_metrics.json` / `seed_metrics.json` / `subgroup_metrics.json` sidecars are folded into an
`Observation` on every import and feed falsification and belief updates without any budget.

**The public leaderboard is a budgeted proxy.** It is a finite sample of the same distribution as the
private split, so treating it as a training signal buys public rank at the cost of private rank. It
is therefore read through `LeaderboardGate`, which ledgers every access:

| Mode | Response | Use |
| --- | --- | --- |
| `forbidden` | violation | runs that must not see the leaderboard at all |
| `gated_binary` (default) | whether a preregistered threshold was met | validating that local CV tracks the leaderboard |
| `numeric` | the public score | late consolidation, when a rank gap must be quantified |

`max_public_queries` (default 3) caps reads per run. Exhausting the budget records a
`LEADERBOARD_BUDGET_EXCEEDED` violation and blocks the run.

**Submissions are capped at five a day, and the loop spends none of them.** Kaggle's allowance is
`Budget.max_daily_submissions` (default 5) and `erlctl kaggle submit --daily-cap`, which refuses an
exhausted day and duplicate bytes. Submission belongs to the evaluator; the research loop reads only
the `metrics.json` a worker wrote locally, so running the loop ten or more times a day costs nothing
against that cap.

**The private score is never unsealed by the research loop.** `erlctl kaggle submit` seals both
scores with AES-GCM; `erlctl kaggle feedback` strips every private field before the gate sees the
payload, so no mode can return it.

The epistemically valuable use of leaderboard feedback is to test a validation hypothesis — does the
local split rank candidates the way the hidden split does? — not to choose between models. Record it
that way: attach the verdict to a `validation` hypothesis and let the belief update carry it.

See also [holdout policy](holdout_policy.md), which governs the separate internal sealed holdout.
