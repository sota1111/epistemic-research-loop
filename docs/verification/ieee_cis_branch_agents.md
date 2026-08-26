# IEEE-CIS branch-isolated agent verification

Date: 2026-08-25 UTC

## Scope

Three independent System C processes received the same clean IEEE-CIS initial state, budget,
competition package, source policy, and final-selection rule. Each process used its own neutral Git
branch, worktree, event log, result directory, and random seed. The topology is deliberately
branch-per-agent: it verifies isolated parallel agents, not multiple role-scoped proposers appending
to one shared Run.

The competition repository is `/workspaces/kaggle-ieee-cis-fraud-detection`. The common initial
branch is `initial/ieee-cis-state` at `ac3b46975e5da64570fb79d6e1141bc5c7525d0f`. It descends from
the pre-experiment solver commit and adds only the official/local competition facts and executable
interface; no earlier result directories or experiment-specific modules are present.

## Branches and selected approaches

| Branch | Head | Run | Selected approach | Result |
| --- | --- | --- | --- | --- |
| `agents/workstream-01` | `e73eee0` | `ieee-cis-workstream-01` | adversarial validation with `time_aware` representation; test whether separation remains after time recoding | AUC `0.9253929` |
| `agents/workstream-02` | `55b34dd` | `ieee-cis-workstream-02` | per-column univariate target AUC scan focused on identity coverage/missingness | max AUC `0.7551651`, 432 features |
| `agents/workstream-03` | `b225d38` | `ieee-cis-workstream-03` | adversarial validation with raw features; attribute separation to temporal covariates | AUC `0.9243440` |

All three experiments completed. Their semantic signatures hash experiment type, QD descriptors,
split strategy, and executable command. The signatures were respectively:

- `c54803834636309fd7328a32e52ec9e0837a62bd14d03d1ffc25a544690a68d7`
- `c3b5b611db1bfe8a187f96fef857065a12292947a3bcf8d6b193f6bda0c86892`
- `eee42441ac2a37b7cdd557575399e06f55e3886e06e9ac30e6cd78c86c74fb22`

Thus the selected designs are pairwise distinct. Workstreams 01 and 03 both investigate
train/test separability, but select different representations, hypotheses, descriptors, and
commands; workstream 02 selects a different diagnostic family entirely.

Each branch commits `research/selected_experiment.json`, which binds the branch to the selected
event, descriptors, command, result, common initial commit, and final event-log hash.

## Mechanical verification

```bash
uv run python scripts/verify_branch_agent_diversity.py \
  --repository /workspaces/kaggle-ieee-cis-fraud-detection \
  --initial-commit ac3b46975e5da64570fb79d6e1141bc5c7525d0f \
  --agent ieee-cis-workstream-01=agents/workstream-01 \
  --agent ieee-cis-workstream-02=agents/workstream-02 \
  --agent ieee-cis-workstream-03=agents/workstream-03
```

The verifier passed all six checks: at least two agents, neutral branch names, common initial-state
ancestry, completed selections, branch-record/event-log equality, and pairwise-distinct semantic
signatures.

## Defects found by this run

The live parallel run exposed two audit defects that single-run tests did not:

1. CLI transcripts shared filenames and could overwrite one another. Transcript paths are now
   namespaced by Run ID.
2. `RunCreated.base_commit_sha` described the orchestration repository even when the executor ran a
   separate competition worktree. Initialization now records the executor workspace's Git HEAD.

## Limits of the result

This verifies independent branch execution and different selected research approaches after one
System C cycle. It does not establish that the three branches have produced complete, competitive
Kaggle submission pipelines, that one approach is superior, or that native role-scoped agents can
append proposals to one shared Run. The current topology uses three isolated Runs because the
single-Run controller accepts one proposal batch per planning transition.
