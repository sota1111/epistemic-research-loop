# Epistemic Research Loop C-lite システム仕様書

**文書バージョン:** 0.1
**対象リポジトリ:** `epistemic-research-loop`
**対象領域:** Kaggleコンペティション自律攻略
**実装方針:** Evolution / Quality-Diversity + Bayesian Experimental Design + Hypothesis Registry + Falsification + OOF Error Diversity
**ステータス:** 実装用初期仕様

> [!IMPORTANT]
> IEEE-CIS scaling検証後の差分仕様は
> [C-lite修正仕様書 v0.2](./c_lite_revision_v0.2.md) である。両文書が矛盾する場合はv0.2を優先する。

---

## 1. 仕様の位置づけ

本システムは、Active Inference全体を実装するものではない。

Active Inferenceから次の考え方を採用する。

- 現在の研究状態には観測できない不確実性が存在する
- 性能改善だけでなく、不確実性を減らす実験にも価値がある
- 仮説、観測、信念更新、将来の意思決定を明示的に管理する
- 望ましい研究状態と現在状態との差を研究行動の選択に利用する

一方、Expected Free Energyを含む完全な生成モデルは構築しない。Kaggle研究では実験結果の生成分布を正確にモデル化することが難しく、誤った生成モデルから精密なExpected Free Energyを計算すると、精密に誤った意思決定を行う危険がある。

そのため、本仕様では必要な機能を次の既存手法へ分解する。

| 必要機能                 | 採用する実装手段                        |
| ------------------------ | --------------------------------------- |
| 解法の性能最適化         | Evolutionary Search                     |
| 解法空間の多様性維持     | Quality-Diversity / MAP-Elites型Archive |
| 研究上の不確実性管理     | Explicit Hypothesis Registry            |
| 情報価値による実験選択   | Bayesian Experimental Design            |
| 仮説の反証               | Independent Falsifier                   |
| Ensemble価値の管理       | OOF Error Diversity                     |
| Validationの不確実性管理 | Validation World Posterior              |
| 全体予算配分             | Meta Controller                         |

この構成は、調査結果で提案された最小構成である「Strong Evolution/QD search、複数Validation World、明示的仮説、EIGまたはEVSI、独立Falsifier、OOF residual archive、Meta Controller」を実装対象とする。

---

## 2. システム目的

### 2.1 最終目的

固定された計算資源、LLMトークン、実験回数、提出回数の範囲内で、KaggleコンペティションのHidden TestまたはPrivate Leaderboardに対する最終性能を最大化する。

### 2.2 中間目的

本システムは、単純なLocal CV改善だけでなく、次の研究能力を持つ。

1. 信頼すべきValidation方式を調査する
2. データ生成過程に関する競合仮説を保持する
3. Train/Test shift、時間構造、Entity構造、重複、Leakage、Label noiseを調査する
4. 現在有力な仮説に対する反証実験を実行する
5. モデル、特徴量、表現、Validation、仮説の多様性を維持する
6. 単体性能が低くても、誤差が独立している候補を保持する
7. 研究行動が将来の意思決定へ与える価値を評価する
8. 仮説の確信度と実際の実験結果のCalibrationを測定する

### 2.3 成功条件

本システムの成功は、研究ノートの充実度ではなく、次の因果連鎖が成立することで判断する。

[
\text{Epistemic Experiment}
\rightarrow
\text{Better Belief}
\rightarrow
\text{Better Validation / Model Decision}
\rightarrow
\text{Higher Private Performance}
]

Critical Discovery数や仮説数が増えても、最終Private性能が改善しなければ、システムとして成功とは判定しない。

---

## 3. 非目的

本システムは、次を目的としない。

- Active Inferenceの理論的に忠実な再現
- Expected Free Energyの厳密計算
- Kaggle Winnerの手順を再生するRecipe Engine
- 「Adversarial Validationを実行したか」などの固定チェックリスト最適化
- 仮説数、情報量、Entropy Reduction自体の最大化
- Public Leaderboardへの逐次的な過適合
- LLMによる主観的な「情報価値が高い」という自己評価
- すべてのコンペで複雑なEnsembleを構築すること
- すべてのAgentを同じLocal CVへ収束させること

---

## 4. 基本原則

### 4.1 Strong Baseline First

System Cが比較すべき相手は単純なHill Climbingではなく、強いEvolutionary / Quality-Diversity Searchである。

Evolutionと多様性だけで十分である可能性を、最も強い帰無仮説として扱う。

### 4.2 Solution DiversityとEpistemic Diversityを分離する

**Solution Diversity**

- LightGBM
- Neural Network
- Transformer
- Linear Model
- Raw Feature
- Aggregate Feature

**Epistemic Diversity**

- Time shiftが主要因という仮説
- Entity composition shiftが主要因という仮説
- Label mechanismが主要因という仮説
- Duplicate leakageが主要因という仮説

異なるモデルを保持していても、全モデルが同じ誤ったRandom CVを信じている可能性がある。したがって、モデル空間だけでなくValidationやデータ生成過程に関する競合仮説を維持する。

### 4.3 仮説は反証可能にする

仮説には必ず次を含める。

- Claim
- Alternative hypotheses
- Prior probability
- Observable prediction
- Experiment result under each hypothesis
- Potential falsifier
- Downstream decision
- Posterior probability

### 4.4 実験前に予測を固定する

実験終了後に都合のよい解釈を生成することを防ぐため、実験開始前に予測分布、評価指標、判定基準を固定する。

### 4.5 Realized Information Gainを単独報酬にしない

Posteriorが大きく動いたこと自体は、正しい学習を意味しない。

次を併用する。

- Predictive log score
- Brier score
- Prediction interval coverage
- Replication consistency
- Held-out diagnostic performance
- Downstream decision change
- Private性能への寄与

調査結果でも、ノイズによって誤った確信を得た場合にRealized Information Gainが大きくなる危険が指摘されている。

### 4.6 Winner情報を実行時に使用しない

Winner Write-upは評価用のCritical Discovery定義にのみ使用する。

Agentには次を与えない。

- Winner Write-up
- Winner Notebook
- Winner固有のFeature名
- Competition固有の有名なMagic
- Critical Discovery一覧
- Private Leaderboard結果

---

## 5. システム全体構成

