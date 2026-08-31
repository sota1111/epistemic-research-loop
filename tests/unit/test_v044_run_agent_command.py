from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_runner() -> ModuleType:
    script_path = Path("scripts/run_v044_agent.py")
    spec = importlib.util.spec_from_file_location("run_v044_agent", script_path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def test_command_codex_branch_pins_model_and_reasoning_effort() -> None:
    runner = _load_runner()
    config = {"cli": "codex", "model": "gpt-5.6-sol", "prompt_arm": "p1", "reasoning_effort": "low"}
    command = runner._command(config, "do the thing", Path("/tmp/workdir"))
    assert command[0] == "codex"
    assert "-m" in command and command[command.index("-m") + 1] == "gpt-5.6-sol"
    assert "-c" in command
    assert command[command.index("-c") + 1] == 'model_reasoning_effort="low"'
    assert command[-1] == "do the thing"
    assert "-C" in command and command[command.index("-C") + 1] == "/tmp/workdir"


def test_command_claude_branch_has_no_reasoning_effort_flag() -> None:
    runner = _load_runner()
    config = {"cli": "claude", "model": "claude-opus-5", "prompt_arm": "p3"}
    command = runner._command(config, "do the thing", Path("/tmp/workdir"))
    assert command[0] == "claude"
    assert "--model" in command and command[command.index("--model") + 1] == "claude-opus-5"
    assert "--dangerously-skip-permissions" in command
    assert "-p" in command and command[command.index("-p") + 1] == "do the thing"
    assert "-c" not in command
    assert not any("model_reasoning_effort" in part for part in command)


def test_command_rejects_unknown_cli() -> None:
    runner = _load_runner()
    with pytest.raises(SystemExit):
        runner._command({"cli": "glm", "model": "x", "prompt_arm": "p1"}, "prompt", Path("/tmp/workdir"))


def test_all_configs_use_a_supported_cli() -> None:
    runner = _load_runner()
    for run_id, config in runner._ALL_CONFIGS.items():
        assert config["cli"] in {"codex", "claude"}, f"{run_id} has unsupported cli {config['cli']!r}"
        assert "model" in config, f"{run_id} is missing a model"


def test_v046_config_sets_are_registered_in_all_configs() -> None:
    from epistemic_loop.benchmark.v044_full_feature_pilot import V046_LOW_FB_CONFIGS, V046_LOW_NOFB_CONFIGS

    runner = _load_runner()
    for run_id in {**V046_LOW_NOFB_CONFIGS, **V046_LOW_FB_CONFIGS}:
        assert run_id in runner._ALL_CONFIGS
