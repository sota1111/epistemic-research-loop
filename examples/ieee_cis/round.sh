#!/usr/bin/env bash
# One research round, split at the two points where the proposing agent must answer.
#
#   round.sh <run-id> plan                      # write the experiment-design request, show state
#   round.sh <run-id> run <experiments.json> <size>   # propose, select, dispatch, import
#   round.sh <run-id> judge <belief.json>       # falsify, update belief, decide the phase
#
# Everything here is `erlctl`; the script only saves keystrokes and prints the parts of the state a
# proposer actually needs to see. No decision is made in this file.
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; [ -f .env ] && source .env; set +a

RUN="$1"; ACTION="$2"

case "$ACTION" in
plan)
  uv run erlctl experiments request --run-id "$RUN" >/dev/null
  uv run python - "$RUN" <<'PY'
import json, sys
from pathlib import Path
from epistemic_loop.controller.research_graph import ResearchController
from epistemic_loop.storage.repositories import ResearchRepository

run_id = sys.argv[1]
state = ResearchController(ResearchRepository(Path(".runs"), Path(".state/epistemic-loop.db"))).state(run_id)
print(json.dumps({
    "phase": state.phase.value,
    "loop_state": state.loop_state.value,
    "hypotheses": {h.id: {"type": h.type.value, "status": h.status.value,
                          "confidence": round(h.current_confidence, 3)} for h in state.hypotheses.values()},
    "open_candidates": [p.id for p in state.open_candidates()],
    "observations": {o.experiment_id: o.metrics for o in state.observations.values()},
    "falsification_history": state.falsification_digest(),
    "validation_reuse": state.validation_reuse(),
    "budget_used": state.usage.model_dump(mode="json"),
}, indent=1, ensure_ascii=False))
PY
  ;;
run)
  SOURCE="$3"; SIZE="${4:-1}"
  uv run erlctl experiments propose --run-id "$RUN" --from "$SOURCE" >/dev/null
  uv run erlctl experiments select --run-id "$RUN" --size "$SIZE" | uv run python -c "
import json,sys
d=json.load(sys.stdin)
print('SELECTED:', d['selected_experiment_ids'], '| phase:', d['phase'])
for k,v in sorted(d['utility_breakdown'].items(), key=lambda x: -(x[1]['total'] if x[1] else -9)):
    print(f\"  {k:14s} total={v['total']:+.4f} prag={v['pragmatic']:+.4f} epis={v['epistemic']:.3f} robu={v['robustness']:.3f} dive={v['diversity']:.2f} cost={v['cost']:.3f}\" if v else f'  {k:14s} GATED')
if d['rejected_reasons']: print('REJECTED:', json.dumps(d['rejected_reasons'], indent=1))
import pathlib; pathlib.Path('.state/selected.txt').write_text(''.join(f'{i}\n' for i in d['selected_experiment_ids']))
"
  # Dispatch every selected experiment first, then import every result. The state machine allows
  # `selecting -> executing -> parsing` once per round, so importing between two dispatches would
  # try to re-enter `executing` from `parsing`. This is the order the autonomous loop uses.
  # `|| [ -n "$EXP" ]` so a final line without a trailing newline is still processed.
  while read -r EXP || [ -n "$EXP" ]; do
    [ -z "$EXP" ] && continue
    echo "--- dispatch $EXP"
    uv run erlctl experiments dispatch --run-id "$RUN" --experiment-id "$EXP" | tail -8
  done < .state/selected.txt
  while read -r EXP || [ -n "$EXP" ]; do
    [ -z "$EXP" ] && continue
    echo "--- import $EXP"
    uv run erlctl experiments import-result --run-id "$RUN" --experiment-id "$EXP" | tail -12
  done < .state/selected.txt
  ;;
judge)
  for BELIEF in "${@:3}"; do
    uv run erlctl beliefs update --run-id "$RUN" --from "$BELIEF" | tail -7
  done
  uv run erlctl run advance --run-id "$RUN" | tail -12
  ;;
*) echo "unknown action: $ACTION" >&2; exit 2 ;;
esac