```text
                         ┌────────────────────────┐
                         │     Meta Controller     │
                         │ Budget / Policy / Stop  │
                         └────────────┬───────────┘
                                      │
             ┌────────────────────────┼────────────────────────┐
             │                        │                        │
             ▼                        ▼                        ▼
  ┌───────────────────┐   ┌────────────────────┐   ┌──────────────────┐
  │ Hypothesis Registry│   │ Validation Worlds  │   │    QD Archive    │
  │ Belief / Evidence  │   │ Posterior / Fidelity│  │ Solution / Error │
  └─────────┬─────────┘   └──────────┬─────────┘   └────────┬─────────┘
            │                         │                      │
            └──────────────┬──────────┴──────────────┬───────┘
                           ▼                         ▼
                  ┌─────────────────┐      ┌─────────────────────┐
                  │ Experiment BED  │      │ Experiment Proposers│
                  │ EIG / EVSI      │      │ Specialist Agents   │
                  └────────┬────────┘      └──────────┬──────────┘
                           └──────────────┬────────────┘
                                          ▼
                              ┌──────────────────────┐
                              │ Experiment Scheduler │
                              │ Cost / Risk / Queue  │
                              └──────────┬───────────┘
                                         ▼
                              ┌──────────────────────┐
                              │ Isolated Runner      │
                              │ Train / Evaluate     │
                              └──────────┬───────────┘
                                         ▼
                ┌────────────────────────┼────────────────────────┐
                ▼                        ▼                        ▼
       ┌────────────────┐      ┌──────────────────┐     ┌──────────────────┐
       │ Metric Evaluator│      │ Belief Updater   │     │ OOF Analyzer     │
       │ CV / Robustness │      │ Bayes / Calibration│    │ Residual Diversity│
       └────────┬───────┘      └─────────┬────────┘     └────────┬─────────┘
                └────────────────────────┼────────────────────────┘
                                         ▼
                              ┌──────────────────────┐
                              │ Finalizer / Ensemble │
                              │ Locked Submission    │
                              └──────────────────────┘
```

---

## 6. コンポーネント仕様

## 6.1 Meta Controller

### 責務

- 全体予算の管理
- Exploit、Explore、Epistemic Experimentへの予算配分
- 実験候補のUtility比較
- 実験Queueの生成
- 停止条件の判定
- 最終候補のLock
- System A/B/B+/Cの実行モード切替
- Agent間の情報公開範囲管理

### 入力

- Experiment Proposal一覧
- Hypothesis Registry
- Validation World Posterior
- QD Archive
- OOF Diversity
- 残予算
- 実験履歴
- Public Query残数

### 出力

- 次に実行するExperiment ID
- Experiment優先順位
- Agent別予算
- Stop / Continue判定
- Final Candidate Set

### 予算配分の初期値

以下は本仕様上の実装初期値であり、調査結果から直接導かれた固定値ではない。

| フェーズ     | Exploit | QD Explore | Epistemic |
| ------------ | ------: | ---------: | --------: |
| 初期構造調査 |     30% |        30% |       40% |
| 中盤探索     |     45% |        30% |       25% |
| 終盤最適化   |     65% |        25% |       10% |

配分は固定せず、次により動的に変更する。

- Validation World PosteriorのEntropy
- 上位候補間の順位不安定性
- Hypothesis Calibration
- Criticalな未解決仮説の有無
- QD Archiveの空Cell数
- 最終期限までの残り時間
- Ensemble候補のError Diversity

---

## 6.2 Hypothesis Registry

### 責務

研究上の仮説、競合仮説、予測、証拠、Posterior、反証状態を機械可読形式で保持する。

### Hypothesis Schema

```yaml
hypothesis:
  id: H-001
  category: validation
  claim: >
    Random CV is optimistic because the hidden test distribution
    represents a later time period.
  alternatives:
    - H-002
    - H-003

  prior:
    probability: 0.45
    source: weak_generic_prior
    strength: low

  predictions:
    - id: P-001
      observable: model_rank_correlation
      if_true:
        distribution: beta
        mean: 0.45
        confidence_interval: [0.20, 0.70]
      if_false:
        distribution: beta
        mean: 0.92
        confidence_interval: [0.82, 0.99]

  falsifiers:
    - multiple rolling backtests show rank correlation above 0.95
    - score variance does not increase under chronological split

  evidence:
    supports: []
    contradicts: []

  posterior:
    probability: 0.45
    updated_at: null
    calibration_score: null

  downstream_decisions:
    - select_primary_validation
    - suppress_unstable_frequency_features
    - change_model_ranking

  status: active
  owner_agent: validation-scientist
  created_cycle: 1
```

### Hypothesis Status

| Status         | 意味                           |
| -------------- | ------------------------------ |
| `draft`        | 予測または反証条件が未定義     |
| `active`       | 実験選択対象                   |
| `supported`    | Posteriorが支持閾値以上        |
| `weakened`     | 反証証拠が存在                 |
| `falsified`    | 事前定義した反証条件を満たした |
| `inconclusive` | 実験精度または再現性不足       |
| `superseded`   | より具体的な仮説へ置換         |
| `archived`     | 意思決定への影響がなくなった   |

### 必須制約

- 仮説にObservable Predictionがない場合、`active`へ遷移できない
- Alternative Hypothesisが存在しない場合、EIG対象にできない
- 実験後にPrediction Rangeを変更してはならない
- Posterior更新理由をEvidence IDへ紐付ける
- LLMの文章上の確信度だけでPosteriorを更新してはならない
- Winner由来Priorは初期実装では使用しない
- Winner corpusを使う場合もPrior strengthは`low`に固定する

仮説レジストリの基本構造は、調査結果で提示されたClaim、Prior、Predictions、Potential Falsifier、Evidence、Posterior、Downstream Implicationsを踏襲する。

---

## 6.3 Validation World Manager

### 目的

「どのLocal ValidationがHidden Testを最も適切に近似するか」を、単一の決め打ちではなく競合するValidation Worldとして管理する。

### 初期Validation World

```text
W_random
W_stratified
W_group
W_time
W_rolling_time
W_time_group
W_entity_seen
W_entity_unseen
W_adversarial_weighted
```

コンペのデータ構造に適用不可能なWorldは無効化できる。

### Validation World Schema

```yaml
validation_world:
  id: W-time-group
  split_type: time_group
  assumptions:
    - hidden test is later in time
    - rows from the same entity should not cross folds

  parameters:
    time_column: TransactionDT
    group_column: inferred_uid
    n_splits: 4
    gap_days: 30

  posterior_probability: 0.25

  diagnostics:
    model_rank_stability: null
    score_variance: null
    pseudo_future_accuracy: null
    train_valid_shift: null
    leakage_risk: null

  evidence_ids: []
  status: active
```

### Posterior更新に利用する観測

- Pseudo-future Backtest性能
- Split間のモデル順位相関
- Rank Reversal率
- Fold間Score variance
- Entity内・Entity外Generalization差
- 時間経過に対する性能劣化
- Adversarial Validation結果
- Public-like Queryとの整合性
- 重複・Leakage診断

### Validation Fidelity

