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

Each round is a state machine, and every step appends to the canonical log:
`hypothesizing -> planning -> scoring -> selecting -> executing -> parsing -> falsifying -> updating
-> phase_decision`. A step invoked from the wrong state is refused rather than silently reordered,
so the record cannot claim a prediction was preregistered after its result was seen.

Automation changes who fills the proposal slots, not who decides what counts as evidence. The model
is consulted three times per round — propose hypotheses, design experiments, judge which predictions
the evidence matched. The disposition that follows from those matches, the evidence weight, the
log-odds update, the gates, the utility, and the budget are computed from the proposal, not asked
for.
