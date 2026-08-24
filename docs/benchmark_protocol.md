# Benchmark protocol

System A selects expected robust improvement per cost. System B uses the epistemic utility and then
hands a validated space to the same exploiter. Data, commit, model/provider pool, paired seed,
budgets, retry rules, source policy, environment, and one final submission are held equal.

At least three (recommended five) paired replicates are independent. No run shares research state.
Public and private scores remain encrypted until all runs complete. Reports include every run,
including failures, compute, CV/private gaps, discoveries, falsification, negative control, and the
contamination audit.

## What is scored

Private rank alone cannot tell the two systems apart: a run that reaches the same score by grinding
a misleading split has not done the same work as one that found the structure. `finalize_benchmark`
therefore reports four axes per pair.

| Metric | Meaning |
| --- | --- |
| `sealed_regret` | distance from the scenario's best attainable outcome; sealed until finalization |
| `*_cv_private_gap` | what the run's own local numbers would have implied minus what it actually earned |
| `compute_overhead`, `regret_removed_per_extra_cpu_hour` | what the research overhead bought |
| `*_discovery_rate` | weighted share of the scenario's planted structure the run named |

**Discovery is the headline claim, not rank.** Each scenario declares `GoldFinding`s with acceptable
discovery patterns; `concept_match` credits a run for naming the concept. Both arms are credited
symmetrically for whatever the action they selected exposes — crediting only the epistemic arm would
decide the comparison in advance — so the discovery gap is a consequence of what each system chose
to run.

## Scenarios

| Scenario | Planted structure | Gold finding |
| --- | --- | --- |
| `temporal_shift` | the evaluation split is time-ordered, so random k-fold overstates the score | temporal validation |
| `spurious_leakage` | one feature is target-derived and absent at inference time | leaky feature |
| `candidate_generation_bottleneck` | the ranker cannot exceed the recall of its candidate generator | recall ceiling |
| `iid_easy` | **negative control** — nothing to find | none |

The negative control is the honesty check. It is an ordinary IID problem where the researcher is
supposed to earn nothing and is charged 20% extra compute for trying. `negative_control_win_rate`
and `negative_control_overhead` are reported at the top level: a research system that also wins here
is measuring something other than research.

**These scenarios are a harness test.** Their gains and regrets are stipulated, so the benchmark
demonstrates that the selection policy prefers informative actions and pays for its overhead — not
that the loop beats an exploiter on a real competition.