Validation World (W) のFidelityを次で構成する。

[
F(W)=
w_1 \cdot \text{RankStability}

- ## w_2 \cdot \text{PseudoFutureAccuracy}

## w_3 \cdot \text{Variance}

w_4 \cdot \text{LeakageRisk}
]

最終的な候補評価では、単一CVではなくValidation World Posteriorを用いる。

[
\operatorname{ExpectedScore}(m)
===============================

\sum_W P(W \mid D)\cdot Score(m,W)
]

Validation WorldをRandom、Time、Group、Time+Group等の候補として保持し、そのPosteriorを管理する方針は、調査結果で最優先のInformation Gain対象として提案されている。

---

## 6.4 Experiment Proposal Manager

### Experiment分類

| 種別               | 主目的                               |
| ------------------ | ------------------------------------ |
| `exploit`          | 現在有力な解法の性能向上             |
| `solution_explore` | 新しいモデル・特徴量・表現領域の探索 |
| `epistemic`        | 競合仮説の識別                       |
| `falsification`    | 現在有力な仮説の反証                 |
| `robustness`       | Seed、Split、Perturbation耐性の検証  |
| `ensemble`         | Error DiversityまたはBlend性能の確認 |
| `replication`      | 重要実験の再現性確認                 |

### Experiment Schema

```yaml
experiment:
  id: E-001
  title: Compare random and rolling-time model rankings
  type: epistemic
  proposer_agent: validation-scientist

  competing_hypotheses:
    - H-001
    - H-002

  observable:
    name: spearman_rank_correlation
    unit: coefficient
    computation: compare candidate rankings across validation worlds

  preregistered_predictions:
    H-001:
      mean: 0.45
      interval: [0.20, 0.70]
    H-002:
      mean: 0.92
      interval: [0.82, 0.99]

  measurement_noise:
    method: bootstrap
    bootstrap_iterations: 1000

  decision_affected:
    - primary_validation_world
    - model_selection
    - feature_selection

  expected_cost:
    cpu_minutes: 30
    gpu_minutes: 0
    llm_tokens: 2000
    wall_clock_minutes: 35

  expected_values:
    performance_gain: 0.000
    eig: 0.21
    evsi: 0.13
    qd_contribution: 0.05
    robustness_gain: 0.08

  risk:
    invalid_result_probability: 0.05
    leakage_probability: 0.02

  execution:
    code_ref: null
    dataset_hash: null
    environment_hash: null
    random_seeds: [42, 43, 44]

  status: preregistered
```

### Experiment状態

```text
DRAFT
  ↓
PREREGISTERED
  ↓
SCORED
  ↓
QUEUED
  ↓
RUNNING
  ↓
SUCCEEDED / FAILED / INVALID
  ↓
VERIFIED
  ↓
BELIEF_UPDATED
  ↓
ARCHIVED
```

### 実行前Gate

次を満たさない実験は実行できない。

- Observableが定義されている
- 仮説別の予測が定義されている
- Cost estimateが存在する
- Downstream decisionが明示されている
- 成功・失敗・Inconclusive条件が定義されている
- Dataset snapshotとCode versionを固定できる
- 現在の残予算内で完了可能
- Private情報を参照していない

---

## 6.5 Bayesian Experimental Design Scorer

### Expected Information Gain

仮説集合 (H)、実験 (e)、観測結果 (Y_e) に対して、Expected Information Gainを次で計算する。

[
EIG(e)
======

\mathbb{E}_{y \sim p(y\mid e,D)}
\left[
D_{KL}
\left(
p(H\mid D,e,y)
\Vert
p(H\mid D)
\right)
\right]
]

これは仮説と実験結果のMutual Informationに相当する。

[
EIG(e)=I(H;Y_e\mid D)
]

### EIG計算方法

初期実装では仮説数を離散かつ少数に限定し、Monte Carloで近似する。

```text
for sample in 1..N:
    1. priorから仮説Hをsample
    2. p(y | H, e)から実験結果yをsample
    3. Bayes ruleでposteriorを更新
    4. KL(posterior || prior)を計算
EIG = KLの平均
```

### EIGを使用できない条件

以下の場合はEIGを無効とする。

- 仮説別の予測分布を定義できない
- 予測分布がLLMの単一主観値だけである
- 仮説間で予測分布がほぼ同一
- 観測Noiseが推定不能
- 仮説の意味が重複している
- 結果がDownstream decisionへ影響しない

### EVSI

KaggleではEntropyを減らすことより、将来の意思決定を改善する情報の方が重要である。

[
EVSI(e)
=======

\mathbb{E}\_y
\left[
\max_a
\mathbb{E}[U(a)\mid D,e,y]
\right]

---

\max_a
\mathbb{E}[U(a)\mid D]
]

初期実装では次のProxyを使用する。

[
\widehat{EVSI}(e)
=================

P(\text{decision changes}\mid e)
\times
E[\text{utility difference}]
]

### Experiment Utility

[
\begin{aligned}
U(e)={}&
\alpha \widehat{\Delta Performance}

- \beta \widehat{EVSI}(e)
- \gamma QDContribution(e) \
  &+
  \delta \widehat{\Delta Robustness}
  ***

## \eta Cost(e)

\rho Risk(e)
\end{aligned}
]

この構成は調査結果で示されたExperiment Utilityを基礎とする。

### Cost正規化

```text
NormalizedCost =
    cpu_weight × CPU minutes
  + gpu_weight × GPU minutes
  + token_weight × LLM tokens
  + wall_clock_weight × elapsed minutes
```

### Hard Gate

Utilityが高くても、次の場合は選択しない。

- Leakage Riskが閾値を超える
- 再現不能な外部データに依存する
- 期限内に完了しない
- 同等実験が既に存在する
- 事前登録が不完全
- Public Leaderboard Query上限を超える
- 仮説を区別する能力がない

---

## 6.6 Belief Updater

### 更新対象

- Hypothesis Posterior
- Validation World Posterior
- Performance Belief
- Shift Belief
- Label Noise Belief
- Entity Structure Belief
- Experiment Reliability
- Agent Calibration

### Posterior更新

仮説 (H_i) と観測 (y) に対して、

[
P(H_i\mid y,e,D)
================

\frac{P(y\mid H_i,e,D)P(H_i\mid D)}
{\sum_j P(y\mid H_j,e,D)P(H_j\mid D)}
]

### 更新制約

- 事前登録されたLikelihoodのみ使用する
- 実験後にLikelihoodを変更しない
- 再現性が低い実験はEvidence weightを下げる
- Multiple comparisonを記録する
- 同じデータから得た証拠を独立証拠として重複加算しない
- Failed Experimentは仮説反証として扱わない
- Invalid ExperimentはPosteriorを更新しない

