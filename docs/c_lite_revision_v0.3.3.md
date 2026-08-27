# Epistemic Research Loop v0.3.3 変更仕様

## 1. 位置づけ

**名称:** v0.3.3 — Incremental Value over Strong QD Verification

v0.3.3は探索機能の追加版ではない。v0.3.2で確認した「補完CandidateがLocked EnsembleとしてPrivate AUCを改善した」という結果を保持したまま、Full System Cの追加価値をStrong QD（B）およびPredictive QD（B+）から分離する評価版である。

IEEE-CISのv0.3.2 Private結果は研究上の結論にだけ利用し、Feature、Model、Slice、Ensemble Weightの追加調整には利用しない。

## 2. v0.3.2から継承する観測

| Output | Local AUC | Private AUC | Archive Bestとの差 |
| --- | ---: | ---: | ---: |
| Archive Best | 0.902963 | 0.909654 | 0 |
| W02 Single | 0.909749 | 0.899993 | -0.009661 |
| Locked Ensemble | 0.917213 | 0.914784 | +0.005130 |

Local Ensemble Gain `+0.007465`の一部はPrivateへ転送した。一方、W02単体のLocal順位はPrivateで逆転した。この結果は次の二軸を分けて扱う根拠とする。

```text
Standalone Utility != Ensemble Marginal Utility
```

## 3. Acceptanceの分解

単一の`Primary Hidden Endpoint`を廃止し、次を独立に記録する。

| Acceptance | v0.3.3開始時点 |
| --- | --- |
| Locked portfolio gain vs previous Archive | PASS |
| W02 standalone Hidden transfer | FAIL |
| Ensemble Hidden transfer | PASS |
| Local candidate-ranking fidelity | PARTIAL PASS |
| Quality-conditioned predictive diversity | PASS |
| Archive-wide predictive breadth | PARTIAL、非Blocking |
| Mechanism attribution | PARTIAL |
| Structural falsification | PASS |
| True structure discovery | PARTIAL PASS |
| System C vs B | UNMEASURED |
| System C vs B+ | UNMEASURED |

`candidate_level_transfer`は「候補が単体で勝った」という意味には使用しない。W02の単体転送は明示的にFAIL、候補の補完性を利用したPortfolio転送はPASSとする。

## 4. Validation Fidelity Debt

```yaml
validation_fidelity_debt:
  VF_1_candidate_ranking:
    status: OPEN
  VF_2_ensemble_transfer:
    status: PROVISIONAL_PASS
  VF_3_private_rank_calibration:
    status: PARTIAL
```

Final Selectorは単体AUCだけでなく、次を記録する。

* Horizon間の順位安定性
* Leave-one-horizon-out Selection Regret
* Seed安定性
* Slice別Complementarity
* Ensemble Weight安定性

## 5. Predictive Diversity Debtの修正

`PD-2 Archive-wide Predictive Breadth`は診断専用とする。

```yaml
PD_2_archive_wide_breadth:
  effective_rank: 1.116561
  pilot_threshold: 1.2
  status: PARTIAL
  blocking: false
  purpose: diagnostic_only
```

Effective Rankが1.2未満でも、それだけでCandidate追加を強制しない。Final判断はNested/Hidden Marginal AUC Gain、Seed/Horizon安定性、Quality Floor、Artifact、Leakageを優先する。

## 6. Mechanism Attribution Calibration

Candidate生成前に、各Componentについて以下を事前登録する。

* 効果の符号
* 効果の予測範囲
* 主要因の順位
* 最も強く効くと予測するSlice
* Learner間Transfer

W02の観測は、Missingness Topologyが両Learnerで正だが、Category Hashが主要因だった。このため分類は`USEFUL_REPRESENTATION_WITH_PREREGISTERED_SLICE_SUPPORT`のままとし、Mechanism AttributionはPARTIALとする。W02を構造仮説へ遡及昇格しない。

## 7. Structure Promotion Gate v2

Seed単位の結果は次のEvidence状態だけを持つ。

```text
SUPPORTING_EVIDENCE
CONTRADICTING_EVIDENCE
INCONCLUSIVE
```

Seed単位ではTerminal Promotionを行わない。`VALIDATED_STRUCTURE`はRun集約でのみ決定し、以下を要求する。

1. 3 Seed以上
2. Full aggregateがPass
3. Leave-one-seed-outの全ケースがPass
4. Threshold調整用Control FamilyとHeld-out評価用Control Familyが分離
5. Held-out Positive ControlをPromotion
6. Held-out Negative ControlをReject

単一GeneratorのSeed追加だけで構造発見能力を完全Passにはしない。Control Familyはlatent entity、temporal regime、observation process、routing subpopulation等へ拡張し、Threshold調整用と最終評価用を分離する。

