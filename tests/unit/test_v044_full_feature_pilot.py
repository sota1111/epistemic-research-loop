from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import _auc
from epistemic_loop.benchmark.v042_multi_competition_suite import CompetitionSpec
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_CONFIRMATION_ROWS,
    V044_RESEARCH_ROWS,
    V044_TRANSFER_ROWS,
    _visible_column_map_generic,
    build_v044_suite,
    select_all_generic_columns,
)

_TEST_CONFIGS = {
    "agent-01-s1": {"config_id": "T-p1", "cli": "codex", "model": "gpt-5.6-sol", "prompt_arm": "p1"},
    "agent-02-s1": {"config_id": "T-p3", "cli": "codex", "model": "gpt-5.6-sol", "prompt_arm": "p3"},
}


def _write_pilot_csv(path: Path, *, rows: int, feature_columns: int) -> None:
    rng = np.random.RandomState(11)
    features = rng.standard_normal((rows, feature_columns))
    logit = sum(0.6 * features[:, i] for i in range(min(5, feature_columns))) - 1.0
    probability = 1 / (1 + np.exp(-logit))
    target = (rng.uniform(size=rows) < probability).astype(int)
    data: dict[str, object] = {"row_key": range(rows), "target": target}
    for index in range(feature_columns):
        column = features[:, index]
        if index == feature_columns - 1:
            column = column.copy()
            column[:6] = float("nan")  # 6/200 = 3% missingness, above the 0.02 default threshold
        data[f"var_{index}"] = column
    pd.DataFrame(data).to_csv(path, index=False)


def _spec(csv_path: Path) -> CompetitionSpec:
    return CompetitionSpec(
        competition_id="synthetic-pilot",
        data_path=csv_path,
        target_column="target",
        id_columns=frozenset({"row_key"}),
        time_column=None,
    )


