from epistemic_loop.domain.models import RobustnessAssessment


def robustness_value(assessment: RobustnessAssessment) -> float:
    return assessment.score