## 8. B / B+ / C Arm

### System B — Strong QD

Performance、Semantic Novelty、Implementation Diversity、OOF Error Diversity、Candidate Archiveを使用する。Explicit Hypothesis、Predictive-slice Preregistration、Structure Maturation、Falsifier、Belief Updateは使用しない。

### System B+ — Predictive QD

Bに、Error Slice、Prediction-difference Mechanism、Predictive Diversity Debt、Slice別OOF比較を追加する。Structural Hypothesis Lifecycle、Posterior、Null/Skeptic Fork、Structure Promotionは使用しない。

### System C — Full v0.3.2

B+にAgent-local Hypothesis Registry、Structural Leverage、Structure Maturation、Null/Skeptic、Validation Debt、Falsification、Belief Updateを追加する。

各Armは12 Seed、合計36 Outputとする。同じSeed集合を使用し、実行順はSeedごとのB→B+→C Round-robinとする。Private ScoreはRun中に公開しない。

## 9. Resource MeteringとHard Budget

比較単位はExperiment件数ではなく、実測Resourceとする。

* cgroup v2 `cpu.stat`によるProcess-tree CPU秒
* `memory.current` / `memory.peak`
* LLM Token
* Wall-clock
* 固定CPU setとRAM上限
* `OMP_NUM_THREADS=2`
* `MKL_NUM_THREADS=2`
* `OPENBLAS_NUM_THREADS=2`
* `NUMEXPR_NUM_THREADS=2`

次Runの予約Costが、Finalization Reserveを除く残予算を超える場合は実行しない。Structure Maturation CPU、Candidate CPU、Falsificationで回避した誤判断、最終Privateへの正味寄与を別々に記録する。

Live Primary比較では各Arm専用のcgroup v2 nodeを必須とする。共有root cgroup上の値は他Processを含み得るため、Parser/PolicyのPreflightには利用できるが、Primary比較の実測値としては採用しない。

## 10. Sealed Private Protocol

Private照会前に次をHash固定する。

* Arm Policy
* Prompt
* Budget
* Acceptance Rule
* 36 Candidate commit
* Feature Manifest
* Fold Plan
* Selection Rule
* Test Prediction
* Submission

36件すべてが揃い、実測CPU・Token・Wall-clockが一致し、Artifact Gateを通った場合のみBatchをLockする。部分BatchのPrivate照会は禁止する。

Primaryは以下とする。

```text
PrivateAUC_C - PrivateAUC_B+
PrivateAUC_C - PrivateAUC_B
```

Secondaryとして`PrivateAUC_B+ - PrivateAUC_B`、CV→Private順位相関、Validated Structure数、False Promotion率、Mechanism Calibration、Nested Gain、CPU/Token/Wall-clock、Invalid Artifact率、Opportunity Costを記録する。

## 11. 判定

* `C > B+`かつ同一Budget・複数Seedで再現し、Structure/FalsificationによるDecision改善が媒介する場合はFull Cを採用する。
* `B+ > B`かつ`C ≈ B+`なら通常探索をB+とし、高レバレッジ構造仮説の発生時だけC Forkを起動する。
* `B+ > C`ならStructure Layerを標準探索から外し、監査・安全用途に限定する。
* `B ≈ B+ ≈ C`ならStrong QDで十分と判定する。
* LocalではB+/Cが優位だがPrivateでBが優位なら、探索よりValidation Worldを先に修正する。

## 12. 非目標

v0.3.3では次を行わない。

* Agent数・Cycle数だけを増やす
* Effective Rankが1.2を超えるまでCandidateを追加する
* W02を問題構造としてPromotionする
* Category HashをIEEE-CIS固有の標準Featureにする
* Privateを見ながらWeightを調整する
* Model Family数をAcceptanceのためだけに増やす
* 3 SeedだけでStructure Controlを完全Passとする
* Requested Resourceだけを揃えて実測CPU不一致を許容する

## 13. 実装対応

| 要件 | 実装 |
| --- | --- |
| Acceptance / Debt分解 | `evaluation/v033.py` |
| Mechanism Calibration | `evaluation/v033.py` |
| 36 Output Sealed Batch | `evaluation/v033.py` |
| Private利用制限 | `evaluation/v033.py` |
| cgroup v2 Meter / Hard Budget | `controller/resource_metering.py` |
| Promotion Gate v2 | `controller/structure_validation.py` |
| B/B+/C Runner | `benchmark/v033_matched.py` |
| 実行設定 | `configs/benchmarks/v033_b_bplus_c_36run.yaml` |
| Preflight | `scripts/verify_v033_incremental_value.py` |