### Evidence Weight

[
EvidenceWeight =
Reproducibility
\times
MeasurementQuality
\times
Independence
\times
ProtocolCompliance
]

### Calibration

Agentまたは仮説Categoryごとに次を記録する。

- Brier Score
- Log Loss
- 50% Prediction Interval Coverage
- 80% Prediction Interval Coverage
- 95% Prediction Interval Coverage
- Overconfidence Rate
- Underconfidence Rate

Calibrationが悪いAgentのPrior提案は縮小する。

---

## 6.7 Independent Falsifier

### 目的

現在Populationが最も信じている重要仮説を、最小コストで否定できる実験を提案する。

### 独立性要件

Falsifierは、対象仮説を提案したAgentとは別のContextで動作する。

Falsifierへ渡す情報は次に限定する。

- 仮説Claim
- Supporting Evidence
- Posterior
- Downstream Decisions
- 使用可能なデータ
- 残予算

元Agentの推論メモ、説得的文章、自己評価は渡さない。

### Falsification Priority

[
Priority(H)
===========

P(H)
\times
DecisionImpact(H)
\times
OverconfidenceRisk(H)
\times
Falsifiability(H)
]

### Falsifier出力

```yaml
falsification_proposal:
  target_hypothesis: H-017
  attack_surface:
    - entity leakage
    - unstable temporal aggregation

  minimal_experiment:
    description: compare seen-entity and unseen-entity performance
    estimated_cost: 20 cpu_minutes

  falsification_condition:
    metric: unseen_entity_auc_drop
    threshold: less_than_0.005

  alternative_explanation:
    hypothesis_id: H-024
```

Falsifierを解法Agentから分離し、現在最も信じられている仮説を否定することを独立Objectiveにする方針は、調査結果のAgent設計を踏襲する。

---

## 6.8 Quality-Diversity Archive

### 目的

単一CV最高候補のみを保持するのではなく、有意味に異なるSolutionおよびResearch Worldviewを保持する。

### Behavior Descriptor

初期Descriptorは次とする。

```yaml
descriptors:
  validation_type:
    - random
    - time
    - group
    - time_group

  model_family:
    - linear
    - gbdt
    - neural_network
    - transformer
    - other

  representation:
    - raw
    - aggregate
    - sequence
    - graph
    - image
    - text_sparse
    - embedding

  data_scope:
    - train_only
    - transductive
    - external_data

  shift_hypothesis:
    - none
    - temporal
    - entity
    - covariate
    - label
    - synthetic_test

  entity_hypothesis:
    - none
    - explicit
    - inferred
    - duplicate_graph

  error_profile:
    - global
    - subgroup_specialist
    - rare_class_specialist
    - temporal_specialist
```

### Archive Cell

各Cellには原則として以下を保持する。

- Best quality candidate
- Lowest-cost competitive candidate
- Highest-robustness candidate
- Highest error-diversity candidate

### Candidate Quality

[
Quality(m)
==========

## ExpectedHiddenScore(m)

## \lambda ScoreVariance(m)

## \mu Cost(m)

\nu LeakageRisk(m)
]

単一Random CV ScoreだけでCell winnerを決めない。

### B+ Mode

System B+では、Validation Type、Shift Hypothesis、Entity Hypothesis等をQD Descriptorへ含めるが、明示的Posterior、EIG、Belief Update、Falsifierは使用しない。

これにより、System Cの改善がBayesian/Epistemic機能によるものか、単にQD Descriptorを増やしたことによるものかを分離する。

---

## 6.9 OOF Error Diversity Analyzer

### 目的

単体CVが高い候補だけでなく、既存候補と異なる誤りを持つ候補を保持し、Ensemble価値を評価する。

### 保存データ

各Candidateについて、次を保存する。

```text
row_id
fold_id
target
oof_prediction
residual
timestamp
entity_id
subgroup_id
validation_world
candidate_id
```

### Error Diversity指標

#### Pairwise Residual Correlation

[
Corr\_{ij}
=========

corr(r_i,r_j)
]

#### Prediction Disagreement

分類の場合、

[
Disagreement\_{ij}
=================

\frac{1}{N}
\sum*n
\mathbb{1}
[\hat y*{i,n}\neq\hat y\_{j,n}]
]

#### Residual Covariance Effective Rank

Residual covariance matrix (\Sigma) の固有値を (\lambda_k) としたとき、

[
p_k=\frac{\lambda_k}{\sum_j\lambda_j}
]

[
EffectiveRank
=============

\exp\left(-\sum_k p_k \log p_k\right)
]

#### Marginal Ensemble Gain

[
MEG(m)
======

Score(Ensemble \cup m)-Score(Ensemble)
]

### Archive保持条件

単体性能がBest Candidateより低くても、次を満たす候補は保持する。

- Quality Floorを満たす
- Residual correlationが低い
- 特定Subgroupで一貫した改善がある
- Marginal Ensemble Gainが正
- 複数Validation Worldで効果が再現
- Leakage Riskが低い

### Ensemble構築制約

- OOF PredictionのみでWeightを学習する
- Blend Weight探索と評価を同一Foldで行わない
- Nested OOFまたはSecond-level holdoutを使用する
- Public LBだけでWeightを調整しない
- Error Diversityが高くても品質閾値未満の候補は除外する

調査結果では、Solution / Error DiversityをOOF residual correlation、prediction disagreement、covariance effective rank等で測定することが提案されている。

---

## 6.10 Experiment Runner

### 要件

- 各Experimentを独立ProcessまたはContainerで実行する
- Time limitを強制する
- CPU、GPU、RAM使用量を記録する
- Dataset snapshotを固定する
- Seedを記録する
- Git commit hashを記録する
- Environment lockfileを記録する
- 標準出力、標準エラー、Metric、Artifactを保存する
- 失敗時に他Experimentへ影響させない

### Experiment Manifest

```yaml
run_manifest:
  experiment_id: E-001
  system_mode: C
  git_commit: abc1234
  dataset_hash: sha256:...
  environment_hash: sha256:...
  started_at: 2026-08-25T22:00:00+09:00
  completed_at: null
  resources:
    cpu_cores: 8
    ram_gb: 32
    gpu: RTX3080Ti
    gpu_limit_minutes: 60
  seeds: [42, 43, 44]
```

### Failure分類

| Failure Type       | 処理                           |
| ------------------ | ------------------------------ |
| Code error         | Debug budget内で再実行         |
| Timeout            | Incompleteとして記録           |
| OOM                | Resource profile変更候補を生成 |
| Invalid metric     | Posterior更新禁止              |
| Data leakage       | Candidate失格                  |
| Non-reproducible   | Replication Queueへ追加        |
| Dependency error   | System reliability指標へ記録   |
| Submission invalid | Final candidateから除外        |

