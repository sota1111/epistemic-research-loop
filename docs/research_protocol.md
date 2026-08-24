# Research protocol

Every experiment is preregistered with linked hypotheses, predictions under true and false states,
split, seeds, metrics, controls, decision rule, cost, and required artifacts. Editing any of those
after seeing results creates a new version and event.

An improvement is not trusted from a single CV number. Adoption requires seed/fold reproduction,
subgroup and temporal checks where applicable, leak/duplicate checks, and explicit consideration of
the strongest remaining alternative explanation. Three consecutive optimization experiments force
a diagnostic, replication, or falsification experiment. A high-impact hypothesis cannot become
supported without a falsification attempt.

Discovery diagnoses validation, metrics, shifts, entities, time, leakage, and baseline error.
Consolidation compares lineages, ablates improvements, and establishes robustness. Exploitation runs
HPO and ensembles inside the approved search space. Rank reversal, seed instability, localized gains,
or implausible validation can return the run to research.

The phase is decided from the record, not declared. `derive_phase_evidence` folds the event log into
the six flags the policy reads, so an unattended run progresses on its own — and exploitation cannot
begin until the research brief is published. See [exploiter handoff](exploiter_handoff.md).

Each round is a state machine, and every step appends to the canonical log:
`hypothesizing -> planning -> scoring -> selecting -> executing -> parsing -> falsifying -> updating
-> phase_decision`, with `phase_decision -> exploiter_handoff -> planning` the one way into
exploitation. A step invoked from the wrong state is refused rather than silently reordered, so the
record cannot claim a prediction was preregistered after its result was seen.

Local cross-validation is what the loop reads, so its cadence is bounded by compute rather than by
Kaggle's five-submissions-a-day allowance: ten or more rounds a day is ordinary, and the loop never
spends a submission.

Automation changes who fills the proposal slots, not who decides what counts as evidence. The model
is consulted three times per round — propose hypotheses, design experiments, judge which predictions
the evidence matched. The disposition that follows from those matches, the evidence weight, the
log-odds update, the gates, the utility, and the budget are computed from the proposal, not asked
for.
