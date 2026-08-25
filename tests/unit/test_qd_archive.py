from epistemic_loop.domain.enums import RunMode
from epistemic_loop.domain.models import CandidateDescriptors, QDCandidate
from epistemic_loop.qd.archive import QDArchive
from epistemic_loop.qd.descriptors import descriptor_names_for_mode
from epistemic_loop.qd.evolution import EvolutionarySearch, Individual, evolution_directives
from epistemic_loop.qd.finalizer import select_final_candidate


def _candidate(identifier: str, **changes: float) -> QDCandidate:
    values = {
        "expected_hidden_score": 0.8,
        "score_variance": 0.01,
        "normalized_cost": 0.5,
        "leakage_risk": 0.0,
        "robustness": 0.5,
        "error_diversity": 0.2,
    }
    values.update(changes)
    return QDCandidate(
        id=identifier,
        run_id="run-001",
        experiment_id=f"EXP-{identifier}",
        descriptors=CandidateDescriptors(model_family="gbdt", representation="aggregate"),
        **values,
    )


def test_qd_cell_keeps_quality_cost_robustness_and_error_elites() -> None:
    archive = QDArchive(
        descriptor_names=("model_family", "representation"),
        quality_floor_relative_to_best=0.8,
    )
    candidates = [
        _candidate("quality", expected_hidden_score=0.96),
        _candidate("cheap", expected_hidden_score=0.88, normalized_cost=0.05),
        _candidate("robust", expected_hidden_score=0.88, robustness=0.99),
        _candidate("diverse", expected_hidden_score=0.88, error_diversity=0.95),
    ]
    for candidate in candidates:
        archive.add(candidate)

    cell = archive.entries[0]
    assert cell.best_quality == "quality"
    assert cell.lowest_cost == "cheap"
    assert cell.highest_robustness == "robust"
    assert cell.highest_error_diversity == "diverse"
    assert {item.id for item in archive.candidates} == {item.id for item in candidates}


def test_system_b_and_b_plus_use_different_descriptor_spaces() -> None:
    assert descriptor_names_for_mode(RunMode.SYSTEM_A) == ()
    assert "validation_type" not in descriptor_names_for_mode(RunMode.SYSTEM_B)
    assert "validation_type" in descriptor_names_for_mode(RunMode.SYSTEM_B_PLUS)


def test_evolutionary_search_is_seed_reproducible() -> None:
    population = [Individual("low", 1, 0.1), Individual("high", 10, 0.9)]

    def mutate(value, rng):
        return value + rng.choice([-1, 1])

    def crossover(left, right, _rng):
        return (left + right) // 2

    first = EvolutionarySearch(population, seed=42).ask(8, mutate=mutate, crossover=crossover)
    second = EvolutionarySearch(population, seed=42).ask(8, mutate=mutate, crossover=crossover)
    assert first == second
    assert len(first) == 8


def test_evolution_directives_record_mutation_or_distinct_crossover_parents() -> None:
    candidates = [_candidate("left"), _candidate("right", expected_hidden_score=0.9)]
    first = evolution_directives(candidates, count=20, seed=42, crossover_probability=0.5)
    second = evolution_directives(candidates, count=20, seed=42, crossover_probability=0.5)

    assert first == second
    assert all(item["variation_operator"] in {"mutation", "crossover"} for item in first)
    assert all(len(item["parent_candidate_ids"]) in {1, 2} for item in first)
    assert all(len(set(item["parent_candidate_ids"])) == len(item["parent_candidate_ids"]) for item in first)


def test_finalizer_can_prefer_a_robust_diverse_candidate() -> None:
    brittle = _candidate("brittle", expected_hidden_score=0.90, robustness=0.0, error_diversity=0.0)
    useful = _candidate("useful", expected_hidden_score=0.86, robustness=1.0, error_diversity=0.8)
    assert select_final_candidate([brittle, useful]).id == "useful"
