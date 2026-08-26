# Epistemic Research Loop C-lite v0.3.1 測定・Debt終端仕様

**文書バージョン:** 0.3.1  
**修正対象:** v0.3 Dynamic Structure Maturation  
**対象検証:** IEEE-CIS Fraud Detection  
**ステータス:** 実装・検証用差分仕様

本文書とv0.3以前の仕様が矛盾する場合、本文書を優先する。v0.3.1は探索機能追加版ではない。v0.3を凍結し、Primary Endpoint、Reliability、共通Cross-fit、Structure Validation Debtを測定・終端化する版である。

## 1. 変更目的

v0.3では、固定Nicheを持たないGeneric Agentから異なる方針が生まれ、高レバレッジな構造仮説、動的Maturation Fork、Validation Debt、Semantic Diversity、Resource-safeな逐次実行、Candidate/OOF/Submission生成を確認した。

一方、次は未確認である。

- Locked CandidateがHidden/Private性能を改善したか
- 自発的な構造仮説を正しく検証してTerminal判定できるか
- Semantic DiversityがPredictive Diversityへ変換されたか
- 固定Nicheのv0.2よりGeneric Dynamic Structureのv0.3が優れるか

したがって、同じAgentへCycleを追加せず、測定と既存Debtの終了を優先する。

## 2. 実行順序と適応禁止

1. 現在のLocked Submissionを内容SHA付きで一括凍結する
2. 凍結済みBatchだけをLate Submission endpointへ提出する
3. 新しいRun RootでClean Replayを行う
4. Full Common First-level Cross-fitを3 Seedで行う
5. Island 01 Payment-process Validation DebtをTerminal化する
6. Representation × Learner Transfer Matrixを行う
7. Stagnation / Predictive Diversity Debtを判定する
8. 前項まで合格後にv0.2/v0.3/改良版をMatched-budget比較する

Leaderboard結果を見て提出Candidateを追加、差替え、再重み付けしてはならない。

## 3. Frozen Primary Endpoint Batch

次の順序、内容SHA、用途を採点前に固定する。

| ID | Candidate | 用途 |
| --- | --- | --- |
| 01 | Canonical Baseline | 基準 |
| 02 | v0.2 Corrected Locked Ensemble | 固定Niche方式 |
| 03 | v0.3初回Locked 01/02 Blend | Cycle 1時点 |
| 04 | v0.3 Cycle 2–4 Locked Island 01 | Adaptive探索後 |

全提出は506,691行、`TransactionID,isFraud`の厳密な列契約、TransactionID一意性、非欠損有限確率、内容SHAを満たすことを凍結Gateとする。凍結マニフェストはCandidate集合と順序を含むdeterministic hashを持つ。`--submit`は既存の凍結マニフェストしか受け付けず、提出直前に全ArtifactのSHAを再検証する。

記録項目はPublic/Private AUC、全Leaderboardを取得できる場合のPublic/Private rank相当、各CandidateのLocal forward AUC、Frozen Batch内順位、Local→Private Spearman順位整合性とする。

Competition終了後のLate Submissionは賞、正式順位、当時の競技成績を表さない。事後のHidden/Private Endpointとしてのみ扱う。また既存CandidateはSample、探索Budget、Local protocolが異なるため、このBatchだけでv0.2対v0.3の公平な優劣を結論しない。

## 4. Full Common First-level Cross-fit

対象は次の4 Representationとする。

- Canonical Base
- Island 01 Cycle 4
- Island 02 Cycle 2
- Island 03 Cycle 2

共通条件は全590,540 train rows、3つの同一Expanding Forward Fold、同一Time Gap、同一OOF Row、同一Seed Set（最低3）、Fold内Feature Fit、同一coarse Known/New/Questionable slice、同一Metric provenanceである。coarse client sliceは評価用Proxyであり、Validated Client Identityとは呼ばない。

