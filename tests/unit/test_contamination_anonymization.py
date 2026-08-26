import csv
from pathlib import Path

from epistemic_loop.config import load_config
from epistemic_loop.contamination.anonymize import (
    anonymize_competition_package,
    anonymize_csv_columns,
    anonymous_identifier,
)
from epistemic_loop.controller.research_graph import ResearchController
from epistemic_loop.storage.repositories import ResearchRepository


def test_competition_and_columns_are_deterministically_anonymized() -> None:
    package = {
        "competition_name": "Famous Competition",
        "columns": ["customer_id", {"name": "event_time", "dtype": "int"}],
        "target": "customer_id",
        "description": "Famous Competition historical package",
    }
    anonymized, mapping = anonymize_competition_package(package, salt="run", hash_column_names=True)

    assert anonymized["competition_name"] == anonymous_identifier("Famous Competition", salt="run")
    assert "customer_id" not in str(anonymized)
    assert "Famous Competition" not in str(anonymized)
    assert anonymized["target"] == mapping["customer_id"]
    assert package["target"] == "customer_id"


def test_csv_variant_changes_only_the_header(tmp_path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "anonymous.csv"
    source.write_text("identity,time,value\na,1,0.5\nb,2,0.7\n", encoding="utf-8")

    mapping = anonymize_csv_columns(source, destination, salt="run")

    with destination.open(newline="", encoding="utf-8") as file:
        rows = list(csv.reader(file))
    assert rows[0] == [mapping["identity"], mapping["time"], mapping["value"]]
    assert rows[1:] == [["a", "1", "0.5"], ["b", "2", "0.7"]]


def test_anonymous_variant_does_not_leak_competition_name_into_default_run_id(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    config = load_config(root / "configs" / "system_c_anonymous.yaml")
    controller = ResearchController(ResearchRepository(tmp_path / "runs", tmp_path / "state.db"))

    run = controller.create_run(config, base_commit_sha="abc", dataset_fingerprint="f" * 64)

    assert config.competition.slug not in run.id
    assert config.competition.slug != run.competition_id
