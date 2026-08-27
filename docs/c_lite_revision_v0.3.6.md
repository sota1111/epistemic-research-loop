# Epistemic Research Loop C-lite v0.3.6 仕様書

## Blind Real-Agent Structure Discovery & Population Evolution Qualification

- 対象: Blind Structure Control Suite、IEEE-CIS Development Benchmark、未使用Real Benchmark
- 主目的: Reference Probeではなく、実LLM Agentが未知構造を自律発見・反証・性能転送できるかを測る
- 構成: 3 Generic Agents × 各Pack最大4 Adaptive Cycles
- 固定Niche: なし
- Phase 1共有: なし
- Phase 2共有: Evidence、Debt、Candidate Migration、Full SharingをAblation
- Primary: Real-Agent TSDR / TSRR / FSPR / USTR
- Secondary: IRD、EECR、Selection Regret

本書はv0.3.5の差分仕様である。矛盾する場合は本書を優先する。

## 1. これまでに分かったこと

v0.2では固定NicheからTemporal、Entity/UID proxy、Model/Falsificationという意味的に異なるCandidateが生成され、Semantic Duplicate Rateは0だった。しかし最終候補はLightGBMへ収束し、Agent 05のUIDもFrequency artifact等を除外できずValidated Structureにはならなかった。

初期Scalingでは、Agent数とCycle数を増やしても固定Shell Action SpaceがUID、異種Model、Routing、Post-processing、OOF Ensembleを表現できなかった。探索量を増やしてもAction Spaceが狭ければ狭い領域を詳しく調べるだけだった。

v0.3は固定Nicheを廃止し、Agent-local Belief/Gap/Uncertainty/Salienceから探索を分岐させ、Dynamic Structure Maturationを導入した。Research Questionは分岐したが、Residual Effective Rankは低く、Research DiversityはPredictive Diversityへ自動変換されなかった。

v0.3.1/0.3.2ではError SliceとMechanismの事前登録からWorkstream 02が生まれた。単体Private AUCは0.899993でArchive Best 0.909654を下回った一方、Nested Ensembleは0.914784となり+0.005130改善した。Standalone UtilityとEnsemble Utilityが異なることをHiddenまで確認した。ただしFactorialではAgentの説明よりCategory Hashの寄与が大きく、Candidate成功とMechanism理解を分離する必要が残った。

v0.3.3では3 Agent × 3 Cycleでも最終RepresentationがRaw/Base LightGBMへ収束した。v0.3.4のSealed AuditはDecision Sign Accuracy 5/9、False Rejection 4/5、False Adoption 0/4で、棄却したSimplex EnsembleがSealedで+0.006310上回った。このためShadow ArchiveとAgent Selection/System Final Selection分離を導入した。

v0.3.5はAgent-local Portfolio、3-mode Proposal、Shadow Archive、Stagnation、Blind Control、Aggregate-only Promotion、Calibration、Structure Transferを実装した。Trial 0でTruth混入APIを修正し、Trial 1でTemporal Controlの識別力不足を検出し、Trial 2のReference ProbeでTSDR/TSRR/USTR=1、FSPR=0を得た。これはHarnessの識別可能性であり、実LLM Agent能力の証明ではない。

## 2. v0.3.6の研究質問

1. 同一PromptのGeneric Agentが独立に複数Research Lineageを形成できるか。
2. 実在する未知Structureを発見し、競合Nullから区別できるか。
3. 存在しないStructureをAbstentionではなくEvidenceによりFalsifyできるか。
4. Validated StructureをFeature、Validation、Routing、Decompositionへ変換し、Sealed性能を上げられるか。
5. Exploit、Solution Explore、Epistemic Explore、Structure Maturationが共存し、後続Candidateへ転換するか。
6. 独立能力を凍結した後、Evidence/Debt/Candidate共有が多様性を壊さず成果を上げるか。

