# Epistemic Research Loop C-lite 修正仕様書

## IEEE-CIS Agent/Cycle Scaling検証反映版

- 文書バージョン: 0.2
- 修正対象: `Epistemic Research Loop C-lite システム仕様書 v0.1`
- 対象リポジトリ: `epistemic-research-loop`
- 対象検証: IEEE-CIS Fraud Detection
- 適用方針: 差分仕様。旧仕様と矛盾する場合は本文書を優先する。
- ステータス: 実装修正用

## 1. 修正目的

3 Agentを1 Cycleから3 Cycleへ拡張した検証では、9選択中6件のみ完了し、3件が失敗した。Top-solution Rubricは14.25/100でDiagnostic-onlyに留まった。原因は、固定Shell Action Space、新規Feature/UID/Model/Post-processing/Ensembleを実装できない契約、診断からCandidateへ遷移しない制御、意味的重複、Portfolio size 1、OOF/Error Diversity/Ensemble不在、並列Memory競合、Locked CandidateのHidden評価不在である。

Agent BranchはMemoryを共有せずMeta-controllerもなかったため、Agent間Unionは統合SolutionではなくDiscovery Potentialだけを表した。一方、知識非共有でもAdversarial Validation、Feature AUC、Duplicate Scanへ集中した。従って全面的Cross-agent Memoryを導入するのではなく、次を中心原則とする。

> 共有ストレージ、非共有Belief、選択的Communication

## 2. 修正後システム

本システムは、1つの中央実験基盤の上で複数のAgent-local Belief Islandを並行進化させるEpistemic Research Loopである。

Globalとするもの:

- Dataset Snapshot、Experiment Runner
- Compute Budget、Resource Scheduler
- Artifact Store、Evidence Vault
- Candidate Archive、QD Archive
- Stop Policy、Final Meta-selector、Hidden Evaluator Interface

Agent-localとするもの:

- Hypothesis RegistryとPosterior
- Validation World Belief、現在の問題理解、未検証の作業仮説
- Experiment Proposal History、Exploration Policy
- Candidate内部設計方針

Hypothesis ID、Posterior、優先順位、Validation World Posterior、有力Feature/UID、Best Candidate、次の探索方針、他Agent評価は同期しない。単一のGlobal Hypothesis Posteriorは廃止する。

## 3. 主要変更

| ID | 対象 | v0.2 |
|---|---|---|
| CHG-001 | Agent Memory | Agent-local Hypothesis Registry |
| CHG-002 | Evidence | Global保存、選択的・遅延配信 |
| CHG-003 | Meta Controller | Diversity、Budget、Resource、Queueのみ管理 |
| CHG-004 | Action Space | Agentによるコード・実験・Pipeline生成を許可 |
| CHG-005 | Experiment遷移 | 診断からCandidate実装へのPhase Gate |
| CHG-006 | QD | 複数Epistemic NicheとCandidateを保持 |
| CHG-007 | Novelty | 意味・仮説・Observable・Decision単位 |
| CHG-008 | Validation | Forward Fraud-label Validation必須 |
| CHG-009 | OOF | Candidate昇格の必須Artifact |
| CHG-010 | Ensemble | Final Meta-selectorの必須機能 |
| CHG-011 | Resource | Memory-aware Schedulingと隔離 |
| CHG-012 | 評価 | Locked Hidden/Private PerformanceをPrimary化 |
| CHG-013 | Knowledge Sharing | Comm-0/Comm-S/Comm-Fを独立実験化 |

## 4. アーキテクチャ

```text
Global Control Plane (Budget / Queue / Resource)
  ├─ Agent Island A (local beliefs / registry / history)
  ├─ Agent Island B (local beliefs / registry / history)
  └─ Agent Island C (local beliefs / registry / history)
          ↓ local proposals only
Experiment Proposal Pool
          ↓ semantic duplicate / cost / risk
Diversity-aware Scheduler
          ↓
Isolated Code Runner (build / train / evaluate)
          ├─ Global Evidence Vault
          ├─ Candidate Archive (OOF / test / code)
          └─ Global QD Archive (niche / quality)
                    ├─ Selective Evidence Router
                    └─ Final Meta-selector (cross-fit / ensemble)
```

