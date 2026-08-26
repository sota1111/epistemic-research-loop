# Epistemic Research Loop C-lite v0.3.2 Primary Endpoint and Causal Attribution Verification

**文書バージョン:** 0.3.2  
**修正対象:** v0.3.1 Measurement and Debt Closure  
**対象検証:** IEEE-CIS Fraud Detection  
**ステータス:** 実験用差分仕様

本文書と以前の仕様が矛盾する場合は本文書を優先する。v0.3.2ではControl Plane、Artifact Contract、Agent数、探索Cycleを変更しない。変更対象はPrimary Endpoint、W02因果分解、Acceptance/Debt分解、B/B+/C Arm switch、機会費用会計、Structure Controlに限定する。

## 1. AcceptanceとPredictive Diversity Debt

Predictive Diversity Debtを次の3件へ分ける。

| Debt | 意味 | v0.3.2開始時点 |
| --- | --- | --- |
| PD-1 Quality Complementary Candidate | Quality floorを維持する補完Candidate | Resolved |
| PD-2 Archive-wide Predictive Breadth | Archive全体のResidual Effective Rank | Partial。1.116561 < 1.2 |
| PD-3 Hidden Transfer | Local補完性のPrivate/Hidden転送 | Unmeasured |

PD-1がResolvedでもPD-2、PD-3を自動的にResolvedにしない。全体AcceptanceはControl Plane、Artifact Reliability、Common Cross-fit、Semantic Diversity、Quality-conditioned Predictive Diversity、Archive-wide Breadth、Structural Falsification、True Structure Discovery、Strong QDに対する増分価値、Primary Hidden Endpointを独立表示する。

## 2. Hidden Endpoint Preregistration

スコア照会前に次の順序で一括凍結する。

1. Canonical Baseline
2. v0.3.1 Archive Best Single
3. Workstream 02 Single
4. Archive + Workstream 02 Nested Ensemble

候補commit、feature manifest、common fold plan、ensemble weights、test prediction、submission、selection ruleのSHA-256を固定する。Hidden結果を見た後の候補追加、差替え、再fit、weight変更は禁止する。Canonicalの既知Private scoreは参照値として再利用できるが、新規Candidateの提出順を変更しない。

Primary差分は次とする。

```text
delta_single   = PrivateAUC(W02) - PrivateAUC(ArchiveBest)
delta_ensemble = PrivateAUC(W02+Archive) - PrivateAUC(ArchiveBest)
```

Late Submissionは正式順位・賞の主張に使用しない。Kaggleの日次上限でBatchの一部しか提出できない場合、凍結Batchを変更せず未提出を`pending_external_quota`とし、PD-3は必要スコアが揃うまでUnmeasuredとする。

## 3. W02 Factorial Attribution

全590,540 train rows、354,324 common OOF rows、同一3 Forward Horizon、7日gap、Seed 17/42/20260826で次を逐次実行する。

| ID | Representation | Learner | Category hash |
| --- | --- | --- | --- |
| A | Canonical Base | LightGBM | Off |
| B | Canonical Base | ExtraTrees | Off |
| C | Missingness Topology | LightGBM | Off |
| D | Missingness Topology | ExtraTrees | Off |
| E | Missingness Topology | LightGBM | On |
| F | Missingness Topology | ExtraTrees | On |

全Common OOF、Identity absent、High V missingness、両者のintersectionで同じ差分を測る。Temporal block bootstrapにより差分の95%区間と正値確率を記録する。

```text
learner effect      = B - A
representation LGBM = C - A
representation ET   = D - B
interaction         = D - C - B + A
hash LGBM           = E - C
hash ET             = F - D
```

W02はAttribution後も直ちにStructural Hypothesisへ昇格しない。分類は`USEFUL_REPRESENTATION_WITH_PREREGISTERED_SLICE_SUPPORT`とする。Topologyが複数Learnerへ転送した場合だけ、観測regime仮説を新規Provisional Structureとして登録可能にする。

## 4. Candidate Eligibility

Standalone EligibilityとEnsemble Eligibilityを分離する。

StandaloneはArtifact、Leakage、OOF honesty、Seed stability、Quality floorを要求する。Ensemble専用ArchiveはArtifact、Leakage、OOF honesty、Seed stability、Nested leave-one-candidate-out gain、複数Horizonの方向安定性、fold weight非集中を要求し、単体Quality floorを必須にしない。

Workstream 03はSeed SD 0.02514により両方Failとする。Workstream 01の構造主張FalsifiedとPrediction Candidateの価値は別に判定する。

## 5. B / B+ / C

Arm switchは次を厳密に分離する。

- B: Performance、Semantic Novelty、Candidate Archive、OOF Error Diversity
- B+: BにError Slice/Mechanism事前登録とPredictive Diversity Debtを追加
- C: B+にAgent-local Hypothesis、Structure Maturation、Null/Skeptic、Validation Debt、Falsificationを追加

同一LLM、Agent数、Token、CPU/RAM/GPU、Wall-clock、Heavy compute、Common fold、Seed、最終提出数が一致しなければ`matched=false`とする。Declared budgetだけでなく実測使用量を比較する。Falsification時間はOpportunity CostとしてCandidate探索時間と分けて記録する。

既存のsealed synthetic catalogを使う試験はArm switchのPolicy preflightであり、IEEE-CIS上の増分価値を証明しない。Live LLM matched-budget runがない限り`incremental_value_over_strong_qd=UNMEASURED`を維持する。

## 6. Structure Positive / Negative Control

Positive ControlはAgent非公開の持続Entity、Entity別fraud mechanism、時間を跨ぐ履歴効果を持つ。Negative ControlはFrequency、Group Size、Missingness、Time、周辺Feature分布を保ち、持続Linkだけを破壊する。

Candidate groupingの発見はlatent IDとtargetを参照せず、Fold-safe history、20回linkage null、3 Horizon、3 Seed、未使用held-out属性のconstruct consistencyでGateする。

指標はPositive Acceptance Rate、Negative Rejection Rate、False Structure Promotion Rate、Validation Computeとする。PositiveをPassしNegativeをRejectできなければ、IEEE-CIS上の構造をValidatedと呼ばない。

## 7. 判定

- W02またはEnsembleがPrivateでArchive Bestを上回ればPD-3をResolvedとする。
- Effective Rankが1.2未満ならPD-2はPartialのままとする。
- B+ ≈ CかつB+ > BならPredictive-QDで十分という仮説を支持する。
- Cが追加Compute込みでB+を上回り、その差がStructure/FalsificationによるDecision改善で媒介された場合のみFull C-liteを支持する。
- Local Ensemble Gain > 0かつHidden Gain <= 0ならValidation Fidelityを先に再検討する。
- Synthetic preflightまたはControlだけでIEEE-CIS Hidden優位を主張しない。