v0.3.6はB/B+/C比較ではない。Individual Agent Capability、Population Union Capability、Communication Modeを比較単位とする。

## 3. Phase構成

### Phase 0 — Benchmark Qualification

Controller-only Oracle/Reference評価でControl SuiteのBlindnessとIdentifiabilityを確認する。Agent Capabilityへ算入しない。

### Phase 1 — Independent Real-Agent Qualification

3 Agentを独立実行する。ControllerはPopulation Summary、他Agent Evidence、Global Bestを返さず、研究方向を指定しない。

### Phase 2 — Post-hoc Population Evaluation

全Agent停止・Hash Lock後に初めて、Diversity、Structure、Shadow Recovery、Population Selectable/Oracleを評価する。

### Phase 3 — Communication Ablation

Phase 1 CheckpointからM0 Independent、M1 Evidence、M2 Debt/Challenge、M3 Candidate、M4 Full Sharingへ分岐する。共有Candidateの採用は強制しない。

## 4. Development SuiteとQualification Suite

Development SuiteはAPI、Blindness、Generator Identifiability、Metric、Threshold Debug専用でありPrimaryへ使わない。Qualification SuiteはPrompt Freeze後に新しいOpaque ID、Generator Seed、Column Permutation、Structure Compositionで一度だけ生成し、実行開始後は変更しない。失敗後に修正する場合は新Suite IDを用いる。

PilotはPositive 4、Negative 4、各3 Context、3 Agentとする。ConfirmatoryはPilot通過後、未使用SuiteでPositive/Negative各8へ拡張する。

PositiveにはPersistent Unit、Temporal Relation、Observation Process、Conditional/Compositional Mechanism等をController側だけで含める。NegativeはFrequency、Group size、Time、Missingness、Routing等の表面統計を保ちながら高レバレッジStructureを持たない。Agent PromptへFamily名を載せない。

## 5. Identifiability Preflight

PositiveはResearch Region内で競合Nullと区別可能、Structure-aware OracleがStructure-free Controlを上回り、Sealedでも方向が維持され、Early Windowで主要Signalに完全吸収されないことを要求する。NegativeはMatched Marginalを保ち、Structure-aware Oracleが安定改善せず、Null Rejection可能であることを要求する。Preflight結果はAgentへ配信しない。

## 6. Blindness Contract

Agent RuntimeはGenerator Package、Controller Truth、Reference Probe、Family、Polarity、Generator Seed、Sealed Label、Oracle Operator、Correct Intervention、Controller Logへアクセスできない。Agent-facing APIはOpaque ID、Schema、labelled Research rows、unlabelled Sealed rows、Metric、Artifact Contractだけを含む。

Opaque IDはSecret Salt付きHMACとし、列名とPack/Context順はAgentごとに変える。Generator、Agent-visible Sampling、Null Analysis、Model Seedを分離する。Path、Filename、Environment、例外、repr、Hash prefixにTruthを含めない。

本実装はTruthをFernet暗号化して`.controller_truth/`へ置き、鍵を`.state/`へ分離する。Agent-visible treeに対してPath/Content auditを行う。共有開発HostではKernel mount isolationではなくPolicy isolationであるため、その境界をReportに明記する。

## 7. Human Assistance

Primary Runは完全自律とする。Generic Runtime/Compiler Error、Artifact Validator、Agent自身のDebugと自動Testのみ許可する。HumanによるHypothesis、Feature、Operator、Agent Code、Falsification Test、Candidate選択の追加は禁止する。介入RunはASSISTEDとしてPrimaryから除外する。

## 8. Agent-local Research Contract

全Agentへ同一Prompt/Contractを与え、差はSampling履歴、Local Belief、Local Evidenceから生じさせる。Incumbent、Exploration、Epistemic/Structure、Shadow Archive、Local Debtを保持する。

各Packにつき最大4 Cycleとし、各Cycle開始時に最低3 Proposalを登録する。