---

## 6.11 Finalizer

### 責務

- 最終候補をLockする
- Ensemble Candidateを生成する
- Hidden Evaluatorへ提出可能な形式へ変換する
- 最終Submissionを生成する
- 研究履歴を変更不能状態へする

### Final Candidate Utility

[
FinalUtility(m)
===============

ExpectedHiddenScore(m)

- \omega Robustness(m)
- ## \kappa EnsembleValue(m)

## \lambda Uncertainty(m)

\nu LeakageRisk(m)
]

### Lock条件

- Primary Validation Worldが確定または不確実性を明示
- Candidateの再現実行に成功
- Submission schema validationに成功
- OOFおよびFold assignmentが保存済み
- Dataset hashが一致
- Leakage checkに合格
- Public Query回数上限内
- Final candidate selection ruleを事前固定済み

---

## 7. Agent構成

| Agent                 | 主目的                                | 主要出力                   | 成功指標                 |
| --------------------- | ------------------------------------- | -------------------------- | ------------------------ |
| Validation Scientist  | 信頼すべきValidationを調査            | Validation World、Backtest | Fidelity、Rank Stability |
| DGP / Shift Scientist | Entity、Time、Shift、Duplicateを調査  | Structural Hypothesis      | Hypothesis Resolution    |
| Explorer              | 新しいSolution / Hypothesis領域を開拓 | Candidate、Descriptor      | QD Occupancy             |
| Falsifier             | 有力仮説を否定する                    | Falsification Experiment   | Falsification Coverage   |
| Feature Scientist     | Feature、Aggregation、Target変換      | Feature Candidate          | Performance + Coverage   |
| Model Scientist       | Model、Loss、Training探索             | Model Candidate            | Quality Frontier         |
| Error Scientist       | Subgroup、Residual、Failure分析       | Error Hypothesis           | Explained Residual       |
| Ensemble Scientist    | OOF多様性とBlend最適化                | Ensemble Candidate         | Marginal Ensemble Gain   |
| Meta Researcher       | 予算、信念、Archive全体管理           | Experiment Queue           | Final Utility            |

### Memory分離

Agent間の情報は次の3層に分ける。

#### Shared Empirical Facts

- 実行済みMetric
- Dataset statistics
- 確定したArtifact
- Experiment failure
- 再現可能な観測

#### Explicit Hypothesis Registry

- Claim
- Prior
- Prediction
- Evidence
- Posterior
- Falsifier

#### Private Working Hypotheses

- 各Agent固有の未検証アイデア
- 他Agentへ自動共有しない
- 実験提案時に必要部分のみRegistryへ昇格する

全Agentに同一の巨大Contextを渡すと仮説が収束しやすいため、Shared facts、Private hypotheses、Explicit registryを分離する。

---

## 8. Research State

システム全体の状態を次のVectorとして管理する。

```yaml
research_state:
  validation_fidelity:
    value: 0.62
    uncertainty: 0.18

  dgp_understanding:
    resolved_hypotheses: 3
    active_hypotheses: 7
    posterior_entropy: 1.31

  distribution_shift_understanding:
    value: 0.55
    uncertainty: 0.24

  entity_temporal_integrity:
    value: 0.48
    uncertainty: 0.30

  data_label_quality_understanding:
    value: 0.40
    uncertainty: 0.28

  error_understanding:
    explained_residual_ratio: 0.31

  hypothesis_coverage:
    occupied_taxonomy_cells: 8
    total_taxonomy_cells: 15

  hypothesis_calibration:
    brier_score: 0.19

  falsification_coverage:
    value: 0.44

  representation_coverage:
    qd_occupancy: 0.37

  solution_error_diversity:
    effective_rank: 4.2

  robustness:
    split_score_sd: 0.0031

  performance_belief:
    expected_score: 0.918
    credible_interval: [0.910, 0.924]
```

Preferred Research Stateは一点の正解状態ではなく、Competition Contextに依存する分布として扱う。

「Shiftが存在しないこと」を望ましい状態とするのではなく、「Shiftの原因とモデル順位への影響を根拠付きで理解していること」を望ましい状態とする。

---

## 9. 制御フロー

```text
INIT
  ↓
DATA_PROFILE
  ↓
BASELINE_BUILD
  ↓
INITIAL_VALIDATION_WORLDS
  ↓
INITIAL_HYPOTHESIS_GENERATION
  ↓
EXPERIMENT_PROPOSAL
  ↓
PREREGISTRATION
  ↓
EIG / EVSI / QD / COST SCORING
  ↓
META CONTROLLER SELECTION
  ↓
EXPERIMENT EXECUTION
  ↓
RESULT VERIFICATION
  ↓
BELIEF UPDATE
  ↓
QD ARCHIVE UPDATE
  ↓
OOF DIVERSITY UPDATE
  ↓
FALSIFICATION CHECK
  ↓
BUDGET / STOP CHECK
  ├─ Continue → EXPERIMENT_PROPOSAL
  └─ Stop     → FINAL ENSEMBLE
                    ↓
               LOCKED SUBMISSION
                    ↓
               EVALUATION REPORT
```

---

## 10. 停止条件

次のいずれかを満たした場合、通常の研究Loopを停止する。

- GPU Budgetを消費
- CPU Budgetを消費
- LLM Token Budgetを消費
- Wall-clock deadlineへ到達
- 最大Cycle数へ到達
- Public Query上限へ到達
- 有効なExperiment Proposalが存在しない
- 上位候補順位が連続Cycleで安定
- Expected Utilityが最低閾値未満
- 最終Submission生成に必要な残時間へ到達

### Early Stop禁止条件

以下が未解決の場合、性能収束だけを理由に早期停止しない。

- Validation World Posteriorが高Entropy
- 上位モデルの順位がSplit間で逆転
- Leakage Riskが高い
- 最有力仮説が未反証
- Final Candidateの再現に失敗
- OOF Artifactが欠損

---

## 11. System Mode

## 11.1 System A — KPI Hill Climbing

保持状態:

```text
best_solution
best_local_cv
experiment_history
```

実験選択:

[
e\_{t+1}
=======

\arg\max_e E[\Delta CV(e)]
]

CVが改善したBranchを保持する。

## 11.2 System B — Evolutionary Quality-Diversity

System Aに追加:

```text
population
solution descriptors
archive
mutation
crossover
novelty
QD contribution
```

Utility:

[
U_B(e)
======

\alpha \widehat{\Delta CV}

- ## \gamma QDContribution

\eta Cost
]

## 11.3 System B+ — Epistemic Descriptor QD

System BのDescriptorへ次を追加する。

