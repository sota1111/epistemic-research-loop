# Epistemic Research Loop C-lite 修正仕様書 v0.3

**文書バージョン:** 0.3

**修正対象:** C-lite v0.2（本書と旧仕様が矛盾する場合は本書を優先）

**対象検証:** IEEE-CIS Fraud Detection / Synthetic Structure Controls
**ステータス:** 実装仕様

## 1. 修正目的

v0.2はAgent-local Belief、選択的Communication、Candidate生成までを実現したが、UID FeatureのForward性能向上をClient Identity発見と区別できなかった。v0.3は固定の「問題構造担当Agent」を置かず、任意Agentが高レバレッジな構造仮説を自発的に発見した時だけ、一時的なStructure Maturation Forkを生成する。

中心原則は次である。

```text
Generic Research Agent
  -> high-leverage structural hypothesis
  -> Structure Discovery State
  -> temporary Structure Maturation Fork
       |- Implementation Child
       |- Null / Skeptic Child
       `- Verification Worker
  -> debt resolution and gate decision
  -> fork dissolution / Generic Research State
```

ControllerはUID、時間、Entity等の探索対象を指定しない。発見後の科学的検証だけを強制する。既存`EpistemicNiche`は旧RunのReplay互換用であり、v0.3の既定Agent割当には使用しない。

## 2. Structural Hypothesis

次の意思決定次元のうち2つ以上を変更し得る仮説をStructural Hypothesisとする。

- Validation Split
- 観測単位または予測単位
- Row間の独立性
- Entity / Grouping
- Temporal Order
- Feature Generation
- Candidate Routing
- Post-processing
- Target / Metric Decomposition
- Train/Test生成過程

構造レバレッジは次で評価する。

$$L(H)=\sum_d w_d\mathbf{1}[H\text{が意思決定}d\text{を変更し得る}]$$

ただし、競合仮説、観測可能な予測、反証条件、実行可能な識別実験、影響する意思決定が揃うまではUtility上のStructural Leverageを0とする。大きな物語を記述しただけでは加点しない。

## 3. Lifecycle

```text
OBSERVATION
  -> PROVISIONAL_STRUCTURE
  -> ALTERNATIVES_REGISTERED
  -> DISCRIMINATING_TESTS_PREREGISTERED
  -> PARTIALLY_VALIDATED
       |- VALIDATED_STRUCTURE
       |- USEFUL_ENCODING_UNVALIDATED_STRUCTURE
       |- STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE
       |- FALSIFIED
       `- INCONCLUSIVE
```

`VALIDATED_STRUCTURE`は複数の独立予測と反証試験を通過した状態である。性能だけが上がり意味を確認できない場合は`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`、構造らしいが意思決定や性能を改善しない場合は`STRUCTURALLY_PLAUSIBLE_NON_ACTIONABLE`とする。Agent 05のv0.2 UID結果は`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`であり、Validated Client Identityではない。

## 4. Structure Validation Debt

構造仮説をCandidateが利用した時点でControllerはDebtを自動起票する。

```yaml
structure_validation_debt:
  hypothesis_id: A05-H-UID-001
  structure_type: latent_entity_proxy
  unresolved_requirements:
    - uid_free_ablation
    - frequency_only_control
    - frequency_matched_null
    - linkage_shuffle
    - temporal_persistence
    - known_new_interaction
    - multi_seed_replication
  status: open
  owner_agent: agent-05
  affects_candidates: [CAND-05-001]
```

Debtが開いているCandidateもArchiveとEnsembleへ残せる。ただし以下を禁止する。

- `VALIDATED_STRUCTURE`への昇格
- Preferred Research StateのDGP Understanding改善扱い
- Critical Discovery完全再発見への計上
- T1完全点
- 他Agentへの確認済み事実としてのEvidence Promotion

## 5. Dynamic Structure Maturation Fork

Forkは高レバレッジ仮説を発見したAgentのCheckpointから生成し、仮説検証後に解散する。

| Child | 責務 |
|---|---|
| Implementation | 仮説を利用したCandidateを実装・改善 |
| Null / Skeptic | 競合説明、Null、Linkage Shuffleを実装 |
| Verification | Fold safety、Artifact、統計比較を独立検査 |

Forkには他AgentのBelief、Posterior、Global Best、Candidate Scoreを渡さない。固定Client AgentやTemporal Agentは作成しない。

## 6. UID競合モデル

UID構造主張は少なくとも次を登録する。

