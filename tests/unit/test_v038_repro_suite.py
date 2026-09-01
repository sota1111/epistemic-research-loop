from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import audit_v037_agent_view, decrypt_v037_suite
from epistemic_loop.benchmark.v038_repro_suite import (
    V038_DEV_EXECUTED_RUN_IDS,
    V038_LINEAGE_POLICIES,
    V038_RUN_IDS,
    build_v038_suite,
    v038_lineage_assignment,
)

POLICY_CONTRACT = {
    "null_policy": {"minimum": 5, "maximum": 30, "provenance_required": True},
    "confidence_fields": ["p_structure_exists"],
}


def _build(tmp_path: Path, suite_id: str = "v038-qual-c01") -> tuple[bytes, Path, object]:
    key = Fernet.generate_key()
    prompt = tmp_path / "p1.md"
    prompt.write_text("challenge prompt\n")
    result = build_v038_suite(
        suite_id=suite_id,
        output_root=tmp_path / "public" / suite_id,
        truth_root=tmp_path / "truth",
        key=key,
        prompt_path=prompt,
        policy_contract=POLICY_CONTRACT,
        rows_per_context=600,
    )
    return key, prompt, result


def test_v038_suite_is_blind_p1_only_and_provenance_contracted(tmp_path: Path) -> None:
    key, prompt, result = _build(tmp_path)
    assert result.preflight_passed
    assert result.prompt_hashes == {"p1": hashlib.sha256(prompt.read_bytes()).hexdigest()}
    truth = decrypt_v037_suite(Path(result.encrypted_truth_path), key)
    assert len(truth.aliases) == len(V038_RUN_IDS) * 12 * 3
    seen_policies: list[str] = []
    for run_id in V038_RUN_IDS:
        root = tmp_path / "public" / "v038-qual-c01" / "agent_views" / run_id
        assert not audit_v037_agent_view(root)
        packet = json.loads((root / "agent_packet.json").read_text())
        assert packet["version"] == "0.3.8"
        assert packet["prompt_arm"] == "p1"
        assert packet["fresh_context_required"] is True
        assert packet["null_policy"]["provenance_required"] is True
        assert "null_provenance_fields" in packet
        seen_policies.append(packet["lineage_policy"])
    assert set(seen_policies) == set(V038_LINEAGE_POLICIES)
    assert all(seen_policies.count(policy) == 2 for policy in V038_LINEAGE_POLICIES)


def test_v038_lineage_rotation_differs_across_suites() -> None:
    first = [v038_lineage_assignment(1, index) for index in range(6)]
    second = [v038_lineage_assignment(2, index) for index in range(6)]
    assert first != second
    assert set(first) == set(second) == set(V038_LINEAGE_POLICIES)


def test_v038_suite_identity_is_immutable(tmp_path: Path) -> None:
    _build(tmp_path, "v038-dev-d01")
    key = Fernet.generate_key()
    prompt = tmp_path / "p1.md"
    with pytest.raises(FileExistsError, match="immutable"):
        build_v038_suite(
            suite_id="v038-dev-d01",
            output_root=tmp_path / "public" / "v038-dev-d01",
            truth_root=tmp_path / "truth",
            key=key,
            prompt_path=prompt,
            policy_contract=POLICY_CONTRACT,
            rows_per_context=600,
        )


def test_v038_rejects_unknown_suite_and_missing_provenance_contract(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    prompt = tmp_path / "p1.md"
    prompt.write_text("prompt\n")
    with pytest.raises(ValueError, match="preregistered"):
        build_v038_suite(
            suite_id="v037-repro-b01",
            output_root=tmp_path / "public" / "x",
            truth_root=tmp_path / "truth",
            key=key,
            prompt_path=prompt,
            policy_contract=POLICY_CONTRACT,
            rows_per_context=600,
        )
    with pytest.raises(ValueError, match="provenance"):
        build_v038_suite(
            suite_id="v038-qual-c02",
            output_root=tmp_path / "public" / "v038-qual-c02",
            truth_root=tmp_path / "truth",
            key=key,
            prompt_path=prompt,
            policy_contract={"null_policy": {}, "confidence_fields": []},
            rows_per_context=600,
        )


def test_v038_development_subset_is_balanced() -> None:
    executed = [run for runs in V038_DEV_EXECUTED_RUN_IDS.values() for run in runs]
    assert len(executed) == 6
    agents = [run.rsplit("-s", 1)[0] for run in executed]
    assert all(agents.count(agent) == 2 for agent in set(agents))
    for run in executed:
        assert run in V038_RUN_IDS
