# Epistemic Research Loop C-lite v0.3.7 仕様書

## Agent Reproducibility, Blind-spot Diversity, and Falsification Qualification

- 対象: Blind Structure Control Suite
- 構成: 4 New Suites × 3 Generic Agents × 2 Sampling Conditions
- 固定Niche: なし
- Online Cross-agent共有: なし
- Primary: Agent-level TSDR / TSRR / FSPR / USTR / Calibration
- Secondary: Shared Blind-spot、Lineage継続、Transfer、Population補完性
- ステータス: v0.3.6後のEngineering Pilot

本書はv0.3.6の差分仕様である。矛盾する場合は本書を優先する。

## 1. 目的

v0.3.6のPopulation UnionはTSDR 0.75、TSRR 1.00、FSPR 0、USTR 0.875だったが、Persistent-unitを全Agentが見逃し、Negative棄却が一Agentへ偏った。v0.3.7ではPopulation Unionを主評価にせず、次を分離する。

1. Agent単体の反復可能な研究能力
2. Agent間のDiscovery/Rejection Complementarity
3. 全Agentに共通するBlind Spot
4. Prompt salienceとLineage選択Policyの効果
5. Structure DiscoveryとDownstream Transfer

## 2. Suite Lock

Prompt、Policy、Promotion Gateを変更する前に4 Suiteを生成しLockする。各SuiteはPositive/Negative各6 Pack、各3 Contextを持つ。Agent-visible viewはOpaque Pack/Context ID、列名、列順、行順をAgentごとに変え、Controller Truth、Family、Polarity、Generator Seed、Confirmation/Transfer labelを公開しない。

Primary Matrixは次とする。

```text
4 Suites × 3 Agent identities × 2 sampling conditions = 24 evaluations
```

同一LLM sessionが複数Suiteを処理した場合は、完全独立24 Runとは表現せず、Trajectory数とSuite評価数を分けて報告する。

## 3. Persistent-unit Ladder

Controller-onlyで次の4 Positiveと、表面統計を合わせた4 Negativeを生成する。

| Level | Positive | 主な難しさ |
| --- | --- | --- |
| L1 | Clear persistence | 強い反復と履歴効果 |
| L2 | Noisy proxy | 欠損・複数Proxy・frequency decoy |
| L3 | Delayed history | 複数過去行の累積効果 |
| L4 | Compositional persistence | persistent link × time × frequency |

発見には「Entity」という語を要求しない。Rowより上位の反復単位、history/link intervention、Positive support、対応NegativeのEvidence-based rejectionを要求する。

## 4. Compositional Controls

Ladder以外に次を含め、Structure existenceとPredictive utilityを分離する。

- Observation process × routing
- Stable structure without predictive utility
- Useful encoding without structure
- Random routing surface

## 5. Prompt Ablation

### P0

v0.3.6 Generic Promptを維持する。

### P1

P0へ次の一文だけを加える。

> 現在の定式化が暗黙に置いている独立性、観測単位、定常性、単一生成機構のうち、少なくとも1つを疑う仮説を生成してよい。

具体的なStructure、Feature、Operator名は与えない。Persistent TSDRだけでなく、全Family TSDR、TSRR、FSPR、Blind-spot、Research Diversityを評価する。

## 6. Lineage Selection Ablation

### S0 Deterministic Best Utility

各Cycleで推定Utility最大のLineageを選ぶ。

### S1 Posterior Commit

Utility posteriorからLineageをSamplingし、最低2 Cycleまたは明示Falsificationまで追跡する。

### S2 Two-hit Maturation

Novel Lineageを一度の弱い結果で削除せず、独立含意、Matched Null、Cross-context、実装可能性のいずれかで明示終了するまでFollow-upを一度許可する。

P0/P1とS0/S1/S2はSuiteごとのLatin-squareで配分する。

## 7. Failure Trace

Persistent missを次へ分ける。

```text
A hypothesis generation
B discriminating-test design
C implementation
D evidence or promotion
```

Agent自己申告とController観測を分離する。ControllerはResearch-vs-null、Independent implication、Confirmation、LOCO、Matched Negative、Promotionを再判定し、最初の客観Failureを保存する。

## 8. Full-refit Sequential Null

各ReplicateでStructure-destroying permutation、Feature再生成、Fold-local fit、Model再学習、OOF評価を行う。5回ごとにFutility/Early-supportを評価し、最大30回とする。

