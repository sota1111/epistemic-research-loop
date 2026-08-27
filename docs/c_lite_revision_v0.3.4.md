# Epistemic Research Loop C-lite v0.3.4 変更仕様

## 1. 位置づけ

**名称:** 成果限定 B / B+ / C 比較・Sealed Decision Quality検証  
**対象:** IEEE-CIS Fraud Detection  
**比較:** Outcome-only  
**構成:** 3 Generic Agents × 3 Adaptive Cycles × 12 Outer Seeds × B/B+/C  
**Primary:** 全36 Output lock後のHidden / Private AUC

v0.3.4はAction Space、Artifact、Common Cross-fit基盤を凍結し、次の問いだけを測る。

> 明示的Hypothesis、Falsification、Belief Updateを持つSystem Cは、Strong QDのBまたは
> Predictive QDのB+より高い最終成果へ到達するか。

v0.3.3までにGeneric AgentのSemantic Diversityは確認したが、最終RepresentationとPredictive Errorの
十分な分化、CのB/B+に対する成果上の優位は未測定である。v0.3.4はEfficiency比較を廃止し、純粋な
Capability/Outcome差を測る。

## 2. Outcome-only Resource Policy

CPU、RAM、GPU、Thread、Wall-clock、LLM Token、Experiment数、Costを制限しない。これらをUtility、
Proposal admission、Final Selection、Acceptance、System間の優劣に使用しない。障害解析用の記録だけは
許可する。Heavy Jobを逐次実行するのはMemory/I/O/Oversubscriptionを避けるExperiment Isolationであり、
Resource Budgetではない。

この比較から言えるのは「同じ外部研究機会の下で到達した成果差」である。Cが勝っても、同一Compute、
Efficiency、Cost、実運用適性の優位は主張しない。

```yaml
resource_policy:
  cpu_limit: null
  memory_limit_gb: null
  gpu_limit: null
  thread_limit: null
  wall_clock_limit: null
  experiment_cost_penalty: false
  use_resource_in_selection: false
  use_resource_in_acceptance: false
  heavy_execution_order: sequential
```

## 3. 共通外部条件とImmutable Base

B/B+/Cでbase commit、Dataset、3 Agent、3 Cycle、Outer Seed、LLM、Library、Tool、Code-development権限、
Common Cross-fit、Sealed Decision Set、Final Submission数を揃える。Internet、Winner情報、実行中の
Leaderboard、Agent間Belief/Score/Code/Global Best共有、固定Nicheは禁止する。

IEEE-CIS baseは過去Private結果や過去Agent解法を含まない次のsnapshotに固定する。

```text
ac3b46975e5da64570fb79d6e1141bc5c7525d0f
```

Artifact Validator、Common Forward Cross-fit、Sealed Evaluator、Global Validation Constraint、Decision
Audit、Semantic Overlap、Final Meta-selector、Worktree管理だけをInfrastructure overlayとして許可する。
過去W02実装、Private Score、Candidate、Winner由来のUID/Feature、Global Best、Ensemble Weightは混入禁止。

## 4. 比較Arm

### System B — Strong QD

Candidate Population、Performance Archive、Semantic/Implementation Descriptor、OOF Error Archive、
Mutation Historyを持ち、Performance、Novelty、Coverage、Robustness、Archive Contributionで選択する。
Explicit Hypothesis Registry、Posterior、Competing Explanation、EIG/EVSI、Structure Maturation、Falsification
Debt、Belief Updateは持たない。

$$U_B=\alpha\widehat{\Delta Performance}+\gamma QDContribution+\delta\widehat{\Delta Robustness}$$

### System B+ — Predictive QD

BにExpected Difference Slice、Prediction差のMechanism、Predictive Diversity Debt、Validation World
Descriptor、Slice OOF、Standalone/Ensemble Eligibility分離を追加する。Posterior、Structural Lifecycle、
Null/Skeptic Fork、Validation Debt、EIG/EVSI、Belief Updateは持たない。

$$U_{B+}=U_B+\lambda ExpectedPredictiveComplementarity+\mu SliceCoverage$$

Proposalには`expected_difference_slice`、`predicted_mechanism`、期待するResidual関係、Downstream Decisionを
必須とする。

### System C — Epistemic QD

B+にAgent-local Hypothesis Registry、Alternatives、Observable Prediction、Confidence、Structural Leverage、
Maturation Fork、Null/Skeptic、Independent Verification、Validation Debt、Falsification、Belief Update、
EVSI/Discrimination Valueを追加する。

$$U_C=U_{B+}+\beta EVSI+\kappa DiscriminationValue+\nu ValidationDebtReduction$$

