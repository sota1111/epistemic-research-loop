from datetime import date

from epistemic_loop.contamination.source_policy import StrictHistoricalSourcePolicy


def test_kaggle_discussion_and_competition_github_are_blocked() -> None:
    policy = StrictHistoricalSourcePolicy("ieee-fraud-detection", date(2019, 5, 1))
    discussion = policy.evaluate(
        "https://www.kaggle.com/competitions/ieee-fraud-detection/discussion/1",
        title="solution",
        published_at=date(2019, 9, 1),
        competition_specific=True,
    )
    github = policy.evaluate(
        "https://github.com/example/ieee-fraud-solution",
        title="IEEE solution",
        published_at=date(2020, 1, 1),
        competition_specific=True,
    )
    assert not discussion.allowed
    assert not github.allowed


def test_general_precompetition_paper_is_allowed() -> None:
    policy = StrictHistoricalSourcePolicy("ieee-fraud-detection", date(2019, 5, 1))
    decision = policy.evaluate(
        "https://arxiv.org/abs/1810.00001",
        title="Temporal validation for fraud detection",
        published_at=date(2018, 10, 1),
        competition_specific=False,
    )
    assert decision.allowed


def test_competition_slug_is_blocked_in_literature_query() -> None:
    policy = StrictHistoricalSourcePolicy("ieee-fraud-detection", date(2019, 5, 1))
    assert not policy.validate_search_query("IEEE fraud detection winning solution").allowed
    assert policy.validate_search_query("fraud temporal distribution shift validation").allowed