def test_select_all_generic_columns_excludes_id_target_and_high_missingness(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    _write_pilot_csv(csv_path, rows=200, feature_columns=30)
    spec = _spec(csv_path)
    columns = select_all_generic_columns(spec)
    assert "row_key" not in columns
    assert "target" not in columns
    assert "var_29" not in columns
    assert len(columns) == 29


def test_visible_column_map_generic_is_deterministic_and_unique() -> None:
    key = Fernet.generate_key()
    columns = [f"var_{i}" for i in range(120)]
    map_a = _visible_column_map_generic(key, "suite-1", "run-1", columns)
    map_b = _visible_column_map_generic(key, "suite-1", "run-1", columns)
    map_c = _visible_column_map_generic(key, "suite-1", "run-2", columns)
    assert map_a == map_b
    assert map_a != map_c
    assert len(set(map_a.values())) == len(columns)


def test_build_v044_suite_end_to_end_synthetic_plumbing(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    total_rows = V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS
    _write_pilot_csv(csv_path, rows=total_rows + 500, feature_columns=40)
    spec = _spec(csv_path)

    prompt_p1 = tmp_path / "p1.md"
    prompt_p1.write_text("p1 prompt body\n")
    prompt_p3 = tmp_path / "p3.md"
    prompt_p3.write_text("p3 prompt body\n")

    key = Fernet.generate_key()
    scorer_key = Fernet.generate_key()
    output_root = tmp_path / "run" / "suite-01"
    truth_root = tmp_path / "truth"
    result = build_v044_suite(
        spec,
        output_root=output_root,
        truth_root=truth_root,
        key=key,
        scorer_key=scorer_key,
        prompt_paths={"p1": prompt_p1, "p3": prompt_p3},
        suite_id="suite-01",
        configs=_TEST_CONFIGS,
        run_ids=tuple(_TEST_CONFIGS),
    )

    assert result.column_count >= 20
    assert {run.run_id for run in result.runs} == set(_TEST_CONFIGS)

    view_root_p1 = output_root / "agent_views" / "agent-01-s1"
    view_root_p3 = output_root / "agent_views" / "agent-02-s1"
    packet_p1 = json.loads((view_root_p1 / "agent_packet.json").read_text())
    packet_p3 = json.loads((view_root_p3 / "agent_packet.json").read_text())
    assert packet_p1["research_rows"] == V044_RESEARCH_ROWS
    assert packet_p1["confirmation_rows"] == V044_CONFIRMATION_ROWS
    assert packet_p1["transfer_rows"] == V044_TRANSFER_ROWS
    assert len(packet_p1["feature_columns"]) == result.column_count
    assert "row_key" not in json.dumps(packet_p1)
    assert (view_root_p1 / "agent_prompt.md").read_text() == "p1 prompt body\n"
    assert (view_root_p3 / "agent_prompt.md").read_text() == "p3 prompt body\n"
    # different runs get independently-salted column names even though the underlying
    # row split (and therefore the real data behind each column) is shared
    assert set(packet_p1["feature_columns"]) != set(packet_p3["feature_columns"])

    research = json.loads((view_root_p1 / "research.json").read_text())
    confirmation = json.loads((view_root_p1 / "confirmation.json").read_text())
    assert "target" in research[0]
    assert "target" not in confirmation[0]

    confirmation_labels = json.loads(Fernet(scorer_key).decrypt(Path(result.confirmation_labels_path).read_bytes()))
    transfer_labels = json.loads(Fernet(key).decrypt(Path(result.transfer_labels_path).read_bytes()))
    assert len(confirmation_labels) == V044_CONFIRMATION_ROWS
    assert len(transfer_labels) == V044_TRANSFER_ROWS
    assert set(int(v) for v in confirmation_labels.values()) <= {0, 1}

    # the reference baseline should recover real synthetic signal well above chance
    assert result.reference_baseline_transfer_auc > 0.6

    # a perfect-oracle submission scored against the confirmation labels should be ~1.0
    predictions = {row_id: float(label) for row_id, label in confirmation_labels.items()}
    ordered = sorted(confirmation_labels, key=int)
    oracle_auc = _auc(
        [float(confirmation_labels[i]) for i in ordered],
        [predictions[i] for i in ordered],
    )
    assert oracle_auc == pytest.approx(1.0)


def test_build_v044_suite_column_limit_is_deterministic_subsample(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    total_rows = V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS
    _write_pilot_csv(csv_path, rows=total_rows + 500, feature_columns=40)
    spec = _spec(csv_path)
    prompt_p1 = tmp_path / "p1.md"
    prompt_p1.write_text("p1 prompt body\n")
    prompt_p3 = tmp_path / "p3.md"
    prompt_p3.write_text("p3 prompt body\n")

    def _build(output_dir: str) -> object:
        return build_v044_suite(
            spec,
            output_root=tmp_path / "run" / output_dir,
            truth_root=tmp_path / "truth" / output_dir,
            key=Fernet.generate_key(),
            scorer_key=Fernet.generate_key(),
            prompt_paths={"p1": prompt_p1, "p3": prompt_p3},
            suite_id="suite-limit",
            configs=_TEST_CONFIGS,
            run_ids=tuple(_TEST_CONFIGS),
            column_limit=10,
        )

    result_a = _build("limit-a")
    _build("limit-b")
    assert result_a.column_count == 10
    view_root_a = tmp_path / "run" / "limit-a" / "agent_views" / "agent-01-s1"
    view_root_b = tmp_path / "run" / "limit-b" / "agent_views" / "agent-01-s1"
    packet_a = json.loads((view_root_a / "agent_packet.json").read_text())
    packet_b = json.loads((view_root_b / "agent_packet.json").read_text())
    assert len(packet_a["feature_columns"]) == 10
    # same suite_id + master_seed -> same underlying column subset (subsample is
    # deterministic), even though the visible salted names differ per run's HMAC.
    assert packet_a["research_rows"] == packet_b["research_rows"] == V044_RESEARCH_ROWS


def test_build_v044_suite_confirmation_scoring_disabled_omits_scorer_surface(tmp_path: Path) -> None:
    csv_path = tmp_path / "train.csv"
    total_rows = V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS
    _write_pilot_csv(csv_path, rows=total_rows + 500, feature_columns=40)
    spec = _spec(csv_path)
    prompt_p1 = tmp_path / "p1.md"
    prompt_p1.write_text("p1 prompt body\n")
    prompt_p3 = tmp_path / "p3.md"
    prompt_p3.write_text("p3 prompt body\n")

    result = build_v044_suite(
        spec,
        output_root=tmp_path / "run" / "nofb",
        truth_root=tmp_path / "truth" / "nofb",
        key=Fernet.generate_key(),
        scorer_key=Fernet.generate_key(),
        prompt_paths={"p1": prompt_p1, "p3": prompt_p3},
        suite_id="suite-nofb",
        configs=_TEST_CONFIGS,
        run_ids=tuple(_TEST_CONFIGS),
        enable_confirmation_scoring=False,
    )

    assert result.confirmation_labels_path is None
    view_root_p1 = tmp_path / "run" / "nofb" / "agent_views" / "agent-01-s1"
    assert not (view_root_p1 / "confirmation.json").exists()
    packet_p1 = json.loads((view_root_p1 / "agent_packet.json").read_text())
    assert "confirmation_scorer_command" not in packet_p1
    assert "confirmation_file" not in packet_p1
    assert "confirmation_rows" not in packet_p1
    assert packet_p1["research_rows"] == V044_RESEARCH_ROWS
    assert packet_p1["transfer_rows"] == V044_TRANSFER_ROWS