Global Control Stateはdataset hash、残Budget、AgentとNiche、queue/running IDs、archive occupancy、resource pressure、collapse metricsだけを持つ。Agent Belief Stateはagent ID、niche、private hypotheses、validation-world distribution、private notes/history/rejections/candidate refsを持つ。

## 5. EvidenceとCommunication

全実験結果はGlobal Evidence Vaultへ観測事実として保存する。Featureを削除すべき、Time CVが正しい、Private性能が悪化する、といった解釈はEvidence本文ではなくAgent-local Registryへ保存する。

Visibilityは次の5状態とする。

```text
private
controller_only
shareable_fact
shared_challenge
global_safety
```

Default Communication Modeは`selective_delayed_asymmetric`とし、全Agentへの即時全面共有を禁止する。Schema、Metric、Budget、Resource、Leakage/Safetyは即時共有する。実行中フラグはIDだけ共有する。Raw Metric、単発結果、Artifactは原則非共有とする。再現済み事実は選択的・遅延共有し、Global Best、Posterior、内部方針は探索中共有しない。

Evidence Promotionには、Artifact Contract合格、再現可能、観測/解釈分離、他Agentへの直接指示でないこと、計算削減効果、多様性を著しく損なわないことを要求する。

Challenge Sharingは採用推奨ではなく反証依頼として行い、source agent、source posterior、source candidate scoreを隠す。MigrationはDefaultで3 Cycleごと、またはPhase境界だけに行う。対象は再現済み事実、反証課題、共通Infra Failure、Behavior Descriptor、未探索Nicheに限定する。

## 6. Diversity-aware Meta Controller

Meta ControllerはAgent別Budget、Niche最低Budget、Queue、Semantic Duplication、Resource、二層Archive、Collapse、Agent再初期化、Final遷移とShortlistを管理する。Posterior平均、Global Posterior、最有力仮説/Global BestのBroadcast、同一Evidence Summary配布、同方向への誘導、短期CVだけによるNiche淘汰は禁止する。

初期Niche:

```text
temporal, entity_client, validation, distribution_shift, label_quality,
feature_representation, model_family, error_analysis, falsification,
post_processing, ensemble
```

各AgentへPrimary Nicheを1つ以上割り当て、対象仮説、Operator、成功指標を分ける。初期最低Budgetはtemporal 0.15、entity_client 0.15、validation 0.15、distribution_shift 0.10、feature_representation 0.15、model_family 0.10、falsification 0.10、post_processing/ensemble 0.10とする。最低Budget消費前に短期ScoreだけでNicheを削除しない。

## 7. Semantic DuplicationとCollective Collapse

Proposalを次のSignatureへ正規化する。

```yaml
semantic_signature:
  target_hypotheses: [temporal_shift]
  data_slice: [train_vs_test]
  operation: [adversarial_classifier]
  observable: [auc]
  decision_affected: [feature_policy]
  candidate_producing: false
```

Target Hypothesis、Data Slice、Operation、Observable、Downstream Decisionが同一で新しい反証条件がなければSemantic Duplicateとする。Replicationだけはoriginal experiment、変更条件（seed/time window/entity slice）、replication hypothesisを必須として許可する。

測定対象はProposal Similarity、Hypothesis Cluster Entropy、Experiment Family Effective Count、QD Niche Occupancy、Feature Family/Validation World重複、Global Best近傍へのBudget集中、連続同一Family数である。

次のうち2つ以上が2 Cycle連続したらCollapseとする: 同一Cluster 70%以上、Effective Count < 2.0、QD Occupancyが増えない、同一Hypothesis FamilyへBudget 50%以上、平均Similarity > 0.80。

処置順はdominant cluster停止、未探索Nicheへ再配分、Prompt/Prior再初期化、別Operator Agent追加、最有力仮説をFalsifierへ渡す、Global Bestを隠す、Action Space点検、不足Tool/Script生成とする。

## 8. Code-development / Isolation Contract

各Agentは独立Git WorktreeまたはContainerで、Python Script、既存Script、Feature Generator、Validation Splitter、UID Generator、Fold-safe Aggregator、Model Family、Post-processing、OOF、Ensemble/Stack、Candidate/Submission Pipeline、Unit Test、Manifestを作成・修正できる。

