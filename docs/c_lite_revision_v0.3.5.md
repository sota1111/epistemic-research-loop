# Epistemic Research Loop C-lite v0.3.5 仕様書

## Independent Agent Evolution & Structure Discovery Qualification

- 対象: IEEE-CIS Fraud Detection + Structure Control Suite
- 基本構成: 3 Generic Agents × 3 Adaptive Cycles
- 固定Epistemic Niche: なし
- Phase 1 Cross-agent Research Sharing: なし
- Primary Evaluation: Agent-level Research Quality / Structure Calibration / Sealed・Hidden Transfer
- Status: 実装済みQualification仕様

## 1. 目的

v0.3.4までに、Generic Agentから異なるResearch Questionが生じ、Artifact、Common Cross-fit、
Sealed IsolationがEnd-to-Endで動くことを確認した。一方、Semantic DiversityはPredictive
Diversityを保証せず、Local ValidationによるFalse Rejectionが大きな損失になり得た。

v0.3.5ではB/B+/C比較を保留し、次を先にQualificationする。

1. 固定担当なしの各Agentが、複数のResearch Ideaを生成・選択・進化できるか。
2. 実在する構造を発見・検証し、存在しない構造を棄却できるか。
3. Validated StructureをCandidate Decisionへ変換し、Sealed/Hidden改善へ接続できるか。

中心原則は次である。

```text
Agent Diversity != Agent Role Diversity
Agent Evolution != one-line local tuning
Structure Discovery != writing a plausible story
Structure Validation != improving CV
Useful Structure = Validated + DecisionChanged + FutureGain > 0
```

## 2. Phase 1 — Independent Agent Qualification

3 Agentは独立したLocal Research Loopを持つ。ControllerはArtifactを保存するが、Run終了まで
Population情報をAgentの研究判断へ使わない。

Agentへ渡さない情報:

- 他AgentのHypothesis、Candidate、Score、Debt、Failure、Research Direction
- Global Best、Population Summary、Global Semantic Coverage

Agentへ渡す情報:

- 共通Dataset、Artifact Contract、Validation Contract、Safety/Leakage Rule
- 自分のEvidence、Candidate Archive、Debt、Belief State

Phase 1のPopulation metricは`observe-only`であり、Agentを別方向へ誘導しない。共有そのものを
恒久禁止せず、Phase 2でEvidence、Debt/Challenge、Candidate Migrationを独立Ablationする。

## 3. Local Research Portfolio

各Agentは単一Lineageではなく次を保持する。

```text
Incumbent Line   現在の有力Candidate
Challenger Line  異なる説明・表現
Structural Line  高レバレッジ構造の探索・反証
```

Archive Eliteも次の3つに分離する。

- Performance Elite
- Information Elite
- Structural Elite

テーマはAgent-localであり、Controllerは特定Feature、Model、Entity、Time等を指定しない。

## 4. Cycle Proposal Contract

各Cycleは最低3 Proposalを事前登録する。

```yaml
proposals:
  - mode: exploit
    purpose: improve current incumbent
  - mode: explore
    purpose: investigate a substantially different explanation
  - mode: epistemic
    purpose: discriminate or falsify an important uncertainty
```

高レバレッジ不確実性がない場合だけ`epistemic`を`novel_exploration`へ変更できる。Proposalは
次のDescriptorを持つ。

```yaml
research_descriptor:
  hypothesis_family: ...
  representation_family: ...
  validation_world: ...
  data_slice: ...
  experiment_operator: ...
  model_family: ...
  downstream_decision: ...
  structural_claim: true | false
```

Local Noveltyは自分のArchiveとの最小正規化Hamming distanceで測る。Noveltyだけは最大化しない。

## 5. Dynamic Explore / Exploit

初期Priorは`exploit=0.34, explore=0.33, epistemic=0.33`とする。その後はAgent自身の
Incumbent Gain、Research State Coverage、Uncertainty Reduction、Structure Validation、
Candidate Complementarityで更新する。Resource CostはUtilityへ含めない。

## 6. Local Search Stagnation

2 Cycle以上、同一Semantic FamilyでDecision Change、Candidate Improvement、Uncertainty
Reductionがすべてない場合に発火する。通知は次だけとする。

> 現在の研究経路は新しいDecisionまたはEvidenceを生成していない。既存Beliefと異なる説明を最低1つ生成せよ。

具体的な研究方向は指定しない。同一Familyの合理的な深掘りは妨げない。

## 7. Diversity Acceptance

Agent別に、3 Cycleで2以上のSemantic Family、または同一Family内で2以上の競合仮説識別を要求する。
PopulationはRun終了後だけ集約し、初期Engineering Gateを次とする。

```text
3 Agent中2 Agent以上が個別Gateを通過
Population Effective Research Family >= 2.5
Dominant Family Fraction <= 0.6
```

ActionはE1 Exploitation、E2 Solution Exploration、E3 Epistemic Exploration、E4 Structure
Maturationへ事後分類する。3種類以上を実行し、単一Type占有率を0.70以下とする。このGateは
Hidden成果の代替ではない。

## 8. Shadow Candidate Archive

Local rejectionは「次CycleのParentにしない」だけを意味する。次を満たす棄却CandidateはShadow
Archiveへ残し、Global Final Selectorが再評価できる。

- Artifact valid
- Leakageなし
- Prediction生成可能
- Parentと意味的差分あり

Final SelectorはAgent判断と分離し、Performance Elite、Information Elite、Structural Elite、
Shadow Candidateを共通Cross-fitで比較する。

## 9. High-leverage Structure

次のうち2つ以上を変え得る仮説をHigh-leverage Structureとする。