全UtilityからCost項を除く。詳細Policyは`docs/v034_arm_*_policy.md`へ固定する。

## 5. Agent-local StateとEvidence境界

全Agentへ同じGeneric Promptを与え、Model、Feature、UID、Role、Nicheを指定しない。Current Belief、Gap、
Uncertainty、Salience、Hypothesis、Utility、Candidate Score/Design、Validation World BeliefはAgent-localで、
他Agentへ共有しない。

全ArtifactはGlobal Evidence Vaultへ保存するが、保存と配信を分離する。Agentが受け取れるのはDataset、
Schema、Artifact/Leakage Rule、Validation Eligibility Rule、自分のArtifact検査、Proposalの意味的重複有無
だけである。他AgentのFeature、Model、Score、Posterior、Candidate、Global Best、解釈、次方針を渡さない。

## 6. Global Validation Constraint

Validation上の知識はBelief共有ではなく、評価資格制約として共有する。初期Constraintを次に固定する。

```text
GVC-IEEE-001:
Future-transportのFinal Pool、正式なPredictive Diversity、Weight学習、Rankingには
past-only strict-forward OOFを必須とする。
```

Random/Shuffled OOFはDebug、Representation探索、Model理解の診断に使用できるが、Final Candidate Ranking、
正式なError Diversity、Ensemble Weight、Future Private根拠には使用しない。

新Constraintは、(A)独立Agent 2件以上、(B)単独Agentで3 Horizon×3 Seed・同方向・Artifact/Verifier Pass、
または(C)Leakage/Target/Future/Fold/Schema安全問題でのみ昇格する。Agent通知にはConstraint違反だけを含め、
発見元、Score、Model、Feature、Global Bestを含めない。

## 7. Semantic Overlap

同ClusterのExperimentを次に分類する。

* `independent_replication`: 独立Agent、Evidence未閲覧、事前登録、同じClaimに対してModel、Observable、Slice、
  または反証経路が異なり、Constraint/Calibrationへ新しいEvidenceを与える。正の成果として数える。
* `redundant_duplication`: Claim、Operation、Observable、Decisionが同じで、新しい予測差も事前登録された
  Replication目的もない。QD Contributionを与えない。
* `unique`: 単一Clusterの固有実験。

Experiment IDの違いだけをNoveltyにしない。

## 8. Cycle ContractとParent/Challenger Lock

各Runの3 Agentは各3 Cycleを順次実行する。Cycle開始時に自分のEvidence/Candidate、Global Constraint、
Semantic Similarity、Artifact Contractだけを受け取る。

全Armで次を必須とする。

```text
proposal.yaml
decision_binding.yaml
semantic_signature.yaml
experiment_source/
local_metrics.json
parent_predictions.parquet
challenger_predictions.parquet
decision_result.yaml
artifact_validation.json
```

B+/Cは`expected_error_slice.yaml`と`predicted_mechanism.yaml`、Cはさらに`hypothesis.yaml`、
`alternatives.yaml`、`falsification.yaml`、`belief_update.yaml`、`validation_debt.yaml`を出力する。

Cycle終了時にParent、Challenger、Local AUC、Local選択、Minimum Gain、Stability/Rejection条件、両Prediction
HashをLockする。3 Agent×3 Cycleの9 Decision Hashが揃わないRunはFinal Lockできない。

## 9. Research/Sealed Partition

`TransactionDT, TransactionID`でstable sortし、先頭80%をResearch Region、最新20%をSealed Decision
Regionとする。AgentはResearch RegionだけでFeature、Validation、Model、OOF、Ensemble Weightを研究する。
Sealed LabelはAgentとAgent-local Finalizerに渡さず、全36 OutputのLock後にのみ一括評価する。

Pipeline、Feature、Hyperparameter、WeightをLockした後、Submission生成時だけ全590,540 train rowsで
決定論的に再学習できる。Sealed結果を見た変更は禁止する。Competition Testは506,691行を必須とする。

## 10. Full Common First-level Cross-fit

Final Selectionへ進む全Candidateを同一planで再実行する。

```yaml
stable_sort: [TransactionDT, TransactionID]
split_type: expanding_time
horizons: 3
minimum_gap_days: 7
model_seeds: [17, 42, 20260826]
feature_fit_scope: fold_train_only
```

Dataset、Research row set、Fold Plan Hashを全36 Outputで一致させる。Agent-local FoldだけのRanking、
Shuffled/Forward AUCの直接比較、異なるRow SetのUtility混在、MSEだけのAUC Final選抜、Future Rowを含む
Feature Fitを禁止する。