Test Label、実行中のHidden/Private Score、Winner Code/Write-up、foldを越えるTarget Aggregate、testを含むTarget Encoding、Dataset Snapshot破壊、他Agent Workspace参照、Global Best複製、Artifactなしの完了報告は禁止する。Global登録はArtifact Contractに合格したEvidence/Candidateだけに限る。

## 9. Experiment分類とPhase Gate

Diagnostic ExperimentはShift、Entity、Leakage、Label、Validation、Error Sliceを調べ、Evidence、local belief update、Decision Recommendationを出す。Candidate-producing Experimentは診断をFeature/Validation/Model/Post-processingへ実装し、Pipeline Code、Feature/Fold/Model、OOF/Test Prediction、Metrics、Submission、Run Manifestを出す。

Phaseは次の7段階とする。

```text
PHASE_0_BASELINE
PHASE_1_DIAGNOSIS
PHASE_2_HYPOTHESIS_DISCRIMINATION
PHASE_3_CANDIDATE_IMPLEMENTATION
PHASE_4_ROBUSTNESS
PHASE_5_ENSEMBLE
PHASE_6_FINALIZATION
```

同一AgentがDiagnosticを3回連続実行したら、次の1回はCandidate-producingを必須とする。例外はvalidation leakage未解決、dataset corruption未解決、実装に必要な観測欠落、resource不足だけとし、機械可読理由をControllerへ提出する。Resource/invalid artifact failureは診断回数やPosteriorを更新しない。

Diagnosticは`decision_id`、possible actions、result-to-actionを事前登録する。結果をAction-changing、Action-neutral（理由必須）、Inconclusive、Invalidに分類する。

## 10. IEEE-CIS Plugin

Pluginは次を実行可能にする。

- card/addr/email/device/D/reference date/transaction time/frequency consistencyによる複数UID候補、stability/precision proxy、Seen/New/Questionable分割
- 3 Horizon以上のForward Validation、Time Gap、Rolling/Expanding Window、期間感度、rank stability、client slice
- fold内fit/validation transformによるUID count、amount mean/std、time delta、D/V aggregate、frequency、target-independent aggregate
- LightGBM/XGBoost/CatBoost/Linear/Neuralのうち2 family以上
- Known/New/Questionable AUC、frequency/time horizon slice、routing比較
- Client average/consistency、Known/New routing、temporal smoothing、calibration、適用前後Forward評価
- OOF、prediction/residual correlation、marginal gain、weighted/rank blend、stack、nested cross-fit

Adversarial AUCはDistribution Shiftの診断だけに用いる。変化後はMulti-horizon Forward Fraud-label Validation、Model Rank変化、Candidate Performanceを確認して採否を決める。

UIDはoverlapだけでは昇格させない。時間をまたぐ再出現、UID内feature consistency、fraud label structure、UID外generalizationとの差、複数Forward Foldでの再現、fold-safe aggregate改善、単純frequency artifactでないことの7条件を要求する。

## 11. 二層Archive

Epistemic ArchiveはTemporal/Entity/Label/Shift/Validation/Post-processing Hypothesisを保持する。Candidate ArchiveはRunnable Pipeline、OOF/Test Prediction、Model Artifact、再現情報、Error Profileを保持する。

Candidate descriptorはsource agent、niche、validation world、model family、representation、routing、post-processing、error profileを持つ。Agentに公開するのは未探索Niche、cell占有、resource cost、自分の位置だけとし、他Agent score/feature/code/posterior、Global Best、blend weightを非公開とする。

Archiveはminimum candidate slots 8、maximum 40、minimum niche slots 1とし、Portfolio size 1を禁止する。Best Expected Performance、Best Robustness、Best Temporal Generalization、Best New-client Performance、Best Error Diversity、Lowest-cost Competitive Candidateを保持する。

## 12. Candidate Artifact Contract