```yaml
proposal_set:
  exploit:
    description: ...
    expected_decision: ...
  explore:
    description: ...
    novelty_from_local_archive: ...
  epistemic:
    competing_hypotheses: [...]
    discriminating_observable: ...
```

各Proposalはhypothesis family、representation、validation world、observation unit、slice、operator、model、downstream decision、structural claimを自由記述する。固定Category menuは提示せず、正規化はPost-hoc Controllerだけが行う。

同一Semantic Family、Decision変更なし、Performance改善なし、Uncertainty Reductionなし、Falsification Evidenceなしが2 Cycle続く場合のみGeneric Stagnation通知を返す。具体的Feature/Model/Structureは指示しない。

## 9. Structure LifecycleとProposal

```text
OBSERVATION
→ PROVISIONAL_STRUCTURE
→ ALTERNATIVES_REGISTERED
→ DISCRIMINATING_TEST
→ PARTIALLY_VALIDATED
→ VALIDATED_ACTIONABLE | VALIDATED_NON_ACTIONABLE
  | USEFUL_ENCODING_UNVALIDATED | FALSIFIED | INCONCLUSIVE
```

Structure主張にはconfidence、2つ以上のalternative、true/false時の観測予測、confounder、falsification condition、independent implication、affected decisionsを必須とする。Debtはmatched null、independent implication、cross-context、seed stability、downstream transferをAgent-localに管理する。

自然言語がController Family名と一致する必要はない。影響単位を特定し、競合Nullと異なる予測を登録し、Intervention/AblationがMechanismへ作用し、Positiveで再現しMatched NegativeをPromotionしない場合にBehaviorally Equivalent Discoveryとする。

## 10. ResolutionとAggregate Promotion

Negativeで単にINCONCLUSIVEを出してもRejection成功に数えない。Resolution RateはVALIDATED、FALSIFIED、USEFUL_ENCODING_UNVALIDATEDの割合として報告し、AbstentionによるFSPR回避を防ぐ。

Terminal Promotionは単一Context/Seedで行わない。3 Context中2以上のSupport、重大な逆転なし、Leave-one-context-out Stability、Matched Null Rejection、Independent Implication、Fold/Causal Safetyを要求する。

## 11. Structure TransferとShadow Archive

Validated ActionableごとにAgent自身がStructure-informed CandidateとCapacity-matched Structure-free Controlを同一Training Region/Seedで実装し、unlabelled Sealed rowsへ予測する。

$$StructureGain=AUC_{sealed}(aware)-AUC_{sealed}(control)$$

Local rejectionは次Parentにしないことだけを意味する。Artifact-valid Parent/ChallengerはShadow Archiveに保持し、Post-hoc Final Selectorが回収可能にする。

## 12. Finalization

各Agentは他Agent情報なしでFinal Candidate、Structure Status、Confidence、Shadow Archive、Selection ReasonをLockする。3 AgentすべてのHash Lock後にControllerがTruthを復号し、以下を分離する。

- Individual Outcome: Agent自身の選択
- Population Selectable: Sealed Labelなしの共通Research Geometryで選択可能な成果
- Population Oracle: 全Shadowから事後算出する上限

## 13. Metrics

- IRD: 2 Research Family以上を実行したAgent割合
- TSDR: Validated Positive Packs / Positive Packs
- TSRR: 明示的Falsified Negative Packs / Negative Packs
- FSPR: Promoted Negative Packs / Negative Packs
- USTR: Positive Sealed Gainを持つValidated Actionable / Validated Actionable
- EECR: Explore/Epistemic LineageがParent、Final、Ensembleへ変換された割合
- SRR: VALIDATED/FALSIFIED/USEFUL_ENCODING_UNVALIDATED / 全Pack

Agent別値、Population Union、Wilson 95%区間、Family Failure、Agent×Family差を報告する。ConfirmatoryではAgent/Family/PackをRandom Effectとする階層Modelを使用できる。

