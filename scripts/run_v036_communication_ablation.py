#!/usr/bin/env python3
"""Preregister or summarize v0.3.6 post-freeze communication ablations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_loop.controller.v036_real_agent import CommunicationMode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--independent-scorecard", type=Path)
    parser.add_argument("--mode-scorecard", action="append", default=[])
    parser.add_argument("--output", type=Path, default=Path("docs/v036_communication_ablation.json"))
    arguments = parser.parse_args()
    independent = _load(arguments.independent_scorecard) if arguments.independent_scorecard else None
    supplied: dict[str, dict[str, object]] = {}
    for value in arguments.mode_scorecard:
        mode, path = value.split("=", 1)
        supplied[mode] = _load(Path(path))
    modes: dict[str, object] = {}
    independent_effective = float(independent["population_effective_family_count"]) if independent is not None else None
    for mode in CommunicationMode:
        if mode.value == CommunicationMode.INDEPENDENT.value and independent is not None:
            result = independent
        else:
            result = supplied.get(mode.value)
        if result is None:
            modes[mode.value] = {"status": "unmeasured", "reason": "no frozen checkpoint branch output supplied"}
            continue
        effective = float(result["population_effective_family_count"])
        drr = effective / independent_effective if independent_effective else 1.0
        modes[mode.value] = {
            "status": "measured",
            "tsdr": result["population_union_tsdr"],
            "tsrr": result["population_union_tsrr"],
            "fspr": result["population_union_fspr"],
            "ustr": result["useful_structure_transfer_rate"],
            "eecr": result["exploration_to_exploitation_conversion"],
            "diversity_retention_ratio": drr,
            "adoption_gate": (
                drr >= 0.80
                and float(result["population_union_fspr"])
                <= float(independent["population_union_fspr"] if independent else result["population_union_fspr"])
            ),
        }
    output = {
        "version": "0.3.6",
        "phase": "post-freeze communication ablation",
        "agent_adoption_is_optional": True,
        "modes": modes,
        "claim_boundary": "unmeasured modes do not support a communication-effect conclusion",
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


if __name__ == "__main__":
    main()
