#!/usr/bin/env python3
"""Read the fitted world model and print what it predicts for one context.

The world model is a distribution over "was this research state decisive here", conditioned on
three structural attributes of the competition -- not a target vector and not a checklist
(`docs/world_model/coding_rules.md`). This is the only supported way to ask it a question.

    uv run python scripts/predict_world_model.py --temporal 0 --entity 1 --decomposable 1

`--context-of` names a competition already in the corpus and uses its context instead.

**Controller-owned.** The output must not be pasted into a prompt, a contract, or any file an agent
can read: a world model handed to the agents being measured stops measuring them
(`docs/world_model/coding_rules.md` §8).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PRIMARY = ROOT / "docs" / "world_model" / "world_model.json"
TWO_PART = ROOT / "docs" / "world_model" / "world_model_counterexample.json"
CODING = ROOT / "docs" / "world_model" / "corpus_coding.json"

STATE_NAMES = {
    "VF": "Validation Fidelity",
    "DGP": "DGP Understanding",
    "DSU": "Distribution Shift Understanding",
    "ETI": "Entity & Temporal Integrity",
    "DLQ": "Data / Label Quality Understanding",
    "EU": "Error Understanding",
    "HC": "Hypothesis Coverage",
    "HCAL": "Hypothesis Calibration",
    "FC": "Falsification Coverage",
    "RMC": "Representation / Model Coverage",
    "SED": "Solution / Error Diversity",
    "ROB": "Robustness",
    "PB": "Performance Belief",
}


def _cell(temporal: int, entity: int, decomposable: int) -> str:
    return f"{temporal},{entity},{decomposable}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temporal", type=int, choices=(0, 1))
    parser.add_argument("--entity", type=int, choices=(0, 1))
    parser.add_argument("--decomposable", type=int, choices=(0, 1))
    parser.add_argument("--context-of", help="use the context of this corpus competition instead")
    parser.add_argument("--label", default="", help="name for the competition being predicted")
    parser.add_argument("--out", type=Path, help="write the prediction as JSON here")
    arguments = parser.parse_args()

    if arguments.context_of:
        corpus = json.loads(CODING.read_text(encoding="utf-8"))
        match = next((item for item in corpus["competitions"] if item["name"] == arguments.context_of), None)
        if match is None:
            raise SystemExit(f"not in the corpus: {arguments.context_of}")
        context = match["ctx"]
    else:
        if None in (arguments.temporal, arguments.entity, arguments.decomposable):
            raise SystemExit("give --temporal, --entity and --decomposable, or --context-of")
        context = {
            "temporal": arguments.temporal,
            "entity": arguments.entity,
            "decomposable": arguments.decomposable,
        }
    key = _cell(context["temporal"], context["entity"], context["decomposable"])

    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    two_part = json.loads(TWO_PART.read_text(encoding="utf-8"))
    corpus = json.loads(CODING.read_text(encoding="utf-8"))
    states: list[str] = corpus["_states"]
    neighbours = [item["name"] for item in corpus["competitions"] if _cell(**item["ctx"]) == key]

    # A context cell the corpus never observed falls back to the global prior -- which is the
    # checklist. When that happens the "context-conditioned" prediction *is* the checklist, and
    # saying so is the whole point: the corpus does not span this competition's context.
    cell_observed = bool(neighbours)

    rows: list[dict[str, Any]] = []
    for state in states:
        conditional = primary["conditional"][state].get(key, primary["global_prior"][state])
        checklist_prior = primary["global_prior"][state]
        distribution = two_part["states"][state]["cells"].get(key, two_part["states"][state]["global"])
        observed = two_part["states"][state]["observed"]
        rows.append(
            {
                "state": state,
                "name": STATE_NAMES[state],
                # The point prediction the pre-registered comparison in results.md was scored on.
                "context_prediction": max(conditional, key=lambda value: conditional[value]),
                "checklist_prediction": max(checklist_prior, key=lambda value: checklist_prior[value]),
                "p_decisive": round(float(conditional.get("1", 0.0)), 4),
                "p_mentioned": round(float(distribution["p_mentioned"]), 4),
                # Direction: given it mattered at all, how often it mattered the other way round.
                "p_minus_given_mentioned": round(float(distribution["p_minus"]), 4),
                "p_counterexample": round(
                    float(distribution.get("p_counterexample", distribution["p_mentioned"] * distribution["p_minus"])),
                    4,
                ),
                "corpus_observations": observed,
            }
        )

    payload = {
        "label": arguments.label or key,
        "context": context,
        "cell": key,
        "cell_observed_in_corpus": cell_observed,
        "corpus_competitions_in_this_cell": neighbours,
        "sources": {
            "primary": str(PRIMARY.relative_to(ROOT)),
            "two_part": str(TWO_PART.relative_to(ROOT)),
            "rules": "docs/world_model/coding_rules.md",
        },
        "caveats": [
            "single coder; inter-coder agreement UNMEASURED",
            *(
                []
                if cell_observed
                else [
                    "THIS CONTEXT CELL IS NOT IN THE CORPUS: every number below falls back to the "
                    "global prior, so the context-conditioned prediction is identical to the checklist"
                ]
            ),
            "all 38 corpus competitions submit predictions; an algorithm submission is out of class",
            "HCAL and FC have zero corpus observations -- their numbers are prior, not evidence",
            "the point prediction cannot emit -1; read p_counterexample instead",
        ],
        "states": rows,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if arguments.out:
        arguments.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
