from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v037_repro_suite import (
    V037_RUN_IDS,
    audit_v037_agent_view,
    build_v037_suite,
    decrypt_v037_suite,
)


def test_v037_suite_is_blind_identifiable_and_has_two_hidden_regions(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    p0 = tmp_path / "p0.md"
    p1 = tmp_path / "p1.md"
    p0.write_text("baseline prompt\n")
    p1.write_text("challenge prompt\n")
    result = build_v037_suite(
        suite_id="v037-repro-b01",
        suite_index=1,
        output_root=tmp_path / "public",
        truth_root=tmp_path / "truth",
        key=key,
        prompt_paths={"p0": p0, "p1": p1},
        policy_contract={
            "null_policy": {"minimum": 5, "maximum": 30},
            "confidence_fields": ["p_structure_exists"],
        },
        rows_per_context=600,
    )

    assert result.preflight_passed
    assert len(result.preflight) == 12
    assert {item.ladder_level for item in result.preflight if item.structure_present} >= {1, 2, 3, 4}
    truth = decrypt_v037_suite(Path(result.encrypted_truth_path), key)
    assert len(truth.aliases) == len(V037_RUN_IDS) * 12 * 3
    for run_id in V037_RUN_IDS:
        root = tmp_path / "public" / "agent_views" / run_id
        assert not audit_v037_agent_view(root)
        packet = json.loads((root / "agent_packet.json").read_text())
        assert len(packet["packs"]) == 12
        context = packet["packs"][0]["contexts"][0]
        assert context["research_rows"] == 360
        assert context["confirmation_rows"] == 120
        assert context["transfer_rows"] == 120


def test_v037_suite_identity_is_immutable(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("prompt\n")
    arguments = {
        "suite_id": "v037-repro-b01",
        "suite_index": 1,
        "output_root": tmp_path / "public",
        "truth_root": tmp_path / "truth",
        "key": key,
        "prompt_paths": {"p0": prompt, "p1": prompt},
        "policy_contract": {"null_policy": {}, "confidence_fields": []},
        "rows_per_context": 600,
    }
    build_v037_suite(**arguments)  # type: ignore[arg-type]
    try:
        build_v037_suite(**arguments)  # type: ignore[arg-type]
    except FileExistsError as error:
        assert "immutable" in str(error)
    else:
        raise AssertionError("suite identity was overwritten")