必須出力は共通Fold Assignment、全Seed OOF、Mean/Fold/Seed AUC、Rank Stability、Residual/Prediction Correlation、Residual Covariance Effective Rank、Nested Marginal AUC/MSE Gain、Slice別Complementarityである。

次をすべて満たす場合、Predictive Collapseの証拠を強める。

```text
Residual Effective Rank < 1.2
Mean Residual Correlation > 0.95
Nested Ensemble AUC Gain <= 0
```

## 5. Representation × Learner Transfer Matrix

Predictive Collapseの原因を、モデルFamily不足と表現情報の同一性へ分解する。Acceptanceの数合わせを目的にモデルを追加してはならない。

| Representation | LightGBM | CatBoost | 単純モデル |
| --- | ---: | ---: | ---: |
| Canonical Base | 必須 | 必須 | Logistic SGD |
| Island 01 | 必須 | 必須 | 任意 |
| Island 02 | 必須 | 必須 | 任意 |
| Island 03 | 必須 | 必須 | 任意 |

全セルは共通Cross-fitを使用する。異LearnerでEffective Rankが上がる場合はModel-family Collapse、上がらない場合はRepresentation Collapseを主要因とする。Island 01のGainが複数LearnerへTransferしても、それだけでPayment-process構造妥当性をPassさせない。

## 6. Island 01 Structure Validation Debt

対象仮説は、Amount residueが持続的Payment-processを表すという主張である。現在の分類は`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`であり、Confirmed Factとして共有してはならない。

### 6.1 Matched Null

ProductCD、Time bin、Amount magnitude、Decimal-resolution分布、Missingness densityを可能な範囲で保持し、Payment-process linkageを破壊する。最低20反復とする。ただし事前登録済みSequential Futility Ruleが、実CandidateがNull 95%点を上回る事後確率を十分低いと判定した場合は早期終了できる。

Sequential判定は、1回のMatched NullがReal Gain以上となる確率を`p`とし、Passに必要な`p < 0.05`のBeta-Binomial posterior probabilityが0.05未満になったとき`structure_unsupported_by_matched_null`とする。Resource FailureはNull結果へ数えない。

### 6.2 独立含意・再現・Adoption

Null Gateを通過した場合のみ、次を継続する。

- Product/Time Contextを跨ぐResidue構造
- 生成に未使用のPayment属性との整合性
- Process cluster別Calibration/Fraud mechanism
- 3 Horizon × 3 Seed × 複数Product/Time Context
- Validation、Routing、Calibration、Target decomposition、Aggregation、Shift modelのいずれかの改善

Null Gateでsequential futilityとなった場合は`waived_by_futility`、20反復完了後にGate不合格となった場合は`waived_by_failed_prerequisite`として後続の独立含意、multi-context、adoptionを終了する。肯定的証拠がないままPassしたことにはしない。予測Gainが再現済みなら最終分類は`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`、再現しなければ`FALSIFIED`、検出力不足なら`INCONCLUSIVE`とする。

Debtの`RESOLVED`は全Requirementが処理済みという意味であり、構造妥当性Passを意味しない。各Requirementは`passed`、`failed`、`waived_by_futility`、`waived_by_failed_prerequisite`、`inconclusive`のOutcomeを保持する。

## 7. Exploration StagnationとPredictive Collapse

Semantic Collapseとは独立に次を判定する。

### Exploration Stagnation

次のすべてが2 Cycle連続した場合に発火する。

- QD Occupancyが増えない
- Validated Structureが増えない
- Accepted CandidateのPrimary Metricが改善しない
- Validation Debtが減らない

### Predictive Collapse

共通Cross-fit Candidateが3件以上あり、Effective Rank < 1.2、Mean Residual Correlation > 0.95、Nested Ensemble AUC Gain <= 0をすべて満たす場合に発火する。

