#!/usr/bin/env python3
"""Execute one fresh-context v0.4.0 run through the configured CLI.

One invocation = one (suite, run-slot) pair = one fresh LLM context, where the run slot
maps to a preregistered execution configuration (CLI x model x prompt arm x reasoning
effort). Shared across every v0.4.0 study that reuses the grammar/pack-plan suite
machinery (generation-1 Track A, the codex sol reasoning-effort ablation, ...); the
configuration mapping is selected by suite id via ``_resolve_config``. Claude slots run
through `claude -p` exactly as in v0.3.8/9; codex slots run through `codex exec` with
`-s danger-full-access` (this container's bwrap dependency for `-s workspace-write` is
broken) and an explicitly pinned `-c model_reasoning_effort`. Contract repair feedback
(never truth) is bounded; claude repairs continue the conversation, codex repairs start a
fresh context over the same working directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from epistemic_loop.benchmark.v040_grammar_suite import (
    V040_GEN1_CONFIGS,
    V040_GEN1_SUITE_IDS,
    V040_SOL_ABLATION_CONFIGS,
    V040_SOL_ABLATION_SUITE_IDS,
)
from epistemic_loop.controller.v040_agent import load_v040_submission, validate_v040_submission

#: Each study (generation-1 Track A, the codex sol reasoning-effort ablation, ...) preregisters
#: its own suite ids and execution-configuration mapping; this runner is shared across studies
#: that reuse the same grammar/pack-plan machinery, so it selects the mapping by suite id.
_CONFIG_REGISTRY: tuple[tuple[tuple[str, ...], Mapping[str, Mapping[str, str]]], ...] = (
    (V040_GEN1_SUITE_IDS, V040_GEN1_CONFIGS),
    (V040_SOL_ABLATION_SUITE_IDS, V040_SOL_ABLATION_CONFIGS),
)


def _resolve_config(suite_id: str, run_id: str) -> Mapping[str, str]:
    for suite_ids, configs in _CONFIG_REGISTRY:
        if suite_id in suite_ids:
            config = configs.get(run_id)
            if config is None:
                raise SystemExit(f"run id {run_id!r} has no preregistered configuration for suite {suite_id!r}")
            return config
    raise SystemExit(f"suite id {suite_id!r} is not a preregistered v0.4.0 study suite")


RUNNER_INSTRUCTIONS = """# Operational rules for this research run

- Work ONLY inside this directory. Never read, list, or write files outside it. Never use the
  network. Never look for controller code, truth manifests, keys, or other agents' work.
- `agent_prompt.md` is the binding research prompt. `agent_packet.json` lists your data packs.
  `submission_contract.json` is the exact output schema.
- Write your final output to `agent_submission.json` in this directory with `version` `0.4.0`.
- Keep your analysis code in this directory (any layout). Use deterministic seeds.
- python3 is available. Prefer simple, capacity-matched models; the datasets are small
  (hundreds of rows per context file). Vectorize where possible and avoid long hyperparameter
  searches; the whole run should finish well within your session.
- Every executed null replicate must regenerate features and refit the model, and must be
  recorded in `null_summary.replicates` with: replicate_index, permutation_hash,
  preserved_statistics (name -> finite number), feature_manifest_hash, fold_plan_hash,
  model_fit_manifest_hash, oof_prediction_hash, gain. Hashes are lowercase sha256 hex digests
  computed over the corresponding artifacts you actually produced. The gain values must equal
  `replicate_gains` entry-by-entry.
- For every context of a pack with a terminal resolution, include `implication_provenance` in
  the context object: {statistic, held_out (must be true), null_reference_position in [0,1]
  (position of your held-out implication statistic within your own confounder-preserving null
  distribution), computation_hash}. Terminal resolutions must be consistent with these
  positions and with your implication strengths, as stated in the research prompt and contract.
- Your lineage policy is stated in `agent_packet.json` and is binding as described in the
  research prompt.
