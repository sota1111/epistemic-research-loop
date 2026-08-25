# Cycle retrospective — IEEE-CIS, runs 001 through 009

Written 2026-08-25 from the event logs in `.runs/`, the submission ledger in
`.state/kaggle-submissions.jsonl`, and the Kaggle API. Every number below is reproducible with
`erlctl run status` or the commands recorded alongside each claim; none of it is recalled.

## 1. What the leaderboard actually said

Seven submissions were spent. The private leaderboard has since become visible, which changes the
conclusion of the earlier report — that report could only see public scores.

| # | arm | description | public | private |
|---|---|---|---|---|
| 1 | epistemic | E-SUB-09 baseline | 0.934969 | 0.905709 |
| 2 | exploiter | tuned: uid_agg, 1500 trees, lr 0.02 | **0.938967** | 0.907136 |
| 3 | epistemic | ordering candidate A | 0.934969 | 0.905709 |
| 4 | epistemic | ordering candidate B | 0.936254 | **0.908484** |
| 5 | epistemic | ordering candidate C | 0.932155 | 0.898684 |
| 6 | epistemic | ordering candidate D | 0.937832 | 0.905236 |
| 7 | epistemic | ordering candidate E | 0.935898 | 0.906821 |

Submission 3 is byte-identical to submission 1 and scored identically. It was filed because the
duplicate guard compares SHA-256 fingerprints and reconciled records carry an empty fingerprint, so
the guard had nothing to compare. One of five daily submissions bought zero information.

### The preregistered ordering test

Five candidates were ranked on local CV before any of them was submitted, so the three orderings can
be compared without hindsight.

| ranking | order |
|---|---|
| local CV | A > D > E > C > B |
| public | D > B > E > A > C |
| private | B > E > A > D > C |

Kendall tau: local vs public **+0.00**, local vs private **−0.20**, public vs private **+0.40**.

Local CV carried no information about the public leaderboard and slightly negative information about
the private one. The candidate local CV ranked *last* (B) is the one that won the private
leaderboard. This is the most consequential measured result of the whole exercise and it was
obtained because the ordering was preregistered; had the ranking been formed after seeing scores, it
would have proved nothing.

### Exploiter versus epistemic, restated

The earlier report concluded the exploiter won. On public scores it did: 0.938967 is the highest of
the seven. On private it does not: 0.907136 places it behind candidate B's 0.908484. The honest
statement is that the exploiter won the metric that was visible and lost the metric that counted,
by a margin (0.0013) far smaller than the spread between candidates, and that N=1 per arm remains
too small to call either way. What the comparison does establish is that public-leaderboard
selection would have chosen D (private 0.905236) — the second-worst candidate on private.

## 2. What the loop did unattended

Runs 001–009 were driven by `erlctl run loop` with no API key, shelling out to the `claude` CLI.

| run | proposals | completed | failed | observations | outcome |
|---|---|---|---|---|---|
| 001–007 | 24 | 0 | 3 | 3 | every experiment failed or was never dispatched |
| 008 | 7 | 1 | 1 | 2 | first completed experiment; crashed at round 2 |
| 009 | 14 | 4 | 4 | 8 | four rounds completed end to end |

Run 009 took 44 minutes for four rounds — 11 minutes per round, or roughly 130 rounds per day
against a requirement of ten. Experiment execution is not the constraint: the median experiment ran
6 seconds and the longest under two minutes. Proposal generation is essentially all of the wall
clock.

### Did the loop change what it was asking?

Yes, and the event log shows it in the wording of the questions rather than in a summary statistic.

Round 3 measured a validation gap: `random_kfold` 0.96320 against `time_holdout` 0.93069, a gap of
0.0325. Round 4's proposal opens by quoting those numbers back:

> Is the observed 0.0325 ROC-AUC gap between random_kfold (0.96320) and time_holdout (0.93069)
> carried by card1 entity overlap rather than by time?

The answer it obtained: grouping folds by `card1` gives 0.8656 against random's 0.9632, a gap of
0.0976 — three times the temporal gap. Entity overlap, not temporal drift, is the dominant source of
validation optimism in this dataset. The loop reached that by testing an alternative explanation for
a number it had produced two rounds earlier, which is the behaviour the exercise was set up to look
for.

