#!/usr/bin/env python3
"""Build a frozen v0.3.6 blind structure suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from cryptography.fernet import Fernet

from epistemic_loop.benchmark.v036_blind_suite import (
    DEFAULT_AGENTS,
    build_blind_structure_suite,
)
from epistemic_loop.controller.v036_real_agent import submission_contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--suite-kind", choices=("development", "qualification"), default="qualification")
    parser.add_argument("--positive-packs", type=int, default=4)
    parser.add_argument("--negative-packs", type=int, default=4)
    parser.add_argument("--contexts-per-pack", type=int, default=3)
    parser.add_argument("--rows-per-context", type=int, default=1200)
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v036"))
    parser.add_argument("--truth-root", type=Path, default=Path(".controller_truth"))
    parser.add_argument("--key-file", type=Path, default=Path(".state/v036/controller.key"))
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()

    suite_root = arguments.output_root / arguments.suite_id
    if suite_root.exists() or (arguments.truth_root / f"{arguments.suite_id}.manifest.enc").exists():
        raise SystemExit("suite already exists; qualification suites are immutable and must receive a new suite id")
    arguments.key_file.parent.mkdir(parents=True, exist_ok=True)
    if arguments.key_file.exists():
        key = arguments.key_file.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        arguments.key_file.write_bytes(key + b"\n")
        os.chmod(arguments.key_file, 0o600)
    prompt_source = Path("prompts/generic_research_agent/v036.md")
    prompt_hash = hashlib.sha256(prompt_source.read_bytes()).hexdigest()
    result = build_blind_structure_suite(
        suite_id=arguments.suite_id,
        suite_kind=arguments.suite_kind,
        output_root=suite_root,
        truth_root=arguments.truth_root,
        key=key,
        prompt_hash=prompt_hash,
        agents=DEFAULT_AGENTS,
        positive_packs=arguments.positive_packs,
        negative_packs=arguments.negative_packs,
        contexts_per_pack=arguments.contexts_per_pack,
        rows_per_context=arguments.rows_per_context,
    )
    for agent in DEFAULT_AGENTS:
        target = suite_root / "agent_views" / agent
        shutil.copyfile(prompt_source, target / "v036_agent_prompt.md")
        (target / "v036_submission_contract.json").write_text(
            json.dumps(submission_contract(), indent=2, sort_keys=True) + "\n"
        )
    report = arguments.report or suite_root / "build_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