Controllerは具体的なFeatureやModelを指定しない。Agentへ、既存Archiveと異なる誤りを生むData SliceとMechanismの事前登録を要求し、Predictive Diversity Debtを起票する。DebtはQuality Floorを満たし、既存Poolより低いResidual Correlation、またはNested Ensembleで正のMarginal AUC Gainを示した場合だけ閉じる。

## 8. Acceptanceの4層化

| 層 | 判定対象 | v0.3開始時点 |
| --- | --- | --- |
| Control-plane | Generic Agent、Isolation、Semantic Diversity、Resource Safety、Artifact、Candidate、Final Lock | Pass |
| Dynamic Structure Mechanism | 自発登録、Leverage、Fork、Debt、非共有、Terminal Promotion | Partial Pass |
| IEEE-CIS Capability | Validated Client Proxy、UID Aggregate、Known/New、2 Model Family、OOF、Ensemble | Fail |
| Primary Endpoint | Locked Private/Hidden、Matched Baseline、Multi-seed、複数Competition | Unmeasured |

Generic C-liteのStructure Discovery成功条件は「Validated High-leverage Structureが1件以上」である。Validated behavioral client proxyとfold-safe UID aggregateはIEEE-CIS固有のCritical Discovery Oracleとして別に保持し、Agentへ通知しない。

## 9. Clean Replay Reliability Gate

完全に新しいWorktreeとRun RootでCold-start Replayする。次を必須とする。

- Canonical Dataset Hash Helper
- Sampling時もTest全件を要求するSentinel
- Candidate Schema/Preflight SDK
- OOFとFold Assignmentの一意・一致検査
- Submission/Test Predictionの506,691行検査
- First-attempt Valid Artifact Rate >= 95%
- Resource Failure Rate <= 5%
- OOF Honesty Gate = Pass

Retry後の成功率でFirst-attempt率を置換してはならない。Reliability Gate未通過時は研究方式の比較へ進めない。

## 10. Matched-budget比較

前項まで完了後、次を比較する。

```text
Arm A: v0.2 Fixed Epistemic Niche
Arm B: v0.3 Generic Dynamic Structure
Arm C: v0.3 + Stagnation / Predictive Diversity Debt
```

Base Commit、LLM Version、Agent数、Cycle、Token/CPU/GPU/Wall-clock Budget、Dataset、Artifact Contract、Common Cross-fit、Seed、Submission数を一致させる。Primary EndpointはLocked Private/Hidden AUCとし、Validated Structure数、False Promotion率、Validation時間、Semantic Effective Count、Implementation Diversity、Residual Effective Rank、Marginal Ensemble Gain、Completion率、CostをSecondaryとする。

Arm Cはv0.4候補であり、本v0.3.1の測定結果を確認する前にDefaultへ昇格しない。

## 11. 今すぐ禁止する操作

- 同じ3 AgentへCycle 5以降を追加する
- Agent数だけを増やす
- Payment-processをConfirmed Structureとして配信する
- UID探索をControllerから指示する
- AcceptanceのためだけにModel Familyを増やす
- 狭いOOF IntersectionだけでPredictive Collapseを確定する
- Semantic Signature数を探索成功の主指標にする
- Leaderboard Scoreを見ながらCandidateを逐次変更する

## 12. 実装対応表

| 要件 | 実装 |
| --- | --- |
| Frozen batch / SHA / Local→Private | `evaluation.primary_endpoint`、`evaluate_ieee_cis_v031_primary_endpoint.py` |
| 4層Acceptance | `evaluation.acceptance` |
| Stagnation / Predictive Debt | `controller.stagnation` |
| Sequential Futility / Terminal判定 | `controller.structure_validation` |
| Debt Requirement Outcome | `StructureValidationDebt.resolution_outcomes` |
| Canonical Hash / Sentinel / OOF honesty | `plugins.ieee_cis_artifacts` |
| Full Common Cross-fit / Learner Matrix | `run_ieee_cis_v031_common_crossfit.py` |
