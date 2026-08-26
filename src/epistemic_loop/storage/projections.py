from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from epistemic_loop.domain.events import EventEnvelope, EventType

SCHEMA = """
CREATE TABLE IF NOT EXISTS projected_events (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  UNIQUE(run_id, sequence)
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  competition_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  phase TEXT NOT NULL,
  status TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hypotheses (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence REAL NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hypotheses_run ON hypotheses(run_id);
CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  experiment_type TEXT NOT NULL,
  status TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_run ON experiments(run_id);
CREATE TABLE IF NOT EXISTS observations (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  experiment_id TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(run_id);
CREATE TABLE IF NOT EXISTS validation_worlds (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  split_type TEXT NOT NULL,
  posterior_probability REAL NOT NULL,
  status TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_validation_worlds_run ON validation_worlds(run_id);
CREATE TABLE IF NOT EXISTS qd_candidates (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  experiment_id TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_qd_candidates_run ON qd_candidates(run_id);
CREATE TABLE IF NOT EXISTS oof_artifacts (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oof_artifacts_run ON oof_artifacts(run_id);
CREATE TABLE IF NOT EXISTS oof_ensembles (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oof_ensembles_run ON oof_ensembles(run_id);
CREATE TABLE IF NOT EXISTS forecast_calibrations (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_or_category TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forecast_calibrations_run ON forecast_calibrations(run_id);
CREATE TABLE IF NOT EXISTS agent_resource_records (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_resource_records_run ON agent_resource_records(run_id);
CREATE TABLE IF NOT EXISTS experiment_retries (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  experiment_id TEXT NOT NULL,
  data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiment_retries_run ON experiment_retries(run_id);
CREATE TABLE IF NOT EXISTS violations (
  event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  data_json TEXT NOT NULL
);
"""