| ID | 説明 |
|---|---|
| H_client | UID proxyは持続的な同一Behavioral Clientを一定精度で表す |
| H_frequency | 改善はGroup Sizeまたは出現頻度による |
| H_time | UIDは登録時期または収集Batchを表す |
| H_components | UID構成Raw Featureが改善を説明する |
| H_linkage_noise | 任意GroupのMemory Featureでも同様に改善する |
| H_leakage | 未来行またはValidation Rowが集約へ混入する |
| H_sparse_overfit | Rare Group細分化による偶然のForward改善である |

## 7. Nested UID Ablation

同一Model、Hyperparameter、Forward Fold、Seedで次を比較する。

| Candidate | 内容 | 分離対象 |
|---|---|---|
| M0_BASE | UID構成列・UID Featureなし | 基準 |
| M1_COMPONENTS | UID構成Raw列のみ | Raw Component |
| M2_FREQUENCY | Raw列 + Count/Cardinality/Frequency | Frequency |
| M3_UID_MEMORY | Fold-safe Count/Amount/Recency/History | Identity Memory |
| M4_LINK_SHUFFLED | Group Size等を保ちLinkのみ破壊 | Client Linkage |
| M5_MATCHED_NULL | Frequency/Time分布を合わせたRandom Group | 任意Grouping |

$$\Delta_{component}=Score(M1)-Score(M0)$$

$$\Delta_{frequency}=Score(M2)-Score(M1)$$

$$\Delta_{identity}=Score(M3)-Score(M2)$$

$$\Delta_{linkage}=Score(M3)-Score(M4)$$

## 8. Frequency-matched NullとLinkage Shuffle

Matched NullはGroup Size、観測回数、粗いTime Bin、Known/New比、Missingness概略、Model/Fold/Seed/Resourceを保持し、長期Link、Client履歴、Amount/Recency/Fraud Historyの継続性、意味のあるUID列共起を破壊する。同一Stratum内でUID割当をPermutationし、20回以上のNull Gain分布を作る。実Gainが95%点を超えなければH_clientを支持しない。

Linkage ShuffleはFrequency、Group Size、Time Densityを維持したまま過去と未来のClient Linkを破壊する。`Score(M3)-Score(M4)≈0`ならH_frequencyまたはH_timeを強める。

## 9. Construct ValidityとTemporal Persistence

UID生成に未使用のDevice、D系、準不変Featureについて、Within-group一致率、Between-group分離、Mutual Information、Future属性予測、群内/群間分散、時間を隔てた再現率をMatched Nullと比較する。Ground-truth Client IDがないため、成功状態名は`Validated Behavioral Client Proxy`とする。

Early Windowで定義したUIDについてMiddle/Lateでの再出現、未使用Feature/Behaviorの安定性、同Frequency Nullとの差を測る。粗いKeyのRow-weighted overlapだけを証拠にしない。

$$Persistence_{UID}>Persistence_{frequency\text{-}matched\ null}$$

## 10. Known / New識別予測

事前登録する含意は次である。

- P1: UID Memory GainはKnown Clientで正
- P2: New ClientではGainが小さい、またはFrequency-onlyと同程度
- P3: Link-shuffled UIDではKnown Client Gainが消える

$$\Delta_{known}=Score_{known}(M3)-Score_{known}(M2)$$

$$\Delta_{new}=Score_{new}(M3)-Score_{new}(M2)$$

$$\Delta_{interaction}=\Delta_{known}-\Delta_{new}$$

Matched Nullでも同じInteractionが生じる場合はIdentity証拠にしない。

## 11. Validated Behavioral Client Proxy Gate

| Gate | 必須条件 |
|---|---|
| G1 Fold Safety | Aggregateは過去Train Rowだけから生成 |
| G2 UID-free Ablation | M3がM1をForward評価で上回る |
| G3 Frequency Separation | M3がM2を上回る |
| G4 Matched-null Rejection | 実Gainが20個以上のNullの95%点を上回る |
| G5 Linkage Dependence | Link ShuffleでGainが有意に減少 |
| G6 Construct / Persistence | 未使用Feature整合性または継続性がNullを上回る |
| G7 Replication | 3 Horizon以上・3 Seed以上で方向再現 |
| G8 Client Interaction | 事前登録Known/New差が成立しNullを上回る |
| G9 Decision Adoption | Validation、Aggregation、Routing等へ反映 |

初期判定はPaired block bootstrap 95% CIのlower bound > 0、3 Horizon中2以上で同方向、重大な逆転なし、3 Seedで符号安定とする。

## 12. 構造妥当性と予測性能の二軸分類