- Predictions for `.confirmation.json` and `.transfer.json` files must be aligned to the row
  order of those files and must come from models fit on research labels only.
"""

KICKOFF = (
    "You are executing a locked blind research protocol. Read agent_prompt.md, agent_packet.json, "
    "submission_contract.json, and RUNNER.md in the current directory. Then carry out the complete "
    "protocol for every pack in the packet and write agent_submission.json here. Work autonomously "
    "and stay strictly inside this directory."
)

CLAUDE_SETTINGS = {
    "permissions": {
        "deny": [
            "Read(//workspaces/**)",
            "Glob(//workspaces/**)",
            "Grep(//workspaces/**)",
            "Read(//home/*/.erl-controller/**)",
            "WebFetch",
            "WebSearch",
            "Bash(curl:*)",
            "Bash(wget:*)",
            "Bash(git:*)",
        ]
    }
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--suite-root", type=Path, default=Path(".runs/v040"))
    parser.add_argument("--output-root", type=Path, default=Path(".runs/v040/agent_outputs"))
    parser.add_argument("--workdir-root", type=Path, default=Path.home() / "erl-v040-runs")
    parser.add_argument("--timeout-seconds", type=float, default=10800)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=1000)
    arguments = parser.parse_args()

    config = _resolve_config(arguments.suite_id, arguments.run_id)
    view_root = arguments.suite_root / arguments.suite_id / "agent_views" / arguments.run_id
    if not (view_root / "agent_packet.json").exists():
        raise SystemExit(f"missing locked agent view: {view_root}")
    output_dir = arguments.output_root / arguments.suite_id / arguments.run_id
    if (output_dir / "agent_submission.json").exists():
        raise SystemExit(f"output already recorded for {arguments.suite_id}/{arguments.run_id}")

    workdir = arguments.workdir_root / arguments.suite_id / arguments.run_id
    if not workdir.exists():
        workdir.mkdir(parents=True)
        for item in view_root.iterdir():
            if item.is_dir():
                shutil.copytree(item, workdir / item.name)
            else:
                shutil.copy2(item, workdir / item.name)
        (workdir / "RUNNER.md").write_text(RUNNER_INSTRUCTIONS)
        claude_dir = workdir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps(CLAUDE_SETTINGS, indent=2) + "\n")

    packet = json.loads((view_root / "agent_packet.json").read_text())
    attempts: list[dict[str, object]] = []
    submission_path = workdir / "agent_submission.json"
    errors: tuple[str, ...] = ()
    for attempt in range(1, arguments.max_attempts + 1):
        prompt = KICKOFF if attempt == 1 else _repair_prompt(errors)
        command = _command(config, prompt, attempt, arguments, workdir)
        transcript = workdir / f"transcript-attempt-{attempt}.stream.jsonl"
        started = time.time()
        with transcript.open("w") as sink:
            completed = subprocess.run(
                command,
                cwd=workdir,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.PIPE,
                text=True,
                timeout=arguments.timeout_seconds,
                env=_environment(),
                check=False,
            )
        errors = _validate(submission_path, packet)
        attempts.append(
            {
                "attempt": attempt,
                "returncode": completed.returncode,
                "seconds": round(time.time() - started, 1),
                "stderr_tail": (completed.stderr or "")[-2000:],
                "contract_errors_after_attempt": list(errors)[:30],
            }
        )
        if not errors:
            break

    meta = {
        "suite_id": arguments.suite_id,
        "run_id": arguments.run_id,
        "config": dict(config),
        "fresh_context": True,
        "attempts": attempts,
        "contract_valid": not errors,
        "contract_errors": list(errors)[:50],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    for transcript in sorted(workdir.glob("transcript-attempt-*.stream.jsonl")):
        shutil.copy2(transcript, output_dir / transcript.name)
    if errors:
        print(json.dumps({"ok": False, "errors": list(errors)[:20]}, indent=2))
        raise SystemExit(1)
    shutil.copy2(submission_path, output_dir / "agent_submission.json")
    print(json.dumps({"ok": True, "output": str(output_dir / "agent_submission.json"), "meta": meta}, indent=2))


def _command(
    config: Mapping[str, str],
    prompt: str,
    attempt: int,
    arguments: argparse.Namespace,
    workdir: Path,
) -> list[str]:
    if config["cli"] == "claude":
        command = ["claude"]
        if attempt > 1:
            command.append("--continue")
        command += [
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--model",
            config["model"],
            "--max-turns",
            str(arguments.max_turns),
        ]
        return command
    if config["cli"] == "codex":
        # Repairs start a fresh context over the same working directory; codex has no
        # equivalent of claude's --continue that we treat as validated for this harness.
        # model_reasoning_effort is ALWAYS pinned explicitly here rather than left to
        # ~/.codex/config.toml's ambient default: that file is shared across unrelated
        # projects on this host and was observed to change mid-batch during generation 1
        # (xhigh -> low), silently altering one accepted run's execution condition. See
        # docs/v040_gen1_preregistration.json post_registration_deviations.
        effort = config.get("reasoning_effort", "xhigh")
        # -s workspace-write depends on bwrap (Linux user namespaces), which this
        # container blocks unconditionally (verified: unshare returns EPERM even as
        # root). That intermittently blocked real computation throughout generation 1
        # (confirmed in accepted-attempt transcripts, not just the terminal g04/sol
        # failure), confounding codex's measured discovery rate with an infrastructure
        # defect. danger-full-access skips codex's own OS sandbox entirely; isolation
        # then comes only from the workdir-copy + RUNNER.md instructions + transcript
        # audit, matching the isolation this harness already relies on for claude
        # (--dangerously-skip-permissions) and glm/zai (no OS sandbox at all).
        return [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--json",
            "-m",
            config["model"],
            "-c",
            f'model_reasoning_effort="{effort}"',
            "-s",
            "danger-full-access",
            "-C",
            str(workdir),
            prompt,
        ]
    if config["cli"] == "glm":
        # The zai CLI (wrapped by /home/vscode/.local/bin/glm, which sources GLM_API_KEY from
        # the project .env and sets ZAI_BASE_URL/ZAI_MODEL) has no OS-level sandbox at all
        # (verified by reading its tool implementations: text-editor.js resolves paths with no
        # confinement check, bash.js only sets cwd). Isolation here is workdir-copy +
        # RUNNER.md instructions + transcript audit only -- the same posture already used for
        # codex's danger-full-access. -d scopes the CLI's own notion of a working directory;
        # -p is headless mode, which auto-approves every tool call (no interactive gate to
        # bypass). Repairs are fresh -p invocations over the same workdir, matching codex's
        # fresh-context repair semantics (no verified session-continuation flag for -p mode).
        return [
            "/home/vscode/.local/bin/glm",
            "-d",
            str(workdir),
            "-m",
            config["model"],
            "-p",
            prompt,
        ]
    raise SystemExit(f"unknown cli {config['cli']!r}")


def _validate(submission_path: Path, packet: dict[str, object]) -> tuple[str, ...]:
    if not submission_path.exists():
        return ("agent_submission.json was not produced",)
    try:
        loaded = load_v040_submission(submission_path)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return (f"submission failed to parse: {error}",)
    return validate_v040_submission(loaded, packet).errors


def _repair_prompt(errors: tuple[str, ...]) -> str:
    listed = "\n".join(f"- {item}" for item in errors[:25])
    return (
        "Your agent_submission.json did not satisfy the locked contract. This is contract "
        "validation feedback only; it contains no information about the data. Fix exactly these "
        f"issues and rewrite agent_submission.json:\n{listed}"
    )


def _environment() -> dict[str, str]:
    # Each CLI authenticates itself; never forward provider API keys into the agent process.
    keep = ("PATH", "HOME", "LANG", "TERM", "SHELL")
    environment = {name: os.environ[name] for name in keep if name in os.environ}
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        environment[name] = "2"
    return environment


if __name__ == "__main__":
    main()