## 11. Candidate Artifact Contract

Final Candidateは次の11 Artifactを必須とする。

```text
candidate.yaml
run_manifest.yaml
feature_manifest.yaml
fold_assignment.parquet
oof_predictions.parquet
test_predictions.parquet
metrics.json
model_artifact/
submission.csv
source_code_ref.json
environment_lock.json
```

Dataset/Source/Fold Hash、OOF Honesty、Strict-forward、Test/Submission行数、Unique TransactionID、Finite
Probability、Schema、Leakage、Reproducibility Metadataを検査する。Exit Code 0や存在だけでは成功にしない。

## 12. Candidate EligibilityとFinal Meta-selector

Standalone EligibilityはArtifact、OOF Honesty、Strict-forward、Seed Stability、LeakageとQuality Floorを要求
する。Ensemble Eligibilityは共通Gateに加えてNested Marginal AUC Gain > 0、複数Horizonで同方向、Weightが
単一Foldに集中しないことを要求する。Standalone Quality Floor未満でもEnsemble Gateを通れば専用Archiveへ
保持する。Final Poolは両Eligibilityの和集合とする。

Final SelectorはNested Strict-forward AUC、Worst Horizon、Seed Stability、事前固定されたCandidate ID
Tie-breakの順で選ぶ。ResourceやComplexityは入力に持たない。Ensemble WeightはOOFかつ評価Blockより前の
Blockだけで学習し、Best Singleを上回らないEnsembleはLockしない。Runごとに
`locked_submission.csv`、`locked_candidate_manifest.json`、`locked_selection_reason.json`の1件だけをLockする。

## 13. Sealed Decision Quality Audit

全Cycle DecisionについてSealed Parent/Challenger AUCを比較し、次を測る。

$$DecisionSignAccuracy=\frac{LocalとSealedで採否が一致したDecision数}{評価可能なDecision数}$$

* False Rejection: Localで棄却したChallengerがSealedでParentを上回る割合
* False Adoption: Localで採用したChallengerがSealedでParentを下回る割合
* Decision Regret: `max(Sealed Parent, Sealed Challenger) - Sealed Selected`
* Run Regret: `Sealed Oracle Best Generated - Sealed Locked Final`

Validation Decisionは順位予測、Rank Correlation、False Adoption、Future Calibrationで評価する。

## 14. System C Structure Lifecycle

Cだけが`OBSERVATION → PROVISIONAL → ALTERNATIVES → DISCRIMINATING TESTS → PARTIAL`を管理し、
`VALIDATED_ACTIONABLE`、`VALIDATED_NON_ACTIONABLE`、`USEFUL_ENCODING_UNVALIDATED`、`FALSIFIED`、
`INCONCLUSIVE`へ終端する。

Seed単位でValidatedへ昇格しない。Run集約で3 Seed以上、Leave-one-seed-out、Confounder-preserving Null、
独立含意、Multi-context、Decision Adoption、Held-out Negative Control Reject、False Promotion Gateを要求する。
Validated前のClaimは他Agentへ共有しない。Validated後も共有対象は観測事実と評価制約だけである。

## 15. Confirmatory MatrixとSealing

```text
B × 12 seeds
B+ × 12 seeds
C × 12 seeds
= 36 Runs

1 Run = 3 Generic Agents × 3 Adaptive Cycles = 9 Agent Cycles
```

同一Outer SeedをB/B+/Cでpairingする。Arm間でResult/Evidenceを移送せず、全36 Runが独立Branchから開始
する。36件すべてのCandidate、Feature、Fold、Decision Rule、Test Prediction、Submission、9 Decision
Hashを検証してBatch Hashを作るまで、Sealed/Private Scoreを一件も返さない。部分Batch評価は禁止する。

## 16. Outcome Metricsと統計

PrimaryはSeed別の`PrivateAUC_C - PrivateAUC_B`と`PrivateAUC_C - PrivateAUC_B+`。SecondaryはSealed
Future AUC、Private Win/Mean/Median、CV→Sealed/Private Spearman、Decision Sign、False Reject/Adopt、
Regret、Nested/Hidden Ensemble Gain、Validated Structure、False Promotion、Constraint/Replication、
Artifact/Submission率である。

Semantic Count、QD Occupancy、Residual Effective Rank/Correlation、Model/Representation/Hypothesis Count、
Entropy/Information Gainは診断専用。CPU、RAM、GPU、Thread、Wall-clock、Token、CostはPrimary、Secondary、
Acceptanceのすべてから除外する。