NullはGroup size、frequency、time bin、missingness、marginal feature、class balanceを保持し、persistent link、regime link、conditional routing、observation coherenceを破壊する。

Pilot ContractはAgentのfull-refit宣言とgain列を必須にする。Confirmatoryでは各Replicateのpermutation、feature、fold、model-fit、OOF hashを必須にし、自己申告だけでFull-refit済みとはしない。

## 9. ConfidenceとCalibration

Confidenceを分解する。

```yaml
confidence:
  p_structure_exists: 0..1
  p_evidence_sufficient: 0..1
  p_actionable: 0..1
  p_positive_transfer: 0..1
```

- C0: Raw Agent confidence
- C1: Development-only isotonic calibration
- C2: Calibration-adjusted evidence requirement

Qualification TruthはRun終了までCalibrationへ使用しない。C1/C2を実行しない場合はUNMEASUREDと明記する。

## 10. DiscoveryとTransferの分離

```text
Research 60%
Structure Confirmation 20%
Transfer Sealed 20%
```

Agentは両Hidden labelを見ない。Structure Confirmationは事前LockしたTranslationだけを評価し、Hidden上の事後最大化を禁止する。Transfer SealedはStructureの存在判定へ使用しない。

Terminal状態は次とする。

- VALIDATED_ACTIONABLE_TRANSFERRED
- VALIDATED_ACTIONABLE_NOT_TRANSFERRED
- VALIDATED_NON_ACTIONABLE
- USEFUL_ENCODING_UNVALIDATED
- FALSIFIED
- INCONCLUSIVE

Validated Actionableでは2種類以上のTranslationを生成し、Structure-free Controlと比較する。

## 11. Evidence-based Rejection

NegativeのTSRR creditには、自然言語上の`FALSIFIED`だけでなく次を要求する。

- full-refit nullを棄却できない
- independent implicationが成立しない
- locked Confirmationで再現しない
- causal safetyを満たす

Useful encodingが存在するNegativeは`USEFUL_ENCODING_UNVALIDATED`へ分類できるが、Structure promotionしてはならない。

## 12. LockとBlindness

全24 Outputをhash-lockしてからTruth keyを読む。Finalizerは開封直前に次を再照合する。

- packet SHA256
- submission SHA256
- frozen Prompt SHA256
- encrypted Truth SHA256
- Suite/Run identity set

Truth、Family、Polarity、Sealed label、Reference operatorのAgent-visible leakageは0を要求する。Pilotは共有Host上のPath Policy隔離であり、ConfirmatoryはContainer mount隔離を要求する。

## 13. Metrics

- Agent-level TSDR / TSRR / FSPR / USTR / Resolution / Calibration
- Agent × Sampling condition aggregate
- Median/Worst Agent performance
- Wilson 95% interval（記述用。Pack相関を無視する限界を表示）
- Leave-one-agent-out TSRR
- Marginal Agent Contribution
- Shared Blind-spot Rate
- Discovery/Rejection Complementarity
- Persistent Ladder coverage
- IRD / Effective Family Count / Dominant Family Fraction
- EECR / Deep Lineage Completion / Premature Rejection
- Translation Success / Selection Regret

$$SBR=\frac{Suite\times Seedで全Agentが見逃したPositive}{全Positive}$$

$$DC=TSDR_{union}-\max_i TSDR_i$$

$$RC=TSRR_{union}-\max_i TSRR_i$$

$$MAC_i=Score(Population)-Score(Population\setminus Agent_i)$$

## 14. Engineering Gate

```text
Median Agent TSDR >= 0.50
Median Agent TSRR >= 0.67
All Agent FSPR <= 0.20
Shared Blind-spot Rate <= 0.20
Leave-one-agent-out TSRR >= 0.67
USTR >= 0.50
Median Structure Gain > 0
Brier <= 0.20
ECE <= 0.20
Persistent Level >= 3/4
Persistent discovery by >= 2 Agents
```

個体能力を通過するまでCommunication M1–M4、Agent数/Cycle数のScaling、IEEE-CIS tuningを先行しない。

## 15. 判定範囲

本PilotはSynthetic Agent qualificationであり、IEEE-CIS Hidden改善、未使用Real Benchmark一般化、Communicationの効果を測らない。Full-refit provenance、LLM session independence、Container isolationが不足する場合はConfirmatory claimを行わない。