```text
validation worldview
shift hypothesis
entity hypothesis
label-noise hypothesis
```

ただし次は持たない。

- Hypothesis Posterior
- EIG
- EVSI
- Belief Update
- Independent Falsifier

## 11.4 System C — C-lite

System B+に追加:

```text
hypothesis registry
belief posterior
validation-world posterior
EIG / EVSI
falsifier
calibration
belief update
OOF error archive
```

Utility:

[
U_C(e)
======

\alpha \widehat{\Delta CV}

- \beta EVSI
- \gamma QDContribution
- ## \delta RobustnessGain

## \eta Cost

\rho Risk
]

A/B/B+/Cの比較構成は、調査結果で提示された反証可能な比較設計を採用する。

---

## 12. ストレージ仕様

### 12.1 初期実装

| データ              | 保存方式                   |
| ------------------- | -------------------------- |
| Metadata            | SQLite                     |
| Hypothesis Registry | SQLite + YAML Export       |
| Experiment Manifest | JSON                       |
| Metrics             | SQLite / Parquet           |
| OOF Prediction      | Parquet                    |
| Model Artifact      | Local Object Directory     |
| Logs                | JSONL                      |
| Dataset Snapshot    | Read-only directory + Hash |
| QD Archive          | SQLite + Parquet           |
| Report              | Markdown / JSON            |

### 12.2 Artifact構成

```text
artifacts/
  runs/
    RUN-20260825-001/
      manifest.yaml
      hypotheses/
      experiments/
      candidates/
      oof/
      models/
      submissions/
      reports/
```

### 12.3 Content Addressing

Artifactは原則として次のHashで識別する。

```text
artifact_hash =
SHA256(
    code_commit
  + config
  + dataset_hash
  + environment_hash
  + random_seed
)
```

---

## 13. リポジトリ構成

```text
epistemic-research-loop/
├── README.md
├── pyproject.toml
├── uv.lock
├── configs/
│   ├── system_a.yaml
│   ├── system_b.yaml
│   ├── system_b_plus.yaml
│   ├── system_c.yaml
│   └── competitions/
├── schemas/
│   ├── hypothesis.schema.json
│   ├── experiment.schema.json
│   ├── validation_world.schema.json
│   └── candidate.schema.json
├── src/
│   └── epistemic_research_loop/
│       ├── cli.py
│       ├── orchestrator/
│       │   ├── meta_controller.py
│       │   ├── scheduler.py
│       │   └── stop_policy.py
│       ├── agents/
│       │   ├── validation_scientist.py
│       │   ├── dgp_scientist.py
│       │   ├── explorer.py
│       │   ├── falsifier.py
│       │   ├── feature_scientist.py
│       │   ├── model_scientist.py
│       │   ├── error_scientist.py
│       │   └── ensemble_scientist.py
│       ├── hypotheses/
│       │   ├── registry.py
│       │   ├── belief_update.py
│       │   └── calibration.py
│       ├── bed/
│       │   ├── eig.py
│       │   ├── evsi.py
│       │   └── utility.py
│       ├── validation/
│       │   ├── worlds.py
│       │   ├── splits.py
│       │   ├── fidelity.py
│       │   └── adversarial.py
│       ├── qd/
│       │   ├── archive.py
│       │   ├── descriptors.py
│       │   └── selection.py
│       ├── experiments/
│       │   ├── proposal.py
│       │   ├── preregistration.py
│       │   ├── runner.py
│       │   └── verifier.py
│       ├── oof/
│       │   ├── store.py
│       │   ├── residuals.py
│       │   ├── diversity.py
│       │   └── ensemble.py
│       ├── evaluation/
│       │   ├── metrics.py
│       │   ├── private_evaluator.py
│       │   ├── discovery_score.py
│       │   └── system_comparison.py
│       ├── storage/
│       │   ├── database.py
│       │   ├── artifacts.py
│       │   └── manifests.py
│       └── security/
│           ├── contamination.py
│           └── leakage.py
├── benchmarks/
│   ├── rossmann/
│   ├── ieee_cis/
│   └── airbus/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── benchmark/
└── artifacts/
```

---

## 14. CLI仕様

```bash
# コンペ環境を初期化
python -m epistemic_research_loop init \
  --competition configs/competitions/ieee_cis.yaml \
  --system-mode C

# Baselineを構築
python -m epistemic_research_loop baseline

# 1研究Cycle実行
python -m epistemic_research_loop run-cycle

# 指定回数実行
python -m epistemic_research_loop run \
  --max-cycles 10

# Hypothesis Registryを表示
python -m epistemic_research_loop hypotheses list

# 特定仮説の証拠を表示
python -m epistemic_research_loop hypotheses show H-001

# QD Archiveを表示
python -m epistemic_research_loop archive status

# OOF Error Diversityを計算
python -m epistemic_research_loop oof analyze

# 最終CandidateをLock
python -m epistemic_research_loop finalize

# System比較
python -m epistemic_research_loop benchmark \
  --systems A B B+ C \
  --seeds 10

# Component Ablation
python -m epistemic_research_loop ablation \
  --remove eig falsifier preferred-state
```

---

## 15. 設定ファイル例

```yaml
system:
  mode: C
  max_cycles: 10
  random_seed: 42

budget:
  wall_clock_minutes: 720
  cpu_minutes: 3000
  gpu_minutes: 600
  llm_input_tokens: 500000
  llm_output_tokens: 150000
  public_queries: 5
  final_submissions: 1

selection:
  weights:
    performance: 1.0
    evsi: 0.5
    qd: 0.3
    robustness: 0.2
    cost: 0.2
    risk: 0.5

  minimum_utility: 0.01
  max_epistemic_fraction: 0.40
  max_replication_fraction: 0.20

hypotheses:
  maximum_active: 30
  minimum_prior: 0.05
  maximum_prior: 0.80
  require_alternative: true
  require_falsifier: true
  calibration_enabled: true

validation:
  worlds:
    - random
    - time
    - group
    - time_group
  bootstrap_iterations: 1000
  rank_correlation: spearman

qd:
  maximum_archive_size: 100
  quality_floor_relative_to_best: 0.97
  descriptors:
    - validation_type
    - model_family
    - representation
    - shift_hypothesis
    - entity_hypothesis

oof:
  save_row_level_predictions: true
  metrics:
    - residual_correlation
    - prediction_disagreement
    - covariance_effective_rank
    - marginal_ensemble_gain

security:
  web_access: false
  winner_writeups_access: false
  obfuscate_competition_name: true
  hash_column_names: false
```

---

## 16. 評価仕様

### 16.1 比較対象

- System A
- System B
- System B+
- System C
- System CのComponent Ablation

### 16.2 統一するResource