Candidate昇格には次をすべて要求する。

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
source_code_ref
environment_lock
```

`candidate.yaml`はcandidate/source agent/git commit/dataset hash/environment hash、validation protocol/primary/fold scores/std、known/new slice、artifact refs、leakage、reproducibility/seedsを記録する。Exit Code 0でも欠落があれば成功ではない。

Terminal Status:

```text
COMPLETED
FAILED_EXECUTION
FAILED_RESOURCE
INVALID_ARTIFACT
INVALID_LEAKAGE
INCONCLUSIVE
```

## 13. Resource IsolationとToken Efficiency

Proposalはcpu cores、memory GB、GPU memory、expected minutes、Parquet scan columns、full materializationを見積もる。SchedulerはMemory合計、full scan数、GPU、CPU、I/O、temporary storage、LLM concurrencyを管理する。全Feature/UID探索、full materialization、multi-model CV、OOF stack、大規模aggregateをHeavyとし、原則逐次実行する。

Defaultはheavy 1、light 3、memory safety margin 0.25。`ArrowMemoryError`等は`FAILED_RESOURCE`とし、Posteriorを更新せずresource profileを修正して再実行候補へ戻す。

Proposal token上限、Semantic Cluster別上限、構造化Tool要約、Niche限定Context、Full Log再投入禁止、Candidate最低token配分を設ける。completed experiment、valid candidate、新semantic family、private-score improvement当たりtokenを記録する。

## 14. Final Meta-selector

AgentのBeliefではなくCandidateを共通条件で評価する。Shortlistを`Multi-horizon Forward Folds + Time Gap + Known/New Client Slices + Fold-safe Feature Generation`で再実行し、その共通OOFだけでError Diversityを評価する。

選抜順はLeakage/Artifact/Reproducibility Gate、Common Cross-fit、Performance/Robustness、Error Correlation、Subgroup Complementarity、Blend/Stack生成、Nested Evaluation、Locked Candidate選択とする。

```text
FinalUtility =
  α ExpectedForwardScore
  + β Robustness
  + γ NewClientPerformance
  + δ MarginalEnsembleGain
  - η Uncertainty
  - ρ LeakageRisk
```

Blend weightはOOF以外で学習せず、学習用と評価用を分離する。Nested Cross-fitまたはsecond-level holdoutを使い、predictionだけでなくresidual correlationを使う。Quality floor未満を除外し、Public LBでweight調整しない。

## 15. 制御フロー

```text
INITIALIZE → ASSIGN NICHES → CREATE LOCAL BELIEFS → LOCAL PROPOSALS
→ SEMANTIC DUPLICATION CHECK → RESOURCE CHECK → PREREGISTRATION
→ ISOLATED EXECUTION → ARTIFACT CONTRACT VALIDATION
  ├─ invalid: no belief update
  └─ valid: GLOBAL EVIDENCE STORAGE → LOCAL BELIEF UPDATE
