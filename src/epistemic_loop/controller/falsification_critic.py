from __future__ import annotations

from collections.abc import Sequence

from epistemic_loop.domain.models import FalsificationCriticResult, StructureTestPreregistration


class FalsificationTestCritic:
    """Stateless design review for structure tests.

    It sees no agent posterior, candidate score, or global best.  Its only job is
    to reject tests that cannot distinguish the registered explanations.
    """

    def __init__(self, *, minimum_matched_null_repetitions: int = 20):
        if minimum_matched_null_repetitions < 1:
            raise ValueError("minimum matched-null repetitions must be positive")
        self.minimum_matched_null_repetitions = minimum_matched_null_repetitions

    def review(
        self,
        test: StructureTestPreregistration,
        *,
        existing_tests: Sequence[StructureTestPreregistration] = (),
    ) -> FalsificationCriticResult:
        target_prediction = test.prediction_by_hypothesis[test.target_hypothesis_id]
        rival_predictions = [test.prediction_by_hypothesis[item] for item in test.competing_hypothesis_ids]
        signature = test.semantic_signature.model_dump(mode="json")
        is_duplicate = any(item.semantic_signature.model_dump(mode="json") == signature for item in existing_tests)
        requires_matched_null = any(
            marker in identifier.lower()
            for identifier in test.competing_hypothesis_ids
            for marker in ("null", "frequency", "linkage", "shuffle")
        )
        power_tokens = ("bootstrap", "confidence", "power", "seed", "horizon", "repetition", "replicate")
        checks = {
            "main_false_cannot_pass": all(item != target_prediction for item in rival_predictions),
            "rival_predictions_differ": len(set(test.prediction_by_hypothesis.values())) >= 2,
            "confounders_preserved": bool(test.confounders_preserved),
            "not_semantic_duplicate": not is_duplicate,
            "fold_leakage_blocked": test.fold_safe,
            "adequate_power": any(token in test.power_plan.lower() for token in power_tokens)
            and (not requires_matched_null or test.null_repetitions >= self.minimum_matched_null_repetitions),
            "decision_binding_present": bool(test.decision_affected.strip()),
        }
        reasons = [name for name, passed in checks.items() if not passed]
        return FalsificationCriticResult(
            test_id=test.test_id,
            passed=not reasons,
            checks=checks,
            reasons=reasons,
        )
