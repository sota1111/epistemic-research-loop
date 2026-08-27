# IEEE-CIS v0.3.4 Outcome-only Implementation Verification

Date: 2026-08-27 UTC  
Branch: `system/c-lite-v0.3.4`  
Scope: Infrastructure and policy preflight; no live 36-run or Hidden query

## Result

v0.3.4のOutcome-only比較基盤を実装した。v0.3.3のcgroup/Hard Budget比較は削除せず別モジュールに保持し、
v0.3.4ではCPU、Memory、Thread、Wall-clock、Token、CostをPlan admission、Utility、Final Selector、
Acceptanceから除外した。

Preflightでは次を確認した。

| Check | Result |
| --- | --- |
| B/B+/C × 12 paired seeds | 36 requests generated |
| Agents/Cycles | 3 × 3 per request |
| Immutable base | `ac3b46975e5da64570fb79d6e1141bc5c7525d0f` |
| Resource limits | all `null` |
| Resource in selection/acceptance | `false` |
| GVC-IEEE-001 | registered |
| Shuffled OOF final eligibility | rejected |
| Shuffled OOF diagnostic eligibility | allowed |
| Strict-forward final eligibility | allowed |
| Common cross-fit invariant | 3 horizons, 7-day gap, 3 seeds, past-only |
| Cycle artifacts | B=9、B+=11、C=16 required outputs |
| Final candidate artifacts | 11 required outputs |
| Semantic independent replication | classified and credited |
| All-output lock | requires 36 outputs and 9 decisions/run |
| Partial Hidden batch | rejected by contract |

## Implemented boundaries

`OutcomeOnlyPlan`は12 SeedをB→B+→Cのround-robinでpairingし、同一Base、Dataset、Research Row Set、Fold
Plan、Generic Prompt、External Research Opportunity、Hidden Evaluator、Acceptance、Validation Constraintを
Hash固定する。B/B+/CのPolicy Hashは異なることを要求する。

`SequentialOutcomeOnlyRunner`はHeavy Jobを相互干渉防止のため逐次化できるが、Resource Reservation、
Hard Budget、cgroup admission、早期停止を行わない。Resource Observationはdiagnostic-only型であり、
Selection/Acceptance使用フラグが立つとRunを失敗させる。

各Runは3 Agent×3 Cycleの9 `DecisionLock`、Common Fold Hash、Sealed Prediction Hash、Submission Hashを含む
1件の`V034RunOutputLock`を生成する。全36件が揃わない場合、`V034SealedOutcomeBatch`は作られず、Hidden
Evaluation Readyにならない。

## Decision and outcome audit

Decision AuditはParent/ChallengerについてDecision Sign Accuracy、False Rejection、False Adoption、Decision
Regretを算出する。Outcome集計はArmごとに次を保存する。

* Local/Sealed/Private AUCとCV→Sealed/Private Spearman
* Private Mean/Median/Win Rate
* Run Selection Regret
* Nested/Hidden Ensemble Gain
* Validated/False-promoted StructureとFalse Promotion Rate
* Global Validation Constraint発見数
* Independent ReplicationとRedundant Duplication率
* Artifact Completion / Valid Submission率

Primary Pairingは`C-B`、`C-B+`、Secondary Pairingは`B+-B`。Mean/Median、10,000回Paired Bootstrap 95%
CI、Positive Rate、Exact Sign Test、Worst/Best Seedを実装した。結果分類はFull C、B+ Sufficient、Strong B
Sufficient、Validation Bottleneck、C Rejected、Inconclusiveを区別する。

## Verification

```text
pytest: 345 passed
ruff: All checks passed
mypy --strict: Success (152 source files)
coverage: 85.72% (required 85%)
```

Machine-readable Preflightは[`v034_preflight_result.json`](v034_preflight_result.json)に保存した。

## Current acceptance

Control-plane、Artifact contract、Global Validation Constraint、Common Cross-fit、Decision Auditの実装
PreflightはPASS。Semantic/Predictive Diversity、Structure、Hidden OutcomeはLive Run未実行のためUNMEASURED。
`unrestricted_outcome_advantage_over_B/B_plus`はINCONCLUSIVEである。

Live状態は0/36 Runs、0/324 Cycle Decisions、0/36 Submissions、0/36 Hidden Scoresである。したがって、
System C、B+、Bの成果差については何も主張しない。

## Preserved state

v0.3.3実装はcommit `100ae5b`として親Branchに保存した。v0.4のProblem Formulation実装は既存の
`stash@{0}`に待避されたままで、本変更へ混入していない。