- Validation geometry、Observation unit、Entity definition、Temporal causality
- Target decomposition、Train/Test generating process、Feature generation
- Routing、Post-processing、Error decomposition

Structure Proposalはclaim、H0/H2/H3、各仮説のObservable Prediction、Confounder、
Falsification Condition、Independent Implication、Affected Decisionを必須とする。CV向上だけで
Supportしない。

Lifecycle:

```text
OBSERVATION -> PROVISIONAL_STRUCTURE -> ALTERNATIVES_REGISTERED
 -> DISCRIMINATING_TEST -> PARTIALLY_VALIDATED
 -> VALIDATED_ACTIONABLE | VALIDATED_NON_ACTIONABLE
  | USEFUL_ENCODING_UNVALIDATED | FALSIFIED | INCONCLUSIVE
```

Validation DebtはAgent-localで管理し、matched null、independent implication、multi-context
replication、downstream adoption等の未完了条件を表す。

## 10. Blind Structure Control Suite

AgentにはOpaque Case ID、Schema、Label付きResearch Region、LabelなしSealed Regionだけを渡す。
Positive/Negative、Family、Generator Seed、Sealed LabelはControllerだけが保持する。

Positive Family:

1. P1 Persistent Entity
2. P2 Temporal Regime
3. P3 Observation Process
4. P4 Problem Decomposition / Conditional Routing

Negative Family:

1. N1 Frequency Artifact
2. N2 Temporal-looking Noise
3. N3 Missingness Artifact
4. N4 Random Routing

NegativeはFrequency、Group Size、Time、Missingness等の表面構造を残し、継続的Linkや条件付き
Target Mechanismを持たない。

## 11. Structure Validation Bundle

Terminal Promotionには次をすべて要求する。

```text
G1 competing hypotheses registered
G2 fold / causal safety
G3 confounder-preserving null
G4 independent implication
G5 multi-context replication
G6 multi-seed replication
G7 negative-control discrimination
G8 downstream decision change
```

Nullは20反復以上とする。単一SeedはSupporting/Contradicting/Inconclusive Evidenceにしかならない。
3 Seed以上のAggregate GateとLeave-one-seed-out Stabilityを通過した場合だけTerminal Promotionする。

## 12. Structure-to-Performance Transfer

Validated Structureごとに、同じLearner、Seed、Validationを使うStructure-informed Candidateと
Matched Structure-free Candidateを作る。

```text
Delta_structure = SealedAUC(structure-informed) - SealedAUC(structure-free)
Useful = Validated AND DecisionChanged AND Delta_structure > 0
```

USTRはPositive Sealed Gainを持つValidated Actionable Structureの割合とする。

## 13. MetricsとAcceptance

Primary:

- Independent Research Diversity (IRD)
- True Structure Discovery Rate (TSDR)
- True Structure Rejection Rate (TSRR)
- Useful Structure Transfer Rate (USTR)
- Agent Selection Regret

Structure CalibrationはBrier Score、Expected Calibration Error、Reliability Diagramを記録する。

Acceptance:

```text
A Diversity: 2/3 Agent、Effective Family >= 2.5
B Evolution: Action Type >= 3、Performance改善あり、Epistemic/Structure完了あり
C TSDR >= 0.60
D TSRR >= 0.80 and FSPR <= 0.20
E USTR >= 0.50 and Median Sealed Gain > 0
F Artifact Contract = OOF Honesty = Sealed Isolation = 100%
```

モデル数、Feature数、Semantic Cluster数、Hypothesis数、Posterior変化、False Structure棄却数だけでは
Passにしない。

## 14. IEEE-CIS適用

IEEE-CISにはGround-truth StructureがないためTSDR/TSRRを主張しない。Structure Candidate数、
Falsification完了率、Validated数、Structure-informed Gain、Sealed Gain、Runtime非公開のWinner
Critical Discovery再発見を事後評価する。Winner情報は実行中のAgentへ渡さない。

v0.3.4のArtifact Contract、Common Cross-fit、Sealed Isolation、Final SelectorはStage 0で凍結する。
Stage 1で個別Agent、Stage 2でBlind Control、Stage 3でTransfer、Stage 4でIEEE-CIS、Stage 5で
Populationを事後集約する。Stage 6のCommunication AblationはPhase 1 Qualification後だけ実行する。

## 15. 実装対応

| Requirement | Implementation |
| --- | --- |
| Proposal 3-mode contract | `controller/agent_qualification.py::CycleProposalSet` |
| Dynamic local allocation | `ModeAllocation`, `adapt_mode_allocation` |
| Local Portfolio / three elites | `LocalResearchPortfolio`, `LocalEliteSet` |
| Shadow Archive | `CandidateResearchOutcome.final_recheck_eligible` |
| Local Stagnation | `LocalSearchStagnationDetector` |
| Individual / Population Scorecard | `AgentQualificationScorecard`, `PopulationQualificationScorecard` |
| Blind Control Boundary | `benchmark/structure_controls_v035.py::AgentControlView` |
| Four positive/four negative controls | `generate_blind_structure_controls` |
| Null / implication / context probes | `GenericBlindStructureAgent` |
| Aggregate-only promotion | `evaluation/v035.py::StructureQualificationReport` |
| Calibration / Transfer | `StructureQualificationReport` |
| Acceptance | `V035Acceptance` |

## 16. 判断範囲

Synthetic Control Passは、決定論的Reference Probeと評価ContractのEngineering Qualificationである。
LLM Agent自身の未知構造発見率、IEEE-CIS Hidden/Private改善、Communication効果、B/B+/C優位を示さない。
それらはQualification済みPolicyを新しいSealed Runへ適用して初めて評価する。
