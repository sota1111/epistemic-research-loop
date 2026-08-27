"""Agent-local evolution and observe-only population qualification for v0.3.5."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from statistics import fmean

LOCAL_STAGNATION_NOTICE_JA = (
    "現在の研究経路は新しいDecisionまたはEvidenceを生成していない。既存Beliefと異なる説明を最低1つ生成せよ。"
)


class ResearchMode(StrEnum):
    EXPLOIT = "exploit"
    EXPLORE = "explore"
    EPISTEMIC = "epistemic"
    NOVEL_EXPLORATION = "novel_exploration"


class ActionType(StrEnum):
    EXPLOITATION = "E1_exploitation"
    SOLUTION_EXPLORATION = "E2_solution_exploration"
    EPISTEMIC_EXPLORATION = "E3_epistemic_exploration"
    STRUCTURE_MATURATION = "E4_structure_maturation"


class LocalCandidateStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ResearchDescriptor:
    hypothesis_family: str
    representation_family: str
    validation_world: str
    data_slice: str
    experiment_operator: str
    model_family: str
    downstream_decision: str
    structural_claim: bool = False

    def __post_init__(self) -> None:
        text = (
            self.hypothesis_family,
            self.representation_family,
            self.validation_world,
            self.data_slice,
            self.experiment_operator,
            self.model_family,
            self.downstream_decision,
        )
        if any(not value.strip() for value in text):
            raise ValueError("research descriptors require every semantic dimension")

    def distance(self, other: ResearchDescriptor) -> float:
        left = (*self.semantic_values, self.structural_claim)
        right = (*other.semantic_values, other.structural_claim)
        return sum(a != b for a, b in zip(left, right, strict=True)) / len(left)

    @property
    def semantic_values(self) -> tuple[str, ...]:
        return (
            self.hypothesis_family,
            self.representation_family,
            self.validation_world,
            self.data_slice,
            self.experiment_operator,
            self.model_family,
            self.downstream_decision,
        )


@dataclass(frozen=True)
class ResearchProposal:
    proposal_id: str
    agent_id: str
    cycle: int
    mode: ResearchMode
    purpose: str
    descriptor: ResearchDescriptor

    def __post_init__(self) -> None:
        if not self.proposal_id.strip() or not self.agent_id.strip() or not self.purpose.strip():
            raise ValueError("proposal identity, owner, and purpose are required")
        if self.cycle < 1:
            raise ValueError("proposal cycle must be positive")


@dataclass(frozen=True)
class CycleProposalSet:
    agent_id: str
    cycle: int
    proposals: tuple[ResearchProposal, ...]

    def __post_init__(self) -> None:
        if len(self.proposals) < 3:
            raise ValueError("every v0.3.5 cycle requires at least three proposals")
        if len({item.proposal_id for item in self.proposals}) != len(self.proposals):
            raise ValueError("proposal identifiers must be unique within a cycle")
        if any(item.agent_id != self.agent_id or item.cycle != self.cycle for item in self.proposals):
            raise ValueError("proposal set may contain only one agent and one cycle")
        modes = {item.mode for item in self.proposals}
        if ResearchMode.EXPLOIT not in modes or ResearchMode.EXPLORE not in modes:
            raise ValueError("every cycle requires exploit and explore proposals")
        if not modes & {ResearchMode.EPISTEMIC, ResearchMode.NOVEL_EXPLORATION}:
            raise ValueError("every cycle requires epistemic or explicit novel exploration")


@dataclass(frozen=True)
class ModeAllocation:
    exploit: float = 0.34
    explore: float = 0.33
    epistemic: float = 0.33

    def __post_init__(self) -> None:
        values = (self.exploit, self.explore, self.epistemic)
        if any(value <= 0 for value in values) or not math.isclose(sum(values), 1.0, abs_tol=1e-9):
            raise ValueError("mode allocation must be positive and sum to one")


@dataclass(frozen=True)
class ModeUpdateEvidence:
    incumbent_gain: float = 0.0
    new_research_state_coverage: float = 0.0
    uncertainty_reduction: float = 0.0
    structure_validation: float = 0.0
    candidate_complementarity: float = 0.0

    def __post_init__(self) -> None:
        if any(
            not 0 <= value <= 1
            for value in (
                self.incumbent_gain,
                self.new_research_state_coverage,
                self.uncertainty_reduction,
                self.structure_validation,
                self.candidate_complementarity,
            )
        ):
            raise ValueError("mode update evidence must be normalized to [0, 1]")


def adapt_mode_allocation(
    current: ModeAllocation,
    evidence: ModeUpdateEvidence,
    *,
    learning_rate: float = 0.25,
) -> ModeAllocation:
    """Update local mode weights without a controller-selected research topic."""

    if not 0 < learning_rate <= 1:
        raise ValueError("learning_rate must lie in (0, 1]")
    rewards = (
        evidence.incumbent_gain,
        fmean((evidence.new_research_state_coverage, evidence.candidate_complementarity)),
        fmean((evidence.uncertainty_reduction, evidence.structure_validation)),
    )
    previous = (current.exploit, current.explore, current.epistemic)
    raw = tuple(
        max(0.05, value * (1 + learning_rate * reward)) for value, reward in zip(previous, rewards, strict=True)
    )
    total = sum(raw)
    return ModeAllocation(*(value / total for value in raw))


@dataclass(frozen=True)
class CandidateResearchOutcome:
    proposal: ResearchProposal
    candidate_id: str
    action_type: ActionType
    local_status: LocalCandidateStatus
    local_primary_metric: float
    artifact_valid: bool
    leakage_safe: bool
    predictions_available: bool
    selected_as_next_parent: bool
    decision_changed: bool
    candidate_improved: bool
    uncertainty_reduction: float
    ensemble_potential: float
    structural_leverage: float = 0.0
    structure_validation_strength: float = 0.0
    parent_semantic_distance: float = 0.0
    sealed_primary_metric: float | None = None
    sealed_parent_metric: float | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate outcome requires an identifier")
        bounded = (
            self.uncertainty_reduction,
            self.ensemble_potential,
            self.structure_validation_strength,
            self.parent_semantic_distance,
        )
        if any(not 0 <= value <= 1 for value in bounded):
            raise ValueError("outcome evidence values must lie in [0, 1]")
        if self.structural_leverage < 0:
            raise ValueError("structural leverage cannot be negative")
        if (self.sealed_primary_metric is None) != (self.sealed_parent_metric is None):
            raise ValueError("sealed challenger and parent metrics must be measured together")

    @property
    def final_recheck_eligible(self) -> bool:
        return (
            self.artifact_valid
            and self.leakage_safe
            and self.predictions_available
            and self.parent_semantic_distance > 0
        )

    @property
    def sealed_selected_metric(self) -> float | None:
        if self.sealed_primary_metric is None or self.sealed_parent_metric is None:
            return None
        if self.local_status is LocalCandidateStatus.ACCEPTED:
            return self.sealed_primary_metric
        return self.sealed_parent_metric

    @property
    def sealed_decision_regret(self) -> float | None:
        selected = self.sealed_selected_metric
        if selected is None or self.sealed_primary_metric is None or self.sealed_parent_metric is None:
            return None
        return max(self.sealed_primary_metric, self.sealed_parent_metric) - selected


@dataclass(frozen=True)
class LocalEliteSet:
    performance: CandidateResearchOutcome | None
    information: CandidateResearchOutcome | None
    structural: CandidateResearchOutcome | None


class LocalResearchPortfolio:
    """Three-lineage local archive; rejected valid candidates remain recoverable."""

    def __init__(self, agent_id: str):
        if not agent_id.strip():
            raise ValueError("agent identifier is required")
        self.agent_id = agent_id
        self.mode_allocation = ModeAllocation()
        self._proposal_sets: list[CycleProposalSet] = []
        self._outcomes: list[CandidateResearchOutcome] = []
        self._shadow: dict[str, CandidateResearchOutcome] = {}

    @property
    def proposal_sets(self) -> tuple[CycleProposalSet, ...]:
        return tuple(self._proposal_sets)

    @property
    def outcomes(self) -> tuple[CandidateResearchOutcome, ...]:
        return tuple(self._outcomes)

    @property
    def shadow_candidates(self) -> tuple[CandidateResearchOutcome, ...]:
        return tuple(self._shadow[key] for key in sorted(self._shadow))

    @property
    def final_recheck_candidates(self) -> tuple[CandidateResearchOutcome, ...]:
        return tuple(item for item in self._outcomes if item.final_recheck_eligible)

    @property
    def elites(self) -> LocalEliteSet:
        valid = [item for item in self._outcomes if item.artifact_valid and item.leakage_safe]
        performance = max(valid, key=lambda item: item.local_primary_metric, default=None)
        information = max(valid, key=lambda item: item.uncertainty_reduction, default=None)
        structural_values = [item for item in valid if item.proposal.descriptor.structural_claim]
        structural = max(
            structural_values,
            key=lambda item: item.structural_leverage * item.structure_validation_strength,
            default=None,
        )
        return LocalEliteSet(performance, information, structural)

    def local_novelty(self, descriptor: ResearchDescriptor) -> float:
        if not self._outcomes:
            return 1.0
        return min(descriptor.distance(item.proposal.descriptor) for item in self._outcomes)

    def register_proposals(self, proposals: CycleProposalSet) -> None:
        if proposals.agent_id != self.agent_id:
            raise PermissionError("an agent may register only its own proposal set")
        if self._proposal_sets and proposals.cycle <= self._proposal_sets[-1].cycle:
            raise ValueError("agent cycles must strictly increase")
        self._proposal_sets.append(proposals)

    def record(self, outcome: CandidateResearchOutcome) -> None:
        if outcome.proposal.agent_id != self.agent_id:
            raise PermissionError("an agent may record only its own outcomes")
        if not any(
            outcome.proposal.proposal_id == item.proposal_id
            for proposal_set in self._proposal_sets
            for item in proposal_set.proposals
        ):
            raise ValueError("outcome must reference a preregistered local proposal")
        if any(item.candidate_id == outcome.candidate_id for item in self._outcomes):
            raise ValueError(f"duplicate local candidate: {outcome.candidate_id}")
        self._outcomes.append(outcome)
        if outcome.local_status is LocalCandidateStatus.REJECTED and outcome.final_recheck_eligible:
            self._shadow[outcome.candidate_id] = outcome

    def update_mode_allocation(self, evidence: ModeUpdateEvidence) -> ModeAllocation:
        self.mode_allocation = adapt_mode_allocation(self.mode_allocation, evidence)
        return self.mode_allocation


@dataclass(frozen=True)
class LocalStagnationDecision:
    stagnated: bool
    stagnant_cycles: int
    notification: str | None


class LocalSearchStagnationDetector:
    def __init__(self, *, required_cycles: int = 2):
        if required_cycles < 2:
            raise ValueError("local stagnation requires at least two cycles")
        self.required_cycles = required_cycles
        self._history: list[CandidateResearchOutcome] = []

    def assess(self, outcome: CandidateResearchOutcome) -> LocalStagnationDecision:
        self._history.append(outcome)
        tail = self._history[-self.required_cycles :]
        same_family = (
            len(tail) == self.required_cycles
            and len({item.proposal.descriptor.hypothesis_family for item in tail}) == 1
        )
        no_progress = same_family and all(
            not item.decision_changed and not item.candidate_improved and item.uncertainty_reduction <= 0
            for item in tail
        )
        return LocalStagnationDecision(
            stagnated=no_progress,
            stagnant_cycles=len(tail) if no_progress else 0,
            notification=LOCAL_STAGNATION_NOTICE_JA if no_progress else None,
        )


@dataclass(frozen=True)
class AgentQualificationScorecard:
    agent_id: str
    semantic_families: int
    effective_family_count: float
    repeated_family_rate: float
    incumbent_improvements: int
    successful_parent_changes: int
    rejected_challengers: int
    hypotheses_generated: int
    falsification_tests: int
    belief_changes: int
    provisional_structures: int
    validated_structures: int
    falsified_structures: int
    false_promotions: int
    best_local_candidate: str | None
    best_sealed_candidate: str | None
    selection_regret: float | None
    complementary_candidates: int
    shadow_candidates: int

    @classmethod
    def from_portfolio(
        cls,
        portfolio: LocalResearchPortfolio,
        *,
        validated_structures: int = 0,
        falsified_structures: int = 0,
        false_promotions: int = 0,
    ) -> AgentQualificationScorecard:
        outcomes = portfolio.outcomes
        counts = Counter(item.proposal.descriptor.hypothesis_family for item in outcomes)
        best_local = max(outcomes, key=lambda item: item.local_primary_metric, default=None)
        sealed = [
            item
            for item in outcomes
            if item.sealed_primary_metric is not None and item.sealed_parent_metric is not None
        ]
        best_sealed = max(sealed, key=_sealed_value, default=None)
        regret = None
        if best_sealed is not None and sealed:
            final_selected = sealed[-1].sealed_selected_metric
            oracle = max(max(_sealed_value(item), _sealed_parent_value(item)) for item in sealed)
            if final_selected is not None:
                regret = oracle - final_selected
        epistemic = [
            item
            for item in outcomes
            if item.action_type in {ActionType.EPISTEMIC_EXPLORATION, ActionType.STRUCTURE_MATURATION}
        ]
        return cls(
            agent_id=portfolio.agent_id,
            semantic_families=len(counts),
            effective_family_count=_effective_count(counts),
            repeated_family_rate=(1 - len(counts) / len(outcomes)) if outcomes else 0.0,
            incumbent_improvements=sum(item.candidate_improved for item in outcomes),
            successful_parent_changes=sum(item.selected_as_next_parent for item in outcomes),
            rejected_challengers=sum(item.local_status is LocalCandidateStatus.REJECTED for item in outcomes),
            hypotheses_generated=len(epistemic),
            falsification_tests=sum(item.uncertainty_reduction > 0 for item in epistemic),
            belief_changes=sum(item.uncertainty_reduction > 0 for item in outcomes),
            provisional_structures=sum(item.proposal.descriptor.structural_claim for item in outcomes),
            validated_structures=validated_structures,
            falsified_structures=falsified_structures,
            false_promotions=false_promotions,
            best_local_candidate=best_local.candidate_id if best_local else None,
            best_sealed_candidate=best_sealed.candidate_id if best_sealed else None,
            selection_regret=regret,
            complementary_candidates=sum(item.ensemble_potential > 0 for item in outcomes),
            shadow_candidates=len(portfolio.shadow_candidates),
        )


@dataclass(frozen=True)
class PopulationQualificationScorecard:
    agents: tuple[AgentQualificationScorecard, ...]
    independent_research_diversity: float
    qualifying_agents: int
    population_effective_research_family: float
    dominant_family_fraction: float
    action_mix: dict[str, int]
    executed_action_types: int
    dominant_action_fraction: float
    shadow_candidate_recovery_rate: float | None
    diversity_gate_passed: bool
    action_balance_gate_passed: bool


def build_population_scorecard(
    portfolios: Sequence[LocalResearchPortfolio],
) -> PopulationQualificationScorecard:
    if len(portfolios) != 3 or len({item.agent_id for item in portfolios}) != 3:
        raise ValueError("Phase 1 qualification requires exactly three independent agents")
    scorecards = tuple(AgentQualificationScorecard.from_portfolio(item) for item in portfolios)
    qualifying = sum(item.semantic_families >= 2 or item.falsification_tests >= 2 for item in scorecards)
    family_counts: Counter[str] = Counter(
        outcome.proposal.descriptor.hypothesis_family for item in portfolios for outcome in item.outcomes
    )
    action_counts: Counter[str] = Counter(outcome.action_type.value for item in portfolios for outcome in item.outcomes)
    total_families = sum(family_counts.values())
    total_actions = sum(action_counts.values())
    shadow = [outcome for item in portfolios for outcome in item.shadow_candidates]
    shadow_scored = [
        item for item in shadow if item.sealed_primary_metric is not None and item.sealed_parent_metric is not None
    ]
    recovered = [item for item in shadow_scored if _sealed_value(item) > _sealed_parent_value(item)]
    effective = _effective_count(family_counts)
    dominant_family = max(family_counts.values(), default=0) / total_families if total_families else 0.0
    dominant_action = max(action_counts.values(), default=0) / total_actions if total_actions else 0.0
    return PopulationQualificationScorecard(
        agents=scorecards,
        independent_research_diversity=qualifying / len(portfolios),
        qualifying_agents=qualifying,
        population_effective_research_family=effective,
        dominant_family_fraction=dominant_family,
        action_mix=dict(sorted(action_counts.items())),
        executed_action_types=len(action_counts),
        dominant_action_fraction=dominant_action,
        shadow_candidate_recovery_rate=(len(recovered) / len(shadow_scored) if shadow_scored else None),
        diversity_gate_passed=qualifying >= 2 and effective >= 2.5 and dominant_family <= 0.6,
        action_balance_gate_passed=len(action_counts) >= 3 and dominant_action <= 0.70,
    )


def _effective_count(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    probabilities = [count / total for count in counts.values()]
    return math.exp(-sum(value * math.log(value) for value in probabilities))


def _sealed_value(outcome: CandidateResearchOutcome) -> float:
    if outcome.sealed_primary_metric is None:
        raise ValueError("sealed score was not measured")
    return outcome.sealed_primary_metric


def _sealed_parent_value(outcome: CandidateResearchOutcome) -> float:
    if outcome.sealed_parent_metric is None:
        raise ValueError("sealed parent score was not measured")
    return outcome.sealed_parent_metric