→ candidateならCandidate Archive/OOF Store、診断ならcounter increment
→ SELECTIVE EVIDENCE ROUTING → COLLAPSE CHECK → PHASE GATE
→ COMMON FINAL CROSS-FIT → ERROR DIVERSITY → META-SELECTION
→ LOCKED SUBMISSION → HIDDEN/PRIVATE EVALUATION
```

## 16. 評価

Primary EndpointはLocked Final CandidateのHiddenまたはPrivate Performanceとする。Top-solution Rubricだけでは成功判定しない。

SecondaryはLocal CV、Forward score、CV→Hidden rank correlation、Known/New client、critical discovery rediscovery、rubric、candidate/runnable/OOF/family数、QD occupancy、hypothesis entropy、semantic duplicate/collapse、residual effective rank、ensemble gain、completion/invalid/memory failure率、token/GPU/CPU costとする。

## 17. Knowledge Sharing Ablation

- Comm-0: Schema、Budget、Resource、Safety、Experiment IDだけ共有する。
- Comm-S: 再現済み事実、反証依頼、Infra Failure、未探索Niche、Phase境界Migrationを選択・遅延共有する。Default。
- Comm-F: 仮説、Posterior、結果、Candidate score、Global Best、Summaryをlive共有する。比較用でありDefaultにしない。

同一LLM、Initial Code、Action Space、Token/Compute/Wall-clock、Agent/Cycle、Seed、Hidden Evaluatorで比較する。Comm-S採用条件はHidden performanceがComm-0以上、duplicate率がComm-0未満、hypothesis diversityがComm-Fより高いこと。Comm-F優位なら全面共有への懸念は支持されないが、複数Competition/Seedで再現する。

Search軸（A/B/B+/C）とCommunication軸（Comm-0/S/F）は分離する。主比較はB/B+/C × Comm-S、Communication ablationはC × Comm-0/S/Fとする。

## 18. Acceptance Criteria

機能:

- Agent-local Registry/Posterior/Validation World/Historyを持ち、自動同期しない。
- Evidence Vaultが全Artifactを保存し、RouterがVisibilityを適用する。
- Global Bestを探索中Agentへ公開しない。
- Niche割当、意味ベースDuplicate、Collapse、最低Niche Budgetを実行できる。
- Agentが隔離環境でScript/UID/Validation/Feature/Model/Post-processing/Ensembleを開発できる。
- 3診断後のCandidate強制、Decision Bindingを実行できる。
- 3 Horizon Forward fraud validation、gap、fold-safe UID aggregate、Known/New slice、2 model family以上を実行できる。
- CandidateがOOFを含むArtifact Contractを満たし、Schedulerがmemory競合を防ぐ。
- Common Final Cross-fit、Error Diversity、OOF Ensemble、Locked Submissionを実行できる。

IEEE-CIS 1 Run内最低条件:

```text
1 Validated UID Candidate
3 Horizon以上のForward Validation
1 Fold-safe UID Aggregate Candidate
Known/New Client Slice
2 Model Families以上
3 OOF Candidates以上
1 Ensemble Candidate以上
1 Locked Submission
```

Reliability初期目標はCompletion >= 90%、Invalid Artifact <= 5%、Resource Failure <= 5%、OOF generation >= 90%、Reproduction >= 90%とする。

Research条件として複数Seed、Hidden/Private Primary、Knowledge Sharing独立ablationを要求する。Action Space固定のままAgent/Cycleだけを増やさない。Discoveryが増えてもFinal Performanceが上がらなければ失敗とする。

## 19. 実装優先順位

1. Runner Reliability: Scheduler、memory isolation、Artifact validator、status、dataset/environment hash
2. Code-development Contract: worktree、script/test/candidate/submission
3. IEEE-CIS Validation: forward/gap/UID/fold-safe/client slice
4. Agent-local Belief Islands
5. Diversity Control: niche/signature/duplicate/collapse/minimum budget
6. Selective Communication: vault/promotion/router/challenge/migration
7. Candidate QD/OOF: multi-candidate/common schema/diversity/shortlist
8. Final Meta-selector: common cross-fit/blend/lock/hidden evaluation
9. Matched-budget Evaluation: B/B+/C、Comm-0/S/F、multi-seed/competition

## 20. 標準設定

`configs/system_c.yaml`と`configs/competitions/ieee_cis.yaml`を正本とする。Defaultは4 Agent、local beliefs、Comm-S、3 Cycle migration、semantic threshold 0.85、3 diagnostics gate、3 forward horizons、archive 8–40、heavy 1/light 3、memory margin 0.25、locked hidden performance primaryである。

## 21. v0.1から無効化する要件

次を削除または無効化する。

```text
全Agentが同一Global Hypothesis Posteriorを参照する
全Experiment Resultを全Agentへ即時Broadcastする
Global Best Candidateを探索中に共有する
Meta Controllerが単一の正しい世界理解を決定する
Portfolio size 1を許容する
既存Shell Commandだけで探索する
新規Script作成を禁止する
Adversarial AUCだけでFeature Policyを採用する
Diagnostic Experimentを無制限に連続実行する
Exit Code 0だけで成功判定する
Agent/Cycleだけを増やして評価する
Top-solution Rubricだけで最終性能を判定する
```

## 22. 最終判断

「固定Shell Action SpaceのままAgent/Cycleを増やせばIEEE-CIS上位Pipelineへ近づける」は否定された。一方、Bayesian Experimental Design、Agent-local Registry、Epistemic Niche、QD、Falsification、OOF Error Diversity、Selective Sharing、強いSystem Bに対するC-liteの優位性は未判定である。

次の検証に必要なのは全面Cross-agent Memoryではなく、expressive code-development、local beliefs、global evidence、selective delayed routing、niche/collapse、diagnosis-to-candidate gate、multi-candidate archive、forward fraud validation、OOF diversity、meta-selector、resource isolation、locked hidden evaluationである。

> すべての結果を中央へ保存する。すべての結果を全Agentへ配らない。
> Agentの信念を同期しない。探索領域の多様性を中央で保護する。
> 診断結果を必ずRunnable Candidateへ変換する。