Outer SeedをBlockとしてMean/Median paired delta、10,000回Paired Bootstrap 95% CI、Positive Rate、Exact
Sign Test、Worst/Best Seedを報告する。Minimum Meaningful Private AUC Gainは0.001に固定する。

## 17. 判定

* **Full C Capability Pass:** Median C−B+ ≥ 0.001、Bootstrap下限 > 0、CのB+に対するWin Rate > 0.5、
  CのSelection Regret < B+。
* **B+ Sufficient:** B+ > BかつC ≈ B+。通常B+、高Leverage仮説時だけC Fork。
* **Strong B Sufficient:** B ≈ B+ ≈ C。
* **Validation Bottleneck:** LocalでB+/C優位、PrivateでB優位、CV→Private順位相関が低い。
* **C Rejection:** C < B+、またはStructure/Falsificationを増やしてもPrivate/Regretを改善しない。
* **Inconclusive:** 36 Run未完、Evaluator片Arm失敗、Lock後Policy変更、情報汚染、Sealed漏洩、Hash不一致、
  CIが広すぎる。

`incremental_value_over_strong_qd`という名称は廃止し、Resourceを評価しない成果差を
`unrestricted_outcome_advantage`として記録する。

## 18. Acceptance Model

```yaml
acceptance:
  control_plane: PASS | FAIL
  artifact_reliability: PASS | FAIL
  global_validation_constraint: PASS | FAIL
  full_common_crossfit: PASS | FAIL
  decision_audit: PASS | FAIL
  semantic_diversity: PASS | PARTIAL | FAIL
  quality_predictive_diversity: PASS | PARTIAL | FAIL
  structure_falsification: PASS | PARTIAL | FAIL
  true_structure_discovery: PASS | PARTIAL | FAIL | UNMEASURED
  final_hidden_outcome: PASS | FAIL | UNMEASURED
  unrestricted_outcome_advantage_over_B: PASS | FAIL | INCONCLUSIVE
  unrestricted_outcome_advantage_over_B_plus: PASS | FAIL | INCONCLUSIVE
```

## 19. Controller責務と実行Flow

ControllerはBranch/Worktree Isolation、Artifact、Evidence保存、Validation Constraint、Semantic Overlap、
Common Cross-fit、Decision Audit、Final Lock、Hidden Batch、Outcome集計を行う。Model/Feature/UID指定、Global
Best/他Agent Score共有、Belief統合、ResourceによるReject/優遇は行わない。

```text
PREREGISTER POLICIES
→ CREATE 36 ISOLATED RUNS
→ 3 AGENTS × 3 CYCLES
→ ARTIFACT / CONSTRAINT CHECK
→ LOCK 9 DECISIONS AND ONE FINAL OUTPUT PER RUN
→ COMMON FIRST-LEVEL CROSS-FIT
→ NESTED FINAL SELECTION
→ VERIFY 36 OUTPUT HASHES
→ UNBLIND SEALED DECISION REGION
→ DECISION AUDIT
→ BATCH PRIVATE EVALUATION
→ PAIRED OUTCOME ANALYSIS
→ FINAL ACCEPTANCE
```

## 20. 実装対応

| 要件 | 実装 |
| --- | --- |
| Outcome-only Plan/36 Run Lock | `benchmark/v034_outcome_only.py` |
| Global Validation Constraint | `controller/validation_constraints.py` |
| Stable Partition/Common Folds | `controller/common_crossfit.py` |
| Semantic Replication分類 | `controller/semantic_overlap.py` |
| Cycle Artifact Contract | `controller/cycle_contract.py` |
| Candidate Contract | `controller/candidate_artifacts.py` |
| Arm Policy/Eligibility/Selector | `evaluation/v034.py` |
| Parent/Challenger/Decision Audit | `evaluation/v034.py` |
| Sealed Batch/Paired Statistics | `evaluation/v034.py` |
| 設定 | `configs/benchmarks/v034_b_bplus_c_outcome_only.yaml` |
| Preflight | `scripts/verify_v034_outcome_only.py` |

## 21. 最終原則

仮説数、Semantic Cluster、Effective Rank、反証数、研究ノートの量だけを成功としない。

$$Epistemic/QD\ Policy \rightarrow Better\ Decisions \rightarrow Better\ Locked\ Candidate
\rightarrow Higher\ Hidden/Private\ AUC$$

Cが多くの構造検証を行ってもLocked Hidden成果を上回らなければOutcome-only比較では支持しない。逆にCが
多くのResourceを使用してもPenaltyを与えない。v0.3.4が判定するのは、CがBおよびB+より高い成果上限へ
到達したかだけである。