| Resource             | 統一条件          |
| -------------------- | ----------------- |
| Base LLM             | 同一Model Version |
| LLM Tokens           | 総量同一          |
| GPU                  | GPU時間同一       |
| CPU / RAM            | 同一              |
| Wall-clock           | 同一              |
| Initial Code         | 同一              |
| Initial Data         | 同一              |
| Public Query         | 同一              |
| External Information | 同一              |
| Final Submission     | 1件               |
| Random Seed Set      | 同一              |

実験数そのものではなく、Compute、Token、Wall-clockをPrimaryなBudget一致条件とする。安価な診断実験と長時間のModel Trainingを同一の「1実験」と数えると公平性を損なうためである。

### 16.3 Primary Endpoint

[
PrivatePerformance_C

---

PrivatePerformance_B
]

Primary Endpointは、Locked Final SolutionのPrivate ScoreまたはPercentile Rankとする。

### 16.4 Secondary Endpoint

- Public Score
- Local CV
- CV→Private Candidate Rank Correlation
- Critical Discovery Rediscovery Rate
- Time to Critical Discovery
- Hypothesis Diversity
- Solution Diversity
- OOF Error Diversity
- Validation Fidelity
- Falsification Coverage
- Hypothesis Calibration
- Experiment Efficiency
- GPU Cost
- Token Cost
- Invalid Experiment Rate
- Invalid Submission Rate
- Reproduction Failure Rate

### 16.5 System C成功条件

- System CがSystem BよりPrivate性能で実質的に優れる
- 複数Competitionまたは複数Domainで再現する
- 同一Budget下で優れる
- Validation FidelityまたはCritical Discovery改善が確認できる
- その改善が最終性能向上へ接続している
- System B+との差が存在する

### 16.6 System C失敗条件

次のいずれかを満たした場合、Epistemic Layerの実用価値は支持されない。

- CとBのPrivate性能が同等
- CがBよりPrivate性能で劣る
- 仮説数だけ増えて最終性能が変わらない
- Critical Discoveryは増えるがCompute overheadで負ける
- B+とCが同等
- EIGの高い実験がDecisionへ影響しない
- Belief Calibrationが改善しない
- Cの改善が単なる追加Tokenまたは追加Computeで説明できる

この失敗条件は、調査結果で定義された「C ≈ B」「B+ ≈ C」「Discoveryは増えるがPrivateは改善しない」という反証条件に対応する。

---

## 17. Benchmark構成

### 17.1 推奨順序

| 段階   | Competition              | 主な検証対象                              |
| ------ | ------------------------ | ----------------------------------------- |
| Pilot  | Rossmann Store Sales     | Validation Fidelity                       |
| Main 1 | IEEE-CIS Fraud Detection | Time、Entity、Shift                       |
| Main 2 | Airbus Ship Detection    | Overlap、CV、Problem Decomposition        |
| Main 3 | RiiidまたはH&M           | Online SequenceまたはCandidate Generation |

Rossmannは低コストPilot、IEEE-CISは強い反証用Competitionとして使用する。単一Competitionだけでは一般化を主張しない。

### 17.2 Critical Discovery評価

各Competitionについて、Agent実行前に独立AnnotatorがCritical Discoveryを定義する。

```yaml
critical_discovery:
  id: CD-001
  claim: temporal holdout is more reliable than random split
  evidence_required:
    - rolling backtest result
    - model rank comparison
  minimum_rediscovery_criterion:
    - experiment executed
    - result statistically supported
    - decision changed
  importance: high
```

Rediscoveryと認定するには次の3条件をすべて満たす。

1. 仮説を記述した
2. 実験で検証した
3. Validation、Feature、Model、Ensemble等の意思決定へ反映した

単に「Distribution Shiftがあるかもしれない」と出力しただけではRediscoveryとしない。

---

## 18. Contamination対策

### 必須対策

- Competition名を匿名化する実験Variantを用意する
- Column名をHashまたは意味中立名へ変更するVariantを用意する
- Winner固有の語彙を除去する
- Web Accessを無効化する
- Winner Write-upをPrompt、Memory、Vector Storeへ登録しない
- Critical Discovery一覧をAgentへ見せない
- Winner CodeをInitial Baselineへ混入させない
- CompetitionごとにArtifact Storeを分離する

### Preferred State学習時

- Leave-one-competition-out
- Leave-one-domain-out
- WinnerだけでなくTop 3–10を含める
- Public上位からPrivate失速した例を含める
- Failure caseをControlとして含める
- Prior strengthを低くする

Winner corpus由来のSurvivorship Bias、Meta-overfitting、LLM contamination、Information Gain Goodhartは、本研究の主要な失敗要因として扱う。

---

## 19. 非機能要件

### 19.1 再現性

- 全ExperimentでSeedを記録する
- Dataset Hashを記録する
- Code Commitを固定する
- Environment Lockfileを保存する
- Fold assignmentを保存する
- Submission生成手順を保存する
- 同一Manifestから再実行可能にする

### 19.2 監査可能性

- すべてのPosterior更新をEvidence IDへ紐付ける
- 実験前予測と実験後結果を分離保存する
- 実験後のPrediction改変を禁止する
- Utility計算内訳を保存する
- Meta Controllerの選択理由を記録する
- Agentの自然言語説明と機械Metricを分離する

### 19.3 Resource Isolation

- ExperimentごとにCPU、GPU、RAM上限を設定する
- Timeoutを強制する
- 失敗Experimentが全体Runを停止させない
- Debug retry回数を制限する
- Systemごとの総Budgetを強制する

### 19.4 可搬性

- Linux環境で動作する
- GPUなしでもValidation、BED、QD、Registry部分を実行可能
- Competition固有処理をPlugin化する
- Metricを差し替え可能にする
- Tabular、Time-series、CV、NLPへ拡張可能にする

### 19.5 可観測性

最低限、次をDashboardまたはReportへ出力する。

- 残Budget
- Experiment Queue
- Active Hypotheses
- Hypothesis Entropy
- Validation World Posterior
- QD Occupancy
- Best Candidate
- Robustness
- OOF Effective Rank
- Failure Count
- Public Query Count
- Agent別Cost
- Cycle別Utility内訳

---

## 20. テスト仕様

### Unit Test

- EIG計算
- Bayes Posterior更新
- EVSI Proxy
- QD Cell assignment
- Residual correlation
- Effective Rank
- Budget accounting
- Stop policy
- Schema validation

### Integration Test

- Hypothesis作成からExperiment実行、Posterior更新まで
- Candidate生成からQD Archive登録まで
- OOF生成からEnsemble構築まで
- Failed Experiment時のIsolation
- Final Submission生成

### Regression Test

