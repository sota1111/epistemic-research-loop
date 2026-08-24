from epistemic_loop.domain.models import EpistemicAssessment


def epistemic_value_v1(assessment: EpistemicAssessment) -> float:
    return assessment.score
