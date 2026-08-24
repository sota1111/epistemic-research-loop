# Validation adaptivity

Local cross-validation is the loop's unrestricted signal — but "unrestricted" is about the *budget*,
not about the *statistics*. A validation split answers honestly once. Ask it to choose between
twenty candidates and the winner is partly fitted to that split's noise, so the reported gain is
optimistic by an amount nobody measured. This is the same adaptive-data-analysis failure the sealed
holdout exists to prevent, one level down, and it is the failure that produces a strong CV and a
disappointing private score.

## What counts as one validation scheme

`holdout/adaptivity.validation_fingerprint` hashes the normalised split strategy together with the
sorted metric list. Two experiments that train different models against the same split and read the
same metric are **two queries to one validation set**, not two independent measurements. Whitespace
and letter case do not create a new scheme.

## What spends the budget

Only experiments that *select* — where the result decides which candidate to keep:

| Experiment type | Spends adaptivity | Why |
| --- | --- | --- |
| `optimization` | yes | picks a winner on the split |
| `ablation` | yes | attributes gain on the split |
| `diagnostic` | no | asks what the split *is*, does not choose on it |
| `falsification` | no | tests a preregistered prediction, does not rank candidates |
| `replication` | no | confirms an existing result rather than choosing a new one |
| `robustness` | no | measures spread, does not select on the mean |

Only experiments the run committed to are counted (`selected`, `running`, `completed`, `failed`). A
proposal that was scored and shelved never saw the split, so it cannot have overfitted it.

## The budget

`loop.max_validation_reuse` (default **8**, `0` disables the guard). Once a scheme has answered its
budget of selecting queries, `hard_gate` refuses further selecting experiments against it with a
reason naming the split. Two things unblock the run, and both are real work rather than a bypass:

1. **Rotate the split.** A different split strategy is a different scheme with a fresh budget.
2. **Run a diagnostic, falsification, replication, or robustness experiment.** These do not select,
   so they are never refused — and they are how a run re-establishes what the split still means.

The reuse counts are visible in `erlctl run status`, are handed to the experiment designer as
`validation_reuse` so it can rotate before hitting the wall, and are carried into the research brief
as `search_ranges.validation_reuse_spent` so the exploiter inherits the same accounting.

## What this does not do

It bounds the *number* of adaptive queries; it does not correct the bias of the ones already spent.
A run that has spent its budget has not been de-biased — it has been told to stop pretending the
next number from that split is independent. Correcting the estimate (a held-out re-evaluation, or a
formal adaptive-analysis bound) is future work, not something this guard delivers.

See [holdout policy](holdout_policy.md) for the sealed holdout and
[leaderboard policy](leaderboard_policy.md) for the public leaderboard, which are separate channels
with separate budgets.
