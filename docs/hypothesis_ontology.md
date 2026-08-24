# Hypothesis ontology

Hypotheses cover validation, distribution shift, temporal and entity structure, leakage, target and
metric semantics, sampling, label noise, representation, feature/model families, augmentation,
external data, candidate generation, ensemble diversity, robustness, and computation.

Confidence is an operational prioritization score, not a calibrated claim of truth. It is updated
only from preregistered evidence through bounded log-odds weights and is clipped to 0.05–0.95.
Graph edges are `supports`, `contradicts`, `refines`, `alternative_to`, `depends_on`, `explains`, and
`invalidates`. The default active set is capped at 30.