| 構造妥当性 | 予測改善 | 分類 |
|---|---|---|
| Pass | Pass | VALIDATED_ACTIONABLE_STRUCTURE |
| Pass | Fail | VALIDATED_NON_ACTIONABLE_STRUCTURE |
| Fail | Pass | USEFUL_ENCODING_UNVALIDATED_STRUCTURE |
| Fail | Fail | REJECTED_STRUCTURE |

## 13. Utility

$$\begin{aligned}
U_i(e)={}&\alpha_iE_i[\Delta Performance]+\beta_iEVSI_i(e)+\gamma_iNovelty_i(e)\\
&+\lambda_iStructuralLeverage_i(H)+\mu_iDiscriminationValue_i(e,H)\\
&+\nu_iValidationDebtReduction_i(e)-\eta_iCost(e)-\rho_iRisk(e)
\end{aligned}$$

Structure Validationでは複数の妥当なPrior/Outcome Modelに対する最悪値を`robust_discrimination_value`として利用する。Hyperparameter追加調整より、交絡を保ったまま競合仮説を分離する実験を優先する。

## 14. Stateless Falsification Test Critic

実行前に次を検査する。

1. Main Hypothesisが偽でもTestがPassし得ないか
2. 競合仮説間で予測が異なるか
3. NullがGroup Size、Time、Missingness等の交絡を保持するか
4. 既存TestとのSemantic Duplicateでないか
5. Fold Leakageがないか
6. 検出力と必要反復数があるか
7. 結果がどのDecisionを変えるか

CriticはAgent Belief/Posteriorを読まず、変更しない。

## 15. Meta Controller

ControllerはStructural Hypothesis型判定、Debt生成、Fork Budget、Null Artifact、Common Evaluation、Promotion Gate、Final ReportのDebt表示を担当する。UID探索、UID列指定、Posterior変更、仮説Broadcast、Global Best共有、Client仮説の正解扱いは禁止する。

## 16. IEEE-CIS Acceptance

旧`at least one validated UID`を`at least one validated behavioral client proxy`へ変更する。

| Level | 条件 |
|---:|---|
| 0.00 | UID仮説なし |
| 0.25 | UID候補・コードのみ |
| 0.50 | Forward Candidate実行 |
| 0.75 | UID-free AblationまたはMatched Nullを通過 |
| 1.00 | G1〜G9を通過し最終Candidateへ採用 |

性能が高くてもGate未通過ならT1完全点を与えないが、Performance Candidateとして保持できる。

## 17. Agent 05再分類フロー

UID提案、PROVISIONAL登録、競合登録、Forward Candidate、Debt生成、M0〜M5、20 Null、Known/New Interaction、Held-out coherence、3 Horizon × 3 Seed、Gate判定の順に進める。v0.2結果は現時点で`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`である。

## 18. Synthetic Controls

Positive Controlは安定Latent Client、長期Behavior、Client History依存Fraud Risk、複数表面列へ分散したIdentifierを持つ。Negative Controlは同じGroup Size/Frequency/Time分布を保つが持続Linkを持たない。

測定指標はPositive Control Acceptance Rate、Negative Control Rejection Rate、False Structure Promotion Rate、Time to Structure Validation、Validation Experiment Costとする。このControlを通過しないValidatorでIEEE-CIS UIDをValidatedと呼ばない。

## 19. Acceptance Criteria

- Agentは固定Structure RoleなしにGeneric Stateから開始する
- 任意Agentが自発的にStructural Hypothesisを登録できる
- 2次元未満、予測/反証/識別/Decision欠落の仮説は昇格しない
- Lifecycleの順序を機械的に強制する
- Candidate利用時にDebtを自動生成する
- Debt中もCandidate Archive登録を許可する
- Debt中はConfirmed Fact共有とValidated昇格を禁止する
- Forkは3 Childを動的生成し、完了時に解散する
- CriticはBelief非依存で7検査を行う
- M0〜M5、20 Null、Construct/Persistence、Known/New、3×3再現を評価できる
- 構造妥当性と予測改善を二軸分類する
- Positive/Negative Synthetic Controlsを評価できる

## 20. 最終原則

```text
構造らしい手掛かり
  -> 競合説明
  -> 交絡保持Null
  -> 反証可能な予測
  -> 独立した含意と再現
  -> Validated Structure
  -> Validation / Feature / Routing / Post-processingへ採用
```

重要仮説を自発的発見後にだけ深掘りし、未検証の物語を共有知識へ固定しない。
