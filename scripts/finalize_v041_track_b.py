#!/usr/bin/env python3
"""Open Track B's truth manifest and score the locked runs against the P2 criteria.

P2 (docs/c_lite_v040_policy.md SS4.2, unchanged for Track B):
  1. locked translation's hidden transfer-region gain beats the controller's
     capacity-matched baseline (independently recomputed here from the agent's own
     submitted transfer predictions vs the true hidden labels -- not self-reported).
  2. structure-destruction probe: the promoted candidate's matched-negative twin must
     not also be promoted (in this suite design, criteria 2 and 3 coincide by
     construction -- a matched-negative pack IS the destruction probe for its twin).
  3. no real-data matched-negative pack promoted at all in that run (FSPR control).
  4. evidence bundle valid under the v037/v040 contract (checked at lock time already).

Reproducibility bar: >=2 of 4 runs of the same execution configuration must satisfy all
of P2 on at least one candidate pack, matching the synthetic-side P1 bar.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median

from epistemic_loop.benchmark.v037_repro_suite import V037AliasTruth, _auc, decrypt_v037_suite
from epistemic_loop.benchmark.v041_track_b_suite import V041_TRACKB_CONFIGS, V041_TRACKB_SUITE_IDS
from epistemic_loop.controller.v037_agent import V037Resolution
from epistemic_loop.controller.v040_agent import load_v040_submission

_PROMOTED = {
    V037Resolution.VALIDATED_ACTIONABLE_TRANSFERRED,
    V037Resolution.VALIDATED_ACTIONABLE_NOT_TRANSFERRED,
    V037Resolution.VALIDATED_NON_ACTIONABLE,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", default=V041_TRACKB_SUITE_IDS[-1], choices=V041_TRACKB_SUITE_IDS)
    parser.add_argument("--truth-manifest", type=Path, default=None)
    parser.add_argument("--key-file", type=Path, default=Path(".state/v040/controller.key"))
    parser.add_argument("--lock-file", type=Path, default=None)
    parser.add_argument("--submission-root", type=Path, default=Path(".runs/v041/agent_outputs"))
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()
    if arguments.truth_manifest is None:
        arguments.truth_manifest = Path(f".controller_truth/v041/{arguments.suite_id}.manifest.enc")
    if arguments.lock_file is None:
        arguments.lock_file = Path(f".runs/v041/{arguments.suite_id}_agent_runs.lock.json")
    if arguments.output is None:
        arguments.output = Path(f"docs/{arguments.suite_id.replace('-', '_')}_diagnostics.json")
    if not arguments.lock_file.exists():
        raise SystemExit("Track B outputs must be locked (scripts/lock_v041_track_b_runs.py) before opening truth")

    key = arguments.key_file.read_bytes().strip()
    truth = decrypt_v037_suite(arguments.truth_manifest, key)
    context_truth_by_key = {(item.canonical_pack_id, item.canonical_context_id): item for item in truth.context_truth}
    aliases_by_run: dict[str, list[V037AliasTruth]] = {}
    for alias in truth.aliases:
        aliases_by_run.setdefault(alias.run_id, []).append(alias)

    per_run: list[dict[str, object]] = []
    for run_id in V041_TRACKB_CONFIGS:
        submission_path = arguments.submission_root / arguments.suite_id / run_id / "agent_submission.json"
        loaded = load_v040_submission(submission_path)
        alias_by_pack_context = {(a.opaque_pack_id, a.opaque_context_id): a for a in aliases_by_run[run_id]}
        pack_records: list[dict[str, object]] = []
        for pack in loaded.core.packs:
            first_alias = next(a for (p, _c), a in alias_by_pack_context.items() if p == pack.opaque_pack_id)
            canonical_pack_id = first_alias.canonical_pack_id
            first_truth = next(t for (p, _c), t in context_truth_by_key.items() if p == canonical_pack_id)
            promoted = pack.resolution in _PROMOTED
            # Computed for every pack (candidate and matched-negative alike): the agent's own
            # submitted transfer-region AUC, independently recomputed from their predictions vs
            # the true hidden labels. For matched-negative packs this is the primary signal for
            # whether the v0.4.2 baseline-model fix actually destroyed learnable structure (it
            # should sit at chance, ~0.5) -- see docs/v042_trackb_matched_negative_fix_preregistration.json.
            agent_aucs: list[float] = []
            baseline_aucs: list[float] = []
            for context in pack.contexts:
                alias = alias_by_pack_context[(pack.opaque_pack_id, context.opaque_context_id)]
                context_truth = context_truth_by_key[(canonical_pack_id, alias.canonical_context_id)]
                translation = next(
                    item for item in context.translations if item.candidate_id == pack.selected_translation_id
                )
                agent_aucs.append(_auc(alias.transfer_targets_in_view_order, translation.transfer_predictions))
                baseline_aucs.append(_auc(context_truth.transfer_targets, context_truth.oracle_transfer_predictions))
            agent_median = median(agent_aucs)
            beats_baseline: bool | None = None
            baseline_median: float | None = None
            if first_truth.structure_present:
                baseline_median = median(baseline_aucs)
                beats_baseline = agent_median > baseline_median
            pack_records.append(
                {
                    "opaque_pack_id": pack.opaque_pack_id,
                    "canonical_pack_id": canonical_pack_id,
                    "family": first_truth.family,
                    "matched_pair": first_truth.matched_pair,
                    "structure_present_candidate": first_truth.structure_present,
                    "resolution": pack.resolution.value,
                    "promoted": promoted,
                    "agent_transfer_auc_median": agent_median,
                    "controller_baseline_transfer_auc_median": baseline_median,
                    "beats_capacity_matched_baseline": beats_baseline,
                }
            )
        negatives_promoted = [
            item["canonical_pack_id"]
            for item in pack_records
            if not item["structure_present_candidate"] and item["promoted"]
        ]
        fspr_clean = not negatives_promoted
        pair_ok: dict[str, bool] = {}
        by_pair: dict[str, list[dict[str, object]]] = {}
        for item in pack_records:
            by_pair.setdefault(str(item["matched_pair"]), []).append(item)
        qualifying_packs: list[str] = []
        for pair_id, items in by_pair.items():
            candidate = next(i for i in items if i["structure_present_candidate"])
            negative = next(i for i in items if not i["structure_present_candidate"])
            twin_not_promoted = not negative["promoted"]
            pair_ok[pair_id] = bool(
                candidate["promoted"]
                and candidate["beats_capacity_matched_baseline"]
                and twin_not_promoted
                and fspr_clean
            )
            if pair_ok[pair_id]:
                qualifying_packs.append(str(candidate["canonical_pack_id"]))
        run_p2_satisfied = bool(qualifying_packs)
        per_run.append(
            {
                "run_id": run_id,
                "config_id": V041_TRACKB_CONFIGS[run_id]["config_id"],
                "packs": pack_records,
                "matched_negatives_promoted": negatives_promoted,
                "fspr_clean": fspr_clean,
                "p2_satisfied": run_p2_satisfied,
                "p2_qualifying_packs": qualifying_packs,
            }
        )

    by_config: dict[str, list[dict[str, object]]] = {}
    for record in per_run:
        by_config.setdefault(str(record["config_id"]), []).append(record)
    config_summary = {
        config_id: {
            "runs": len(records),
            "p2_satisfied_runs": sum(1 for r in records if r["p2_satisfied"]),
            "reproducibility_met": sum(1 for r in records if r["p2_satisfied"]) >= 2,
        }
        for config_id, records in by_config.items()
    }
    payload = {
        "version": "0.4.2",
        "study": "track-b-ieee-cis-blind-bridge",
        "suite_id": arguments.suite_id,
        "per_run": per_run,
        "per_config": config_summary,
        "any_configuration_reproducibility_met": any(item["reproducibility_met"] for item in config_summary.values()),
    }
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"per_config": config_summary}, indent=2))


if __name__ == "__main__":
    main()
