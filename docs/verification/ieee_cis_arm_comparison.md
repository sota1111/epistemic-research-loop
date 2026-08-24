# Arm comparison

`ieee-epistemic-001` (epistemic) against `ieee-exploiter-002` (exploiter-only), same data, worker, seeds, budget and submission allowance.

| Measure | Epistemic | Exploiter-only |
| --- | ---: | ---: |
| Experiments completed | 20 | 20 |
| Non-scoring share of experiments | 1.0 | 0.0 |
| Distinct lineages explored | 7 | 2 |
| CPU hours | 12.85 | 18.0 |
| Kaggle submissions | 1 | 1 |
| Hypotheses held | 9 | 20 |
| Hypotheses refuted or contested | 6 | 12 |
| Inconclusive verdicts recorded | 5 | 8 |
| Highest local number seen, any scheme | 0.9350526407528816 | 0.9720512376566095 |
| Estimate the arm steered by | 0.9101 | 0.9721 |
| Public leaderboard score | 0.934969 | 0.938967 |
| Calibration gap (steering minus public) | -0.0249 | 0.0331 |
| Holdout or rule violations | 0 | 0 |

**The local scores are not comparable to each other.** Each arm reports the number produced by
the validation scheme it chose, and choosing that scheme is part of what is being compared.

The calibration gap is the row that can be read directly: each arm's own steering estimate minus
the same kind of hidden measurement. Its **sign** matters as much as its size -- a positive gap
means the arm believed it was better than it was, which is the direction that costs rank when the
hidden split finally arrives.

## Experiment mix

| Type | Epistemic | Exploiter-only |
| --- | ---: | ---: |
| ablation | 3 | 0 |
| diagnostic | 6 | 0 |
| falsification | 6 | 0 |
| optimization | 0 | 20 |
| replication | 5 | 0 |

## Hypothesis outcomes

| Status | Epistemic | Exploiter-only |
| --- | ---: | ---: |
| contested | 1 | 0 |
| falsified | 5 | 12 |
| retired | 1 | 0 |
| supported | 2 | 8 |

## Notes

- N=1. One competition, one submission per arm. This describes what each arm did; it is not evidence that either method is better.
- **The exploiter reached the higher public score: 0.938967 against 0.934969, a margin of 0.0040.** Twenty rounds of tuning beat an untuned baseline, which is what tuning is for.
- The epistemic arm never tuned a model. It stayed in discovery because both of its validation corrections shrank under replication, and it submitted the untuned full-data baseline its research endorsed. This compares a tuned model against an untuned one.
- Compute parity held only on paper. Both arms passed every budget gate, but the epistemic arm ran at 0.63x its declared estimates and the exploiter at 3.12x -- 0.49 against 2.81 worker wall-hours. Budget gates charge declared estimates and never reconcile them.
- The exploiter's 12 falsified hypotheses are tuning knobs that did not help, not refuted claims about the data. Its hypothesis count is an artefact of one-hypothesis-per-knob bookkeeping.
