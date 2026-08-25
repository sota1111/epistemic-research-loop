# Research-state-aware experiment selection

The target architecture is not a checklist distilled from winning Kaggle solutions. It is a
context-conditioned distribution over whether the research process has enough evidence to make
important decisions. Historical solutions provide a weak prior; observations from the current
competition must be able to override it.

This design follows the conclusion in [research models](research_models.md): use Active Inference as
the conceptual language, but implement the smallest testable system with Quality Diversity,
Bayesian Experimental Design, explicit falsification, and deterministic belief updates.

## Decision to implement

The preferred state is a distribution, not a target recipe:

\[
G_d(t)=w_d(c)\,[\tau_d(c)-P(A_d=\mathrm{adequate}\mid D_t)]_+.
\]

Here `d` is a research dimension, `c` is competition context, `A_d` means that the dimension is
decision-ready, and `D_t` is the event log through round `t`. The gap and uncertainty are kept
separate:

| Current condition | Appropriate action |
| --- | --- |
| large gap, high uncertainty | run a discriminating diagnostic |
| large gap, low uncertainty | repair the known deficiency rather than diagnose it again |
| small gap, low uncertainty | move budget to performance search |
| small gap, high uncertainty | investigate only if the result can change a downstream decision |

Moving closer to the preferred state is **not itself a reward**. Otherwise an agent can imitate a
winner's research narrative or manufacture uncertainty and collect credit for resolving it. The
state gap determines what knowledge may matter; an experiment earns epistemic value only from a
preregistered, observable prediction that changes a belief or a downstream decision.

## State representation

The eventual state projection has these dimensions:

1. validation fidelity;
2. DGP, temporal/entity structure, and distribution-shift understanding;
3. data and label quality understanding;
4. error and subgroup understanding;
5. hypothesis calibration and falsification coverage;
6. representation/model coverage and OOF error diversity;
7. robustness and hidden-performance belief.

Each projected dimension must contain a posterior or bootstrap distribution, its evidence lineage,
the last update time, and the decisions it affects. A prose summary may be rendered from this
projection, but prose is not canonical state.

The first implementation slice deliberately models only **validation worlds**:

```text
W = {random, time, group, time+group, ...}
P(W | rolling backtests, model-rank reversals, split variance, entity overlap)
```

Validation fidelity is observable through repeated pseudo-future backtests, Spearman/Kendall model
rank stability, rank-reversal rate, and bootstrap uncertainty. This is both the most consequential
state in the historical review and the state for which this repository already has direct evidence:
on the IEEE-CIS retrospective, local CV had Kendall tau -0.20 with the private ordering.

## Historical preferred-state prior

The offline corpus must include Top 1, Top 3--10, public-to-private failures, and unsuccessful but
well-documented approaches. Each annotation records competition context, research dimension,
claim, observable evidence, when it became known, downstream decision, source URL/hash, and
annotator confidence.

The corpus may estimate `P(A_d | context)` and the downstream importance of a dimension. It may not
emit competition-specific actions such as "construct this UID" or "use pseudo-labeling". Evaluation
uses leave-one-competition-out and leave-one-domain-out priors; the evaluated competition's write-up
is never visible at runtime. Prior strength must be versioned and deliberately weak.

The citation placeholders currently embedded in `research_models.md` are not reproducible corpus
identifiers. They must be converted to stable `SourceRef` records before historical fitting starts.

## Preregistered information value

An experiment targeting hypothesis `H` must declare categorical observable outcomes and the two
likelihood vectors `p(y | H, e)` and `p(y | not H, e)`. They include measurement noise and sum to
one. With the current hypothesis probability from the event log, selection computes

\[
\operatorname{EIG}(e)=I(H;Y_e\mid D_t)
\]

mechanically. The LLM may propose the likelihoods, but it cannot assign its own final information
score. Forecast calibration, replication, and held-out predictive log score are reported separately;
a large posterior movement is not automatically evidence of a good experiment.

Where the downstream action set is explicit, Expected Value of Sample Information is preferred:

\[
\operatorname{EVSI}(e)=
E_y[\max_a E(U(a)\mid D_t,e,y)]-\max_a E(U(a)\mid D_t).
\]

Until that action model is credible, selection keeps expected performance and EIG as separately
auditable components. It constructs a Pareto set, applies state-gap priority and an information-
redundancy penalty, then chooses a portfolio under actual compute/token/wall-clock constraints.
The existing scalar rubric remains only as a migration fallback for old proposal and event schemas.

## Multi-agent organization

The minimum useful population has four roles:

| Role | Objective |
| --- | --- |
| Validation/DGP scientist | maintain competing validation, time, entity, and shift worlds |
| Solution explorer | advance the performance/QD frontier across representations and model families |
| Independent falsifier | find the cheapest test of the highest-impact supported belief |
| Meta-controller | deterministically update beliefs, estimate state gaps, and allocate the shared budget |

Agents share immutable empirical facts and artifact references. Working hypotheses and worldviews
remain scoped to their originating role until entered in the explicit registry. The meta-controller
does not use an LLM self-score. Portfolio diversity covers both solution descriptors and epistemic
descriptors, so different models that all assume the same invalid split do not count as epistemically
diverse.

## Delivery sequence and falsification

1. Add likelihood forecasts and belief-conditioned mechanical EIG to selection.
2. Project and report the validation-world posterior and its state gap.
3. Generate role-scoped proposals and select a performance/epistemic portfolio.
4. Add an offline, versioned preferred-state prior only after the online measurements work.
5. Compare strong solution-QD `B`, epistemic-descriptor `B+`, and posterior/EIG `C` at matched
   **observed** compute, tokens, wall time, and submissions.

Primary success remains locked private performance. Validation-to-private rank correlation,
forecast calibration, time-to-critical-discovery, and compute efficiency must mediate that result.
If `B+` matches `C`, explicit EIG is rejected in favor of epistemic QD. If `C` improves state metrics
but not private performance under equal observed budget, the epistemic layer is rejected for Kaggle
optimization.

## Formula convention

Every implementation and document uses positive terms for value and negative terms for cost/risk:

\[
U(e)=\alpha\,\widehat{\Delta Performance}
     +\beta\,EVSI(e)
     +\gamma\,QD(e)
     +\delta\,\widehat{\Delta Robustness}
     -\eta\,Cost(e)
     -\rho\,Risk(e).
\]

The malformed minus/multiplication signs in the imported deep-research report are transcription
artifacts, not the selection policy.
