from __future__ import annotations

import json
from pathlib import Path

from epistemic_loop.domain.events import EventEnvelope
from epistemic_loop.domain.models import (
    ExperimentProposal,
    ExperimentRequest,
    ExperimentResult,
    Hypothesis,
    Observation,
    ResearchBrief,
)

SCHEMAS = {
    "hypothesis.schema.json": Hypothesis,
    "experiment.schema.json": ExperimentProposal,
    "experiment_request.schema.json": ExperimentRequest,
    "experiment_result.schema.json": ExperimentResult,
    "observation.schema.json": Observation,
    "research_brief.schema.json": ResearchBrief,
    "event.schema.json": EventEnvelope,
}


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "schemas"
    root.mkdir(parents=True, exist_ok=True)
    for name, model in SCHEMAS.items():
        (root / name).write_text(
            json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
