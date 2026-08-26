from enum import StrEnum


class RunMode(StrEnum):
    SYSTEM_A = "system_a"
    SYSTEM_B = "system_b"
    SYSTEM_B_PLUS = "system_b_plus"
    SYSTEM_C = "system_c"
    # Backwards-compatible names used by existing run manifests. Their policy is
    # intentionally mapped to A and C rather than silently rewriting old logs.
    EPISTEMIC = "epistemic"
    EXPLOITER_ONLY = "exploiter_only"


class ValidationSplitType(StrEnum):
    RANDOM = "random"
    STRATIFIED = "stratified"
    GROUP = "group"
    TIME = "time"
    ROLLING_TIME = "rolling_time"
    TIME_GROUP = "time_group"
    ENTITY_SEEN = "entity_seen"
    ENTITY_UNSEEN = "entity_unseen"
    ADVERSARIAL_WEIGHTED = "adversarial_weighted"


class ValidationWorldStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class Phase(StrEnum):
    DISCOVERY = "discovery"
    CONSOLIDATION = "consolidation"
    EXPLOITATION = "exploitation"
    FINALIZED = "finalized"


class ResearchPhase(StrEnum):
    """C-lite v0.2 lifecycle.

    ``Phase`` is retained for replaying v0.1 event logs.  New multi-island
    orchestration uses this more explicit lifecycle so diagnosis cannot be
    confused with candidate implementation.
    """

    PHASE_0_BASELINE = "phase_0_baseline"
    PHASE_1_DIAGNOSIS = "phase_1_diagnosis"
    PHASE_2_HYPOTHESIS_DISCRIMINATION = "phase_2_hypothesis_discrimination"
    PHASE_3_CANDIDATE_IMPLEMENTATION = "phase_3_candidate_implementation"
    PHASE_4_ROBUSTNESS = "phase_4_robustness"
    PHASE_5_ENSEMBLE = "phase_5_ensemble"
    PHASE_6_FINALIZATION = "phase_6_finalization"


class CommunicationMode(StrEnum):
    NO_SHARING = "no_sharing"
    SELECTIVE_DELAYED_ASYMMETRIC = "selective_delayed_asymmetric"
    FULL_LIVE_SHARING = "full_live_sharing"


class EvidenceVisibility(StrEnum):
    PRIVATE = "private"
    CONTROLLER_ONLY = "controller_only"
    SHAREABLE_FACT = "shareable_fact"
    SHARED_CHALLENGE = "shared_challenge"
    GLOBAL_SAFETY = "global_safety"


class EpistemicNiche(StrEnum):
    TEMPORAL = "temporal"
    ENTITY_CLIENT = "entity_client"
    VALIDATION = "validation"
    DISTRIBUTION_SHIFT = "distribution_shift"
    LABEL_QUALITY = "label_quality"
    FEATURE_REPRESENTATION = "feature_representation"
    MODEL_FAMILY = "model_family"
    ERROR_ANALYSIS = "error_analysis"
    FALSIFICATION = "falsification"
    POST_PROCESSING = "post_processing"
    ENSEMBLE = "ensemble"


class AgentResearchState(StrEnum):
    """Dynamic v0.3 state; this is not a permanent agent role."""

    GENERIC_RESEARCH = "generic_research"
    STRUCTURE_DISCOVERY = "structure_discovery"
    STRUCTURE_MATURATION = "structure_maturation"


class StructuralDimension(StrEnum):
    VALIDATION_SPLIT = "validation_split"
    OBSERVATION_OR_PREDICTION_UNIT = "observation_or_prediction_unit"
    ROW_INDEPENDENCE = "row_independence"
    ENTITY_GROUPING = "entity_grouping"
    TEMPORAL_ORDER = "temporal_order"
    FEATURE_GENERATION = "feature_generation"
    CANDIDATE_ROUTING = "candidate_routing"
    POST_PROCESSING = "post_processing"
    TARGET_OR_METRIC_DECOMPOSITION = "target_or_metric_decomposition"
    TRAIN_TEST_GENERATING_PROCESS = "train_test_generating_process"


class StructureLifecycleState(StrEnum):
    OBSERVATION = "observation"
    PROVISIONAL_STRUCTURE = "provisional_structure"
    ALTERNATIVES_REGISTERED = "alternatives_registered"
    DISCRIMINATING_TESTS_PREREGISTERED = "discriminating_tests_preregistered"
    PARTIALLY_VALIDATED = "partially_validated"
    VALIDATED_STRUCTURE = "validated_structure"
    USEFUL_ENCODING_UNVALIDATED_STRUCTURE = "useful_encoding_unvalidated_structure"
    STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE = "structurally_plausible_non_actionable"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class StructureClassification(StrEnum):
    VALIDATED_ACTIONABLE_STRUCTURE = "validated_actionable_structure"
    VALIDATED_NON_ACTIONABLE_STRUCTURE = "validated_non_actionable_structure"
    USEFUL_ENCODING_UNVALIDATED_STRUCTURE = "useful_encoding_unvalidated_structure"
    REJECTED_STRUCTURE = "rejected_structure"


class ValidationDebtStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class ValidationRequirementOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WAIVED_BY_FUTILITY = "waived_by_futility"
    WAIVED_BY_FAILED_PREREQUISITE = "waived_by_failed_prerequisite"
    INCONCLUSIVE = "inconclusive"


class MaturationChildRole(StrEnum):
    IMPLEMENTATION = "implementation"
    NULL_SKEPTIC = "null_skeptic"
    VERIFICATION = "verification"


class MaturationForkStatus(StrEnum):
    ACTIVE = "active"
    DISSOLVED = "dissolved"


class ExperimentKind(StrEnum):
    DIAGNOSTIC = "diagnostic"
    CANDIDATE_PRODUCING = "candidate_producing"


class DecisionOutcome(StrEnum):
    ACTION_CHANGING = "informative_action_changing"
    ACTION_NEUTRAL = "informative_action_neutral"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


class TerminalStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED_EXECUTION = "FAILED_EXECUTION"
    FAILED_RESOURCE = "FAILED_RESOURCE"
    INVALID_ARTIFACT = "INVALID_ARTIFACT"
    INVALID_LEAKAGE = "INVALID_LEAKAGE"
    INCONCLUSIVE = "INCONCLUSIVE"


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class LoopState(StrEnum):
    CREATED = "created"
    OBSERVING = "observing"
    HYPOTHESIZING = "hypothesizing"
    PLANNING = "planning"
    SCORING = "scoring"
    SELECTING = "selecting"
    EXECUTING = "executing"
    PARSING = "parsing"
    FALSIFYING = "falsifying"
    UPDATING = "updating"
    PHASE_DECISION = "phase_decision"
    EXPLOITER_HANDOFF = "exploiter_handoff"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class HypothesisType(StrEnum):
    VALIDATION = "validation"
    DISTRIBUTION_SHIFT = "distribution_shift"
    TEMPORAL_STRUCTURE = "temporal_structure"
    ENTITY_STRUCTURE = "entity_structure"
    LEAKAGE = "leakage"
    TARGET_SEMANTICS = "target_semantics"
    METRIC_SEMANTICS = "metric_semantics"
    SAMPLING = "sampling"
    LABEL_NOISE = "label_noise"
    REPRESENTATION = "representation"
    FEATURE_FAMILY = "feature_family"
    MODEL_FAMILY = "model_family"
    AUGMENTATION = "augmentation"
    EXTERNAL_DATA = "external_data"
    CANDIDATE_GENERATION = "candidate_generation"
    ENSEMBLE_DIVERSITY = "ensemble_diversity"
    ROBUSTNESS = "robustness"
    COMPUTATIONAL = "computational"


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    TESTABLE = "testable"
    UNDER_TEST = "under_test"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    FALSIFIED = "falsified"
    RETIRED = "retired"


class Consequence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Direction(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    UNCHANGED = "unchanged"
    PATTERN = "pattern"


class ExperimentType(StrEnum):
    EXPLOIT = "exploit"
    SOLUTION_EXPLORE = "solution_explore"
    EPISTEMIC = "epistemic"
    DIAGNOSTIC = "diagnostic"
    OPTIMIZATION = "optimization"
    FALSIFICATION = "falsification"
    ROBUSTNESS = "robustness"
    ENSEMBLE = "ensemble"
    REPLICATION = "replication"
    ABLATION = "ablation"


class ExperimentStatus(StrEnum):
    PROPOSED = "proposed"
    GATED = "gated"
    SELECTED = "selected"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HoldoutAccess(StrEnum):
    NONE = "none"
    WORKING_VALIDATION = "working_validation"
    SEALED_HOLDOUT = "sealed_holdout"


class HoldoutPolicyName(StrEnum):
    STRICT_BLIND = "strict_blind"
    GATED_BINARY = "gated_binary"
    OPEN_DEBUG = "open_debug"


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FailureClass(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    IMPLEMENTATION = "implementation"
    MODEL = "model"
    INVALID_DESIGN = "invalid_design"


class FalsificationDisposition(StrEnum):
    SURVIVES = "survives"
    WEAKENED = "weakened"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"


class VerifierResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    DISPUTED = "disputed"


class EdgeType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFINES = "refines"
    ALTERNATIVE_TO = "alternative_to"
    DEPENDS_ON = "depends_on"
    EXPLAINS = "explains"
    INVALIDATES = "invalidates"


class LeaderboardFeedbackMode(StrEnum):
    FORBIDDEN = "forbidden"
    GATED_BINARY = "gated_binary"
    NUMERIC = "numeric"