## 14. Phase 1 Acceptance

```text
Truth/Family/Sealed/Reference leakage = 0
3 Agent中2 Agent以上が2 Research Family以上
Population Effective Family >= 2.5
Dominant Family Fraction <= 0.60
Action Type >= 3
EECR > 0
TSDR >= 0.60
TSRR >= 0.80
FSPR <= 0.20
SRR >= 0.70
Brier <= 0.20
ECE <= 0.20
USTR >= 0.50
Median Structure Gain > 0
Artifact / OOF / Sealed Isolation = 100%
Human-assisted Primary Runs = 0
```

Discovery/Rejectionを満たすがTransfer、Diversity、Calibration、Regretに問題があればPartial。Reference Probeだけ通りReal Agentが発見、棄却、転送、Artifact完了できなければFailとする。

## 15. Communication Ablation

- M0 Independent: 共有なし
- M1 Evidence: 再現済み観測のみ。Score/Best/Belief/推奨なし
- M2 Debt: Evidenceと未解決Question/Challenge
- M3 Candidate: CandidateをParent/Challenger/Ensembleとして利用可能。Score rankingなし
- M4 Full: 比較用にEvidence/Hypothesis/Debt/Candidate/Score共有

Agentはadopt/falsify/ignore/reinterpretを選べる。採用条件はTSDRまたはUSTR改善、FSPR非悪化、Diversity Retention Ratio 0.80以上とする。Phase 1通過前のModeはUNMEASUREDのまま保持し、効果を主張しない。

## 16. Failure Interpretation

- TSDR低、TSRR高、FSPR低: 過度に保守的。Hypothesis generation/識別Experimentを改善
- TSDR高、TSRR低、FSPR高: Structure story過多。Null/Promotion/Calibrationを改善
- TSDR/TSRR高、USTR低: 科学的理解をSolver decisionへ変換できない
- IRD高、TSDR低: Noveltyはあるが高レバレッジStructureへ到達していない
- Individual弱、Population Union強: Communication/Migrationに価値がある可能性
- SharingでTSDR向上、DRR低下: Collective Collapse。共有範囲・時期を縮小

## 17. Real Benchmark Transfer

IEEE-CISはDevelopment Benchmarkとし、Blind Control通過後に同一Prompt/Contractを未使用Competitionへ適用する。Ground-truth StructureがないReal BenchmarkではSealed/Private、Critical Discovery Rediscovery、Decision Sign、False Rejection、Regret、Structure-informed Gain、Population Union、Shadow Recoveryを用いる。Critical DiscoveryはRuntime非公開とする。

## 18. 禁止事項

Reference Probe成功をAgent成功としない。Development SuiteをPrimaryへ再利用しない。失敗後に同じQualification Suiteを修正しない。Structure候補一覧をAgentへ渡さない。名称一致をDiscovery条件にしない。HumanがCode/Test/Candidateを修正しない。Hypothesis数やBelief変化だけを成功としない。Phase 1中にPopulation Summaryを返さない。固定NicheやModel Family強制を再導入しない。

## 19. 実行フロー

```text
Freeze Prompt/Contract
→ Build Development Suite
→ Blindness + Identifiability Preflight
→ Build immutable Qualification Suite
→ Run 3 independent real LLM agents
→ Validate artifacts without truth
→ Lock all hashes
→ Decrypt controller truth
→ Agent/Population/Transfer audit
→ Phase 1 Acceptance
→ Optional checkpointed communication ablation
→ Unused real benchmark
```

中心的因果鎖は次である。

$$Independent\ Agent \rightarrow Diverse\ Research \rightarrow True\ Structure\ Discovery \rightarrow False\ Structure\ Rejection \rightarrow Structure\ Informed\ Decision \rightarrow Sealed/Hidden\ Gain$$

この鎖が成立して初めて、独立Agentの探索多様性とStructure DiscoveryをPopulation Evolutionへ統合する価値を支持する。
