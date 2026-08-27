from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v036_blind_suite import (
    DEFAULT_AGENTS,
    audit_agent_view,
    build_blind_structure_suite,
    decrypt_suite_truth,
)


def test_v036_suite_separates_agent_views_from_encrypted_truth(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    public = tmp_path / "public"
    private = tmp_path / "private"
    result = build_blind_structure_suite(
        suite_id="blind-suite-test",
        suite_kind="qualification",
        output_root=public,
        truth_root=private,
        key=key,
        prompt_hash="prompt-hash",
        rows_per_context=600,
    )

    assert result.preflight_passed
    assert len(result.preflight) == 8
    assert sum(item.structure_present for item in result.preflight) == 4
    assert not any(audit_agent_view(public / "agent_views" / agent) for agent in DEFAULT_AGENTS)
    assert not list(public.rglob("*.enc"))

    truth = decrypt_suite_truth(Path(result.encrypted_truth_path), key)
    assert truth.suite_id == "blind-suite-test"
    assert len(truth.context_truth) == 24
    assert len(truth.aliases) == 72
    packet = json.loads((public / "agent_views" / "agent-01" / "agent_packet.json").read_text())
    assert len(packet["packs"]) == 8
    assert all(len(item["contexts"]) == 3 for item in packet["packs"])
    assert "structure_present" not in json.dumps(packet)


def test_v036_agent_column_and_identifier_views_are_distinct(tmp_path: Path) -> None:
    result = build_blind_structure_suite(
        suite_id="blind-suite-alias-test",
        suite_kind="development",
        output_root=tmp_path / "public",
        truth_root=tmp_path / "private",
        key=Fernet.generate_key(),
        prompt_hash="frozen",
        rows_per_context=600,
    )
    packets = [
        json.loads((Path(result.agent_roots[agent]) / "agent_packet.json").read_text()) for agent in DEFAULT_AGENTS
    ]
    pack_sets = [{item["opaque_pack_id"] for item in packet["packs"]} for packet in packets]
    feature_sets = [{tuple(item["feature_columns"]) for item in packet["packs"]} for packet in packets]
    assert len({frozenset(item) for item in pack_sets}) == 3
    assert len({frozenset(item) for item in feature_sets}) == 3
