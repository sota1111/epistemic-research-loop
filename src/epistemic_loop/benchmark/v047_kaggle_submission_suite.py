"""v0.4.7: real Kaggle test-set materialization for the late-submission verification round.

Every study through v0.4.6 scored agents against a locally sealed holdout carved out of
train.csv, never the real Kaggle test set (see docs/c_lite_v047_policy.md SS0 -- a
deliberate choice through v0.4.6 in favor of pseudo-scoring). This module adds the one new
mechanism v0.4.7 needs: materializing the REAL competition test.csv (506,691 rows for
IEEE-CIS, 200,000 for Santander) as an agent-visible, blindness-preserving view, so an
agent can produce predictions that a human can actually submit to Kaggle afterward.

Blindness is preserved the same way v0.4.4's research/confirmation/transfer regions are:
the real test set's feature columns get the SAME per-run HMAC-salted names
(``v044_full_feature_pilot._visible_column_map_generic``, reused verbatim so an agent's
own feature-engineering code -- which references those exact hashed names -- applies
unchanged) as that run's research/confirmation/transfer files, and the real row identifier
(``TransactionID``/``ID_code``) is replaced by an opaque ``row_id`` in a distinct numeric
range that never collides with the small-sample regions' row_ids. The row_id -> real id
mapping is written to a Controller-only file, never placed in the agent's own workdir.

This module does not build the small research/confirmation/(local sealed)transfer regions
itself -- ``build_v044_suite`` already does that correctly and is reused unchanged
(docs/c_lite_v047_policy.md SS1). ``materialize_real_test_view`` is called once per run_id,
after ``build_v044_suite``, to add the one new file (``real_test.csv``) each run's view
needs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from epistemic_loop.benchmark.v037_repro_suite import _write_json
from epistemic_loop.benchmark.v042_multi_competition_suite import CompetitionSpec
from epistemic_loop.benchmark.v044_full_feature_pilot import (
    V044_MASTER_SEED,
    V044SuiteBuildResult,
    _visible_column_map_generic,
    build_v044_suite,
    select_all_generic_columns,
)

#: Real Kaggle test files -- same schema as each CompetitionSpec's train data_path minus
#: the target column (verified column-for-column equal, docs/c_lite_v047_policy.md SS1).
V047_TEST_DATA_PATHS: dict[str, Path] = {
    "ieee-cis": Path(".data/ieee-cis/test_transaction.csv"),
    "santander-customer-transaction-prediction": Path(".data/santander-customer-transaction-prediction/test.csv"),
}

#: Research/confirmation/transfer row_ids run 0-7999 (v044_full_feature_pilot's
#: V044_RESEARCH_ROWS + V044_CONFIRMATION_ROWS + V044_TRANSFER_ROWS). Real test row_ids
#: start far above that so the two ranges can never collide or be confused.
V047_REAL_TEST_ROW_ID_OFFSET = 1_000_000

#: Generation-1 (exploration) population, docs/c_lite_v047_policy.md SS2.1 -- revised
#: after the user asked for a larger population that includes opus and serves both
#: "evolution" (exploitation, SS2.2/SS2.3) and exploration. Sol: low/xhigh in equal number
#: (4/4), P1/P3 in equal number (4/4), n=2 replicates/cell (don't trust a single
#: replicate's novelty, docs/c_lite_v043_policy.md). Opus: P1/P3 equal (2/2), n=2
#: replicates -- no reasoning-effort dial exists for claude in this harness. run_ids carry
#: no "-s{seed}" suffix (unlike earlier rounds): there is a fixed replicate count per cell
#: per invocation, and the suite_id (embedding a date/run label) already provides the
#: row-sample/salt variation a seed would otherwise encode.
V047_CANDIDATE_CONFIGS: Mapping[str, Mapping[str, str]] = {
    **{
        f"agent-01-r{rep}": {
            "config_id": "F7-low-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "low",
        }
        for rep in (1, 2)
    },
    **{
        f"agent-02-r{rep}": {
            "config_id": "F7-low-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "low",
        }
        for rep in (1, 2)
    },
    **{
        f"agent-03-r{rep}": {
            "config_id": "F7-xhigh-P1",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p1",
            "reasoning_effort": "xhigh",
        }
        for rep in (1, 2)
    },
    **{
        f"agent-04-r{rep}": {
            "config_id": "F7-xhigh-P3",
            "cli": "codex",
            "model": "gpt-5.6-sol",
            "prompt_arm": "p3",
            "reasoning_effort": "xhigh",
        }
        for rep in (1, 2)
    },
    **{
        f"agent-05-r{rep}": {
            "config_id": "F7-opus-P1",
            "cli": "claude",
            "model": "claude-opus-5",
            "prompt_arm": "p1",
        }
        for rep in (1, 2)
    },
    **{
        f"agent-06-r{rep}": {
            "config_id": "F7-opus-P3",
            "cli": "claude",
            "model": "claude-opus-5",
            "prompt_arm": "p3",
        }
        for rep in (1, 2)
    },
}
V047_CANDIDATE_RUN_IDS = tuple(V047_CANDIDATE_CONFIGS)


@dataclass(frozen=True)
class V047RealTestMaterializeResult:
    run_id: str
    real_test_path: str
    id_map_path: str
    row_count: int


@dataclass(frozen=True)
class V047SuiteBuildResult:
    suite_build: V044SuiteBuildResult
    real_test_results: tuple[V047RealTestMaterializeResult, ...]


def materialize_real_test_view(
    spec: CompetitionSpec,
    *,
    key: bytes,
    suite_id: str,
    run_id: str,
    columns: Sequence[str],
    view_root: Path,
    id_map_root: Path,
) -> V047RealTestMaterializeResult:
    """Write ``real_test.csv`` into ``view_root`` and the id_map into ``id_map_root``.

    ``columns`` must be the exact same canonical column list (and ``key``/``suite_id``/
    ``run_id``) already used to build that run's research/confirmation/transfer views, so
    the salted names match and the agent's existing code applies unchanged.
    """

    test_path = V047_TEST_DATA_PATHS[spec.competition_id]
    if not test_path.exists():
        raise FileNotFoundError(f"real test data not found at {test_path}")
    (id_column,) = spec.id_columns
    usecols = sorted(set(columns) | {id_column})
    frame = pd.read_csv(test_path, usecols=usecols).reset_index(drop=True)
    row_ids = frame.index.to_numpy() + V047_REAL_TEST_ROW_ID_OFFSET

    id_map_root.mkdir(parents=True, exist_ok=True)
    id_map_path = id_map_root / f"{suite_id}_{run_id}_id_map.json"
    _write_json(
        id_map_path,
        {
            "id_column": id_column,
            "map": dict(zip((str(value) for value in row_ids), frame[id_column].tolist(), strict=True)),
        },
    )
    id_map_path.chmod(0o600)

    column_map = _visible_column_map_generic(key, suite_id, run_id, columns)
    view = frame[list(columns)].rename(columns=column_map)
    view.insert(0, "row_id", row_ids)
    view_root.mkdir(parents=True, exist_ok=True)
    real_test_path = view_root / "real_test.csv"
    view.to_csv(real_test_path, index=False)

    return V047RealTestMaterializeResult(
        run_id=run_id,
        real_test_path=str(real_test_path),
        id_map_path=str(id_map_path),
        row_count=len(view),
    )


def build_v047_suite(
    spec: CompetitionSpec,
    *,
    output_root: Path,
    truth_root: Path,
    real_test_id_map_root: Path,
    key: bytes,
    scorer_key: bytes,
    prompt_paths: Mapping[str, Path],
    suite_id: str,
    configs: Mapping[str, Mapping[str, str]] = V047_CANDIDATE_CONFIGS,
    run_ids: Sequence[str] = V047_CANDIDATE_RUN_IDS,
    master_seed: int = V044_MASTER_SEED,
) -> V047SuiteBuildResult:
    """Build the v0.4.4 research/confirmation/(local sealed)transfer views unchanged
    (``build_v044_suite``), then add ``real_test.csv`` to each run's view -- the one new
    file v0.4.7 needs (docs/c_lite_v047_policy.md SS1/SS5).
    """

    suite_build = build_v044_suite(
        spec,
        output_root=output_root,
        truth_root=truth_root,
        key=key,
        scorer_key=scorer_key,
        prompt_paths=prompt_paths,
        suite_id=suite_id,
        configs=configs,
        run_ids=run_ids,
        master_seed=master_seed,
    )

    columns = select_all_generic_columns(spec)
    real_test_results = tuple(
        materialize_real_test_view(
            spec,
            key=key,
            suite_id=suite_id,
            run_id=run.run_id,
            columns=columns,
            view_root=Path(run.view_root),
            id_map_root=real_test_id_map_root,
        )
        for run in suite_build.runs
    )

    return V047SuiteBuildResult(suite_build=suite_build, real_test_results=real_test_results)