Belief movement across all runs: 94 updates, 27 up, 33 down, 34 flat, mean |Δ| 0.079. The largest
single move was −0.245. Beliefs move in both directions, which is what distinguishes updating from
accumulating confirmation.

Falsification dispositions across all runs: 44 inconclusive, 24 falsified, 16 survives, 11 weakened.
Inconclusive remains the plurality at 46%, and most of those came from experiments that failed to
run — the falsifier correctly refused to read information into a crashed process. In run 009,
`h-leak-duplicate-boundary` and `h-temporal-regime-heterogeneity` were both eventually **falsified**
on real measurements, and `h-shift-train-test` **survived** on an adversarial AUC of 0.9241.

### Did the loop repair itself?

Once, cleanly, and the timing rules out credit going to the operator.

Every round-1 proposal passed `--data .data/ieee-cis/parquet/train.parquet`. The runner's `--data`
takes a directory, so all five failed minutes into execution. At **05:41:08 UTC** the loop proposed:

> exp-loader-repair-duplicate-scan: With the dataset argument pointing at the parquet directory
> rather than at the train file, does the runner load...

and every proposal from round 2 onward passes the directory. The operator's fix making the runner
accept either form was committed at **05:45:18 UTC** — four minutes later. The loop diagnosed the
defect from the failure text alone and corrected its own tooling.

That was only possible because of a change made during this cycle: failures now carry their own
explanation back to the proposer.

## 3. The recurring defect

Nine defects were fixed across these runs. Eight are the same defect:

**A constraint was enforced in code that the party expected to satisfy it never reads.**

| # | constraint | where it lived | what it cost |
|---|---|---|---|
| 1 | `command` is required | schema only | round lost |
| 2 | `max_gpu_hours: 0` means unlimited | controller | run refused to dispatch |
| 3 | `network_policy` literals | validator | round lost |
| 4 | consecutive-optimization limit | documented config the gate never read | exploiter arm stalled |
| 5 | command allowlist | executor | `mkdir &&` rejected after design |
| 6 | output directory | executor, unnamed | experiment ran, scored failed |
| 7 | `required_artifacts` are file names | post-run existence check | experiment ran, scored failed |
| 8 | `--data` takes a directory | runner internals | four experiments failed mid-run |
| 9 | experiment ids must be unique | controller, raised on the batch | round lost, run 008 stopped |

The fix in every case was the same in shape: move the constraint, or its diagnosis, to where the
party that must satisfy it can see it. Concretely, in this cycle:

- `$ERL_OUTPUT_DIR` is substituted into the command, so a proposal can name a directory that does
  not exist when it is written.
- `ExperimentResult` and `Observation` carry a `failure_excerpt`; `failed_experiments()` forwards it
  with the command that produced it. This is what made the self-repair above possible.
- `used_experiment_ids` reaches the proposer, and a collision drops one proposal instead of the
  batch.
- The competition package publishes the runner's accepted argument values, extracted from the
  runner's own source rather than restated by hand.
- The runner accepts `--data` as a directory or a file and lists valid splits in its error.

The lesson generalises past this project: when an autonomous system keeps failing at the same layer,
the question to ask is not "how do we constrain it harder" but "can the thing being constrained read
the constraint".

## 4. What is still not demonstrated

- **The arms have not been benchmarked.** N=1 per arm, and the private result reverses the public
  one. A real comparison needs repeated runs, which the five-submissions-per-day budget makes slow.
- **Half of the falsification verdicts are inconclusive.** The rate should fall now that experiments
  complete, but that has not been measured over a run where everything ran.
- **The machinery constrains more than it generates.** `E-HPO-01` was scored 16 times and selected
  zero times; 30 of 100 scored experiments were never selected; 23 proposals were rejected at the
  gate. The selection layer demonstrably filters. Whether the proposal layer would produce good
  research without that filter is untested.
- **No end-to-end submission has come out of the unattended loop.** Runs 008 and 009 produced
  diagnostics, not predictions. The path from a completed research round to a scored submission has
  been exercised by hand, not by the loop.