- 同一Seed、同一ManifestでMetricが許容誤差内
- Registryの既存Evidenceが消えない
- System B実行時にEIG機能が混入しない
- System C実行時にPreregistrationを迂回できない
- Public Query上限を超えない

### Contamination Test

- Winner固有語彙がPromptへ含まれない
- Private ScoreがRuntime Contextへ流入しない
- Critical Discovery一覧がAgentへ渡らない
- Competition匿名化Variantで実行可能

---

## 21. MVP受入条件

MVPは以下をすべて満たした場合に完成とする。

1. System A/B/B+/Cを設定切替だけで実行できる
2. 10 Cycle以上の研究Loopを自動実行できる
3. 2種類以上のValidation Worldを比較できる
4. 仮説をSchemaに基づき保存できる
5. 全Epistemic Experimentに事前予測が存在する
6. EIGまたはEVSI Proxyを計算できる
7. Independent Falsifierが反証実験を生成できる
8. QD Archiveが複数DescriptorでCandidateを保持できる
9. Row-level OOF Predictionを保存できる
10. Residual correlationとEffective Rankを計算できる
11. Compute、Token、Wall-clock Costを記録できる
12. Locked Final Submissionを生成できる
13. Winner情報を実行時に使用しない
14. Run全体をManifestから再現できる
15. A/B/B+/C比較Reportを自動生成できる

---

## 22. 実装フェーズ

### Phase 0 — Strong System B

- Baseline Runner
- Evolutionary Search
- QD Archive
- Candidate Schema
- Budget Manager
- OOF Store

この段階で強いSystem Bを構築する。System Bが弱い状態でSystem Cを比較してはならない。

### Phase 1 — Validation Epistemics

- Validation World Manager
- Validation Hypothesis
- Rolling / Group / Time Backtest
- Rank Stability
- Validation Posterior

最初はすべての研究不確実性を扱わず、Validation uncertaintyに限定する。

### Phase 2 — Hypothesis Registry

- Hypothesis Schema
- Prior / Posterior
- Evidence
- Preregistered Prediction
- Calibration

### Phase 3 — BED

- Discrete EIG
- Monte Carlo EIG
- EVSI Proxy
- Experiment Utility
- Meta Controller連携

### Phase 4 — Falsifier

- Independent Context
- Falsification Priority
- Minimal Counter Experiment
- Replication Queue

### Phase 5 — OOF Diversity

- Residual Matrix
- Pairwise Correlation
- Effective Rank
- Marginal Ensemble Gain
- Diversity-aware Finalizer

### Phase 6 — Benchmark

- Rossmann Pilot
- IEEE-CIS Main
- A/B/B+/C比較
- Component Ablation
- Contamination Variant
- Multi-seed評価

---

## 23. 最大リスクと対策

| リスク                      | 内容                                     | 対策                                   |
| --------------------------- | ---------------------------------------- | -------------------------------------- |
| Information Gain Goodhart   | 自分で不確実性を作り、解消したことにする | Calibration、事前予測、Held-out評価    |
| Model Misspecification      | 誤ったLikelihoodからEIGを計算            | 局所仮説、低次元観測、Inconclusive許可 |
| Overhead                    | Epistemic実験に予算を使いすぎる          | Epistemic割合上限、Bとの同Budget比較   |
| QD Gaming                   | Descriptorを埋めるだけになる             | Quality Floor、Decision Impact         |
| Hypothesis Inflation        | 無意味な仮説を大量生成                   | Active Hypothesis上限、Alternative必須 |
| Confirmation Bias           | 提案者が自分の仮説を支持                 | Independent Falsifier                  |
| Public LB Overfit           | Public Scoreに逐次適応                   | Query上限、Locked selection rule       |
| Winner Memorization         | LLMが有名解法を再生                      | 匿名化、Web禁止、Column rename         |
| OOF Leakage                 | Blend Weightを同じOOFで過適合            | Nested OOF、Second-level holdout       |
| False Evidence Independence | 同一データの分析を複数証拠扱い           | Evidence dependency graph              |
| Validation Collapse         | 全候補が同じSplitを信じる                | Validation World Posterior             |
| Reproducibility Failure     | 実験結果を再現できない                   | Manifest、Hash、Replication            |

---

## 24. 最終判断ルール

本システムの研究判断は次の順序で行う。

### System BがSystem Aを上回らない

Evolution/QD実装自体に問題がある。System C評価へ進まない。

### System B+がSystem Bを上回る

EpistemicなDescriptorをQDへ追加する価値がある。

### System CがSystem B+を上回らない

明示的Posterior、EIG、Belief Update、Falsifierは不要である可能性が高い。QD Descriptor設計を採用する。

### System CがSystem B+を上回るがPrivate性能が改善しない

研究状態の可視化には価値があるが、Kaggle攻略性能への実用価値は確認できない。

### System Cが同一Budgetで複数DomainのPrivate性能を改善する

明示的なEpistemic Layerの追加価値が支持される。

---

## 25. 本仕様の最小実装定義

最初に実装するC-liteは、次の9機能に限定する。

```text
1. Strong Evolution/QD Search
2. Random / Time / Group Validation Worlds
3. Explicit Hypothesis Registry
4. Prior / Posterior on Validation Hypotheses
5. Preregistered Experiment Predictions
6. EIGまたはEVSI Proxy
7. Independent Falsifier
8. OOF Residual Diversity Archive
9. Exploit / Explore / Epistemic Budget Controller
```

この最小構成が強いSystem Bを同一Budgetで上回らなければ、Full Active Inference、複雑なGenerative Model、Expected Free Energyへ拡張しない。

本システムの中心は、Active Inferenceという名称ではなく、既存のEvolution/QDシステムへ次の問いを機械可読形式で追加することにある。

> 現在、何が分かっていないのか。
> どの仮説が競合しているのか。
> どの実験がそれらを最も区別するのか。
> その情報によって、次の研究判断は本当に変わるのか。
> その結果、Hidden Test性能は改善したのか。

---

## 26. 実証後の差分仕様

本設計をIEEE-CISへ適用して得た差分仕様は、次を優先して適用する。

1. [C-lite v0.2 scaling correction](c_lite_revision_v0.2.md)
2. [C-lite v0.3 dynamic structure maturation](c_lite_revision_v0.3.md)
3. [C-lite v0.3.1 measurement and debt closure](c_lite_revision_v0.3.1.md)

v0.3.1は、追加Agent/CycleではなくFrozen Hidden Endpoint、Full Common First-level Cross-fit、Structure Debt終端、Predictive Collapse/Stagnation分離を要求する。実測結果は[IEEE-CIS v0.3.1 verification](verification/ieee_cis_v031_measurement.md)に記録する。
