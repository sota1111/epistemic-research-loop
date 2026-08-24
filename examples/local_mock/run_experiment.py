from __future__ import annotations

import json
import os
from pathlib import Path

output = Path(os.environ["ERL_OUTPUT_DIR"])
output.mkdir(parents=True, exist_ok=True)
(output / "metrics.json").write_text(json.dumps({"score": 0.75}), encoding="utf-8")
(output / "fold_metrics.json").write_text(json.dumps({"folds": [0.74, 0.76]}), encoding="utf-8")
(output / "predictions.parquet").write_bytes(b"mock-predictions")
(output / "run_manifest.json").write_text(json.dumps({"mock": True}), encoding="utf-8")