class SqliteProjection:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> SqliteProjection:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def apply(self, event: EventEnvelope) -> None:
        payload = event.payload
        payload_json = json.dumps(payload, sort_keys=True)
        with self.connection:
            inserted = self.connection.execute(
                "INSERT OR IGNORE INTO projected_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.run_id,
                    event.sequence,
                    event.event_type.value,
                    event.occurred_at.isoformat(),
                    payload_json,
                ),
            ).rowcount
            if not inserted:
                return
            if event.event_type == EventType.RUN_CREATED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        payload["id"],
                        payload["competition_id"],
                        payload["mode"],
                        payload["phase"],
                        payload["status"],
                        payload_json,
                    ),
                )
            elif event.event_type in {EventType.HYPOTHESIS_PROPOSED, EventType.HYPOTHESIS_REVISED}:
                self.connection.execute(
                    "INSERT OR REPLACE INTO hypotheses VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        payload["id"],
                        payload["run_id"],
                        payload["type"],
                        payload["status"],
                        payload["current_confidence"],
                        payload_json,
                    ),
                )
            elif event.event_type == EventType.BELIEF_UPDATED:
                row = self.connection.execute(
                    "SELECT data_json FROM hypotheses WHERE id = ?", (payload["hypothesis_id"],)
                ).fetchone()
                if row:
                    hypothesis = json.loads(row["data_json"])
                    hypothesis["current_confidence"] = payload["posterior_confidence"]
                    self.connection.execute(
                        "UPDATE hypotheses SET confidence = ?, data_json = ? WHERE id = ?",
                        (
                            payload["posterior_confidence"],
                            json.dumps(hypothesis, sort_keys=True),
                            payload["hypothesis_id"],
                        ),
                    )
            elif event.event_type == EventType.EXPERIMENT_PROPOSED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?)",
                    (
                        payload["id"],
                        payload["run_id"],
                        payload["experiment_type"],
                        payload["status"],
                        payload_json,
                    ),
                )
            elif event.event_type in {EventType.EXPERIMENT_SELECTED, EventType.EXPERIMENT_STARTED}:
                status = "selected" if event.event_type == EventType.EXPERIMENT_SELECTED else "running"
                for experiment_id in payload.get("selected_experiment_ids", [payload.get("experiment_id")]):
                    if experiment_id:
                        self.connection.execute(
                            "UPDATE experiments SET status = ? WHERE id = ?", (status, experiment_id)
                        )
            elif event.event_type in {EventType.EXPERIMENT_COMPLETED, EventType.EXPERIMENT_FAILED}:
                status = "completed" if event.event_type == EventType.EXPERIMENT_COMPLETED else "failed"
                self.connection.execute(
                    "UPDATE experiments SET status = ? WHERE id = ?",
                    (status, payload["experiment_id"]),
                )
            elif event.event_type == EventType.OBSERVATION_RECORDED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO observations VALUES (?, ?, ?, ?)",
                    (payload["id"], payload["run_id"], payload["experiment_id"], payload_json),
                )
            elif event.event_type == EventType.VALIDATION_WORLD_REGISTERED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO validation_worlds VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        payload["id"],
                        payload["run_id"],
                        payload["split_type"],
                        payload["posterior_probability"],
                        payload["status"],
                        payload_json,
                    ),
                )
            elif event.event_type == EventType.VALIDATION_POSTERIOR_UPDATED:
                for identifier, probability in payload["posterior"].items():
                    row = self.connection.execute(
                        "SELECT data_json FROM validation_worlds WHERE id = ?", (identifier,)
                    ).fetchone()
                    if row:
                        world = json.loads(row["data_json"])
                        world["posterior_probability"] = probability
                        world["evidence_ids"] = [*world.get("evidence_ids", []), payload["evidence_id"]]
                        world["version"] = int(world.get("version", 1)) + 1
                        self.connection.execute(
                            "UPDATE validation_worlds SET posterior_probability = ?, data_json = ? WHERE id = ?",
                            (probability, json.dumps(world, sort_keys=True), identifier),
                        )
            elif event.event_type == EventType.QD_CANDIDATE_EVALUATED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO qd_candidates VALUES (?, ?, ?, ?)",
                    (payload["id"], payload["run_id"], payload["experiment_id"], payload_json),
                )
            elif event.event_type == EventType.OOF_ARTIFACT_RECORDED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO oof_artifacts VALUES (?, ?, ?, ?)",
                    (payload["id"], payload["run_id"], payload["candidate_id"], payload_json),
                )
            elif event.event_type == EventType.OOF_ENSEMBLE_CREATED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO oof_ensembles VALUES (?, ?, ?)",
                    (payload["id"], payload["run_id"], payload_json),
                )
            elif event.event_type == EventType.FORECAST_CALIBRATION_RECORDED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO forecast_calibrations VALUES (?, ?, ?, ?)",
                    (payload["id"], payload["run_id"], payload["proposer_agent"], payload_json),
                )
            elif event.event_type == EventType.AGENT_RESOURCE_RECORDED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO agent_resource_records VALUES (?, ?, ?, ?)",
                    (payload["id"], payload["run_id"], payload["agent"], payload_json),
                )
            elif event.event_type == EventType.EXPERIMENT_RETRY_SCHEDULED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO experiment_retries VALUES (?, ?, ?, ?)",
                    (payload["id"], payload["run_id"], payload["experiment_id"], payload_json),
                )
            elif event.event_type == EventType.PHASE_CHANGED:
                self.connection.execute("UPDATE runs SET phase = ? WHERE id = ?", (payload["phase"], event.run_id))
            elif event.event_type == EventType.STATE_CHANGED:
                run_status = payload.get("run_status")
                if run_status:
                    self.connection.execute("UPDATE runs SET status = ? WHERE id = ?", (run_status, event.run_id))
            elif event.event_type == EventType.RUN_FINALIZED:
                self.connection.execute(
                    "UPDATE runs SET phase = 'finalized', status = 'completed' WHERE id = ?",
                    (event.run_id,),
                )
            elif event.event_type == EventType.VIOLATION_DETECTED:
                self.connection.execute(
                    "INSERT OR REPLACE INTO violations VALUES (?, ?, ?)",
                    (event.event_id, event.run_id, payload_json),
                )
                self.connection.execute("UPDATE runs SET status = 'blocked' WHERE id = ?", (event.run_id,))

    def rebuild(self, events: Iterable[EventEnvelope]) -> None:
        with self.connection:
            for table in (
                "projected_events",
                "runs",
                "hypotheses",
                "experiments",
                "observations",
                "validation_worlds",
                "qd_candidates",
                "oof_artifacts",
                "oof_ensembles",
                "forecast_calibrations",
                "agent_resource_records",
                "experiment_retries",
                "violations",
            ):
                self.connection.execute(f"DELETE FROM {table}")
        for event in events:
            self.apply(event)

    def one(self, table: str, identifier: str) -> dict[str, Any] | None:
        if table not in {
            "runs",
            "hypotheses",
            "experiments",
            "observations",
            "validation_worlds",
            "qd_candidates",
            "oof_artifacts",
            "oof_ensembles",
            "forecast_calibrations",
            "agent_resource_records",
            "experiment_retries",
        }:
            raise ValueError("unsupported table")
        row = self.connection.execute(f"SELECT data_json FROM {table} WHERE id = ?", (identifier,)).fetchone()
        return json.loads(row["data_json"]) if row else None

    def list_for_run(self, table: str, run_id: str) -> list[dict[str, Any]]:
        if table not in {
            "hypotheses",
            "experiments",
            "observations",
            "validation_worlds",
            "qd_candidates",
            "oof_artifacts",
            "oof_ensembles",
            "forecast_calibrations",
            "agent_resource_records",
            "experiment_retries",
            "violations",
        }:
            raise ValueError("unsupported table")
        rows = self.connection.execute(
            f"SELECT data_json FROM {table} WHERE run_id = ? ORDER BY rowid", (run_id,)
        ).fetchall()
        return [json.loads(row["data_json"]) for row in rows]
