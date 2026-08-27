# v0.3.7 Agent Reproducibility and Blind-spot Verification

## 結論

v0.3.7 Engineering Qualificationは**FAIL**だった。

4つの新規Suiteに対する24 Agent評価では、P1 Assumption Challengeと一部Deep-lineage Policyに弱い改善傾向はあった。しかし、厳格なBehavioral Discovery、対応NegativeのEvidence-based rejection、Controller再計算LOCOを適用すると、Median Agent TSDR/TSRR、FSPR、Shared Blind-spot、Persistent Ladder、CalibrationのGateを満たさなかった。

一方、厳格Gateを通過した少数のActionable Structureは6/8でTransferし、Pooled USTRは0.75、Median Structure Gainは+0.09431だった。したがって主なBottleneckは、発見後のTranslationではなく、Structureを安定して発見・反証する前段にある。

## 実装

以下を追加した。

- 4 SuiteをPrompt/Policy変更前に一括生成・LockするBuilder
- Persistent-unit 4-level Ladderと各LevelのMatched Negative
- Observation×Routing、Non-actionable Structure、Encoding-only、Random Routing Control
- P0/P1 Assumption Challenge Ablation
- S0 deterministic / S1 posterior commit / S2 two-hit maturationのLatin-square割当
- 4分解ConfidenceとDevelopment-only calibration utility
- Agent申告/Controller判定を分けるFailure Trace
- 5–30回のSequential full-refit null Contract
- Structure Confirmation / Transfer Sealed分離
- Agent identity、Agent×Sampling condition、Suite×Sampling population集計
- Wilson interval、SBR、DC、RC、MAC、LOAO、USTR、EECR
- Output Lock後のSubmission/Packet/Prompt/Encrypted Truth SHA再照合
- Shadow TranslationのSelection Regret

正本は次である。

- [差分仕様](../c_lite_revision_v0.3.7.md)
- [Preregistration](../v037_preregistration.json)
- [Agent scorecards](../v037_agent_reproducibility_scorecards.json)
- [Population blind spots](../v037_population_blind_spot_report.json)
- [Failure traces](../v037_structure_failure_traces.json)
- [Qualification result](../v037_qualification_result.json)
- [Full-refit null audit](../v037_full_refit_null_audit.json)

## 実行設計

```text
4 locked suites
× 3 generic agent identities
× 2 sampling conditions
= 24 suite-level agent evaluations
```

実行は6つのLLM Agent trajectoryがそれぞれ4 Suiteを処理した。各Suiteは独立Dataset/opaque viewで、Agentは他Agent結果、Truth、Family、Polarity、Hidden labelを見ていない。ただし同一trajectory内では実装経験を持ち越し得るため、これは**24 fresh-context LLM runsではない**。ConfirmatoryではSuiteごとにfresh contextを要求する。

全Agent output 24件はArtifact Contractに合格し、SHA256 Lock後にTruthを開封した。Agent-visible 24 viewのTruth leakageは0だった。

## 試行錯誤

### Trial 0 — Nested Contract不足を開封前に検出

最初に生成した`v037-repro-01..04`は、Agent-visible contractがNested proposal/context/translation schemaを十分に示していなかった。3 Agentの初期実行を中断し、Truthを開封せず、このSuite IDを再利用しなかった。

Nested Contractを固定した後、新しい`v037-repro-b01..b04`を生成・LockしてPrimaryへ使用した。この失敗はAgent研究能力ではなくInfrastructure failureとして除外した。

### Trial 1 — Runtime自己修正

PrimaryではAgentが次を自律修正した。

- `python` alias不在を`python3`へ変更
- scikit-learn不在をNumPy/SciPy実装へ変更
- Agent 02のFold hash/Lineage ID整合性
- Agent 01のnested packet pathと一時syntax error
- Agent 03のthread contentionをsingle-thread BLAS再実行で解消

HumanはHypothesis、Feature、Operator、Candidate選択を追加していない。全Submissionの`human_assisted=false`、`cross_run_information_used=false`、Artifact validを確認した。

### Trial 2 — Sampling-seedを跨ぐSBR過小評価を修正

初回Evaluatorは、一方のSampling conditionで発見したFamilyにより他方の共有Missを救済していた。これは再現性を過大評価するため、Suite × Sampling conditionをPopulation Blockとし、SBRをBlock平均へ変更した。

OutputやTruthは変更していない。

### Trial 3 — Discovery/TSRRの過大評価を修正

独立Auditで次を検出した。

1. Confirmation上でTranslationを事後最大化していた
2. Persistent Positiveに対応Negativeの棄却を要求していなかった
3. Agentが`FALSIFIED`と書くだけでTSRRへ算入していた
4. LOCOがAgent自己申告だった

Evaluatorを次へ修正した。

- ConfirmationはResearch中にLockした`selected_translation_id`だけを使用
- Persistent discoveryは同じAgent/SuiteのMatched NegativeがEvidence-based rejectされた場合だけ算入
- TSRRはNull非棄却、Independent implication不成立、Confirmation非再現、causal/full-refit contractを要求
- LOCOを3 ContextのHidden confirmation/implicationからController再計算
- Agent-reported failure stageとController-adjudicated stageを分離

厳格化により見かけのTSDR/TSRRは低下した。これはPolicyの事後変更ではなく、Preregistered claimと評価実装の不整合修正である。

## 最終結果

### Engineering Gate

| 指標 | 結果 | Gate | 判定 |
| --- | ---: | ---: | --- |
| Median Agent TSDR | 0.0833 | >= 0.50 | Fail |
| Median Agent TSRR | 0.0208 | >= 0.67 | Fail |
| Worst Agent FSPR | 0.3333 | <= 0.20 | Fail |
| Shared Blind-spot Rate | 0.7917 | <= 0.20 | Fail |
| Minimum LOAO TSRR | 0.0000 | >= 0.67 | Fail |
| Pooled USTR | 0.7500 | >= 0.50 | Pass |
| Median Structure Gain | +0.09431 | > 0 | Pass |
| Median Structure Brier | 0.2614 | <= 0.20 | Fail |
| Median Structure ECE | 0.1826 | <= 0.20 | Pass |
| Persistent Levels | 1/4 | >= 3/4 | Fail |
| Persistent discovering Agents | 1/3 | >= 2/3 | Fail |

Pooled uncertaintyは次だった。Wilson intervalはPack間/Suite内相関を無視するため、記述値に限定する。

```text
TSDR  0.0833  Wilson 95% [0.0483, 0.1400]  n=144 positives
TSRR  0.0278  Wilson 95% [0.0109, 0.0692]  n=144 negatives
FSPR  0.1111  Wilson 95% [0.0696, 0.1729]  n=144 negatives
```

### Agent identity別

| Agent | TSDR | TSRR | FSPR | USTR | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 0.1250 | 0.0625 | 0.3333 | 0.0000 | 0.3204 | 0.2733 |
| 02 | 0.0833 | 0.0208 | 0.0000 | 1.0000 | 0.2462 | 0.1826 |
| 03 | 0.0417 | 0.0000 | 0.0000 | 1.0000 | 0.2614 | 0.0757 |

v0.3.6でAgent 03へ見えたFalsification偏重は再現しなかった。今回はAgent 01だけがFalse promotionを多発し、Agent 03のEvidence-based TSRRは0だった。したがって、固定的な「強いFalsifier Agent」が存在するというより、Sampling/trajectory依存が大きい。

### PopulationとFunctional Diversity

```text
Mean Population-union TSDR       0.2083
Mean Population-union TSRR       0.0833
Mean Population-union FSPR       0.3333
Shared Blind-spot Rate            0.7917
Mean Discovery Complementarity    0.0208
Mean Rejection Complementarity    0.0208
IRD                               0.7083
Population Effective Families    14.3505
Dominant Family Fraction          0.1250
Action Types                      3
EECR                              0.1510
Deep Lineage Completion           0.5972
```

Semantic Familyは多いが、Discovery/Rejection Complementarityは各0.0208に留まった。高いSemantic Diversityは重要構造の機能的Coverageを保証しなかった。

### Structural Coverage

数字は8反復中のBehavioral Discovery件数である。

| Family | Agent 01 | Agent 02 | Agent 03 |
| --- | ---: | ---: | ---: |
| Persistent clear | 0 | 0 | 0 |
| Persistent noisy proxy | 0 | 0 | 0 |
| Persistent delayed history | 1 | 0 | 0 |
| Persistent compositional | 0 | 0 | 0 |
| Observation × routing | 1 | 4 | 2 |
| Stable non-actionable structure | 4 | 0 | 0 |

Persistent LadderはL3の1件だけがPositive support、LOCO、対応Negative rejectを同時に通過した。v0.3.6の「全Miss」から完全には脱しておらず、P1の一件を除き共有Blind spotのままだった。

### Failure Stage

未発見Positive 132件のController判定は次だった。

```text
Evidence不足          77
Promotion Gate不足    45
Matched Negative不足  10
```

Agent自己申告ではHypothesis/Test/Implementationを全Packで完了したためStage A–Cは0だったが、これは自然言語/boolean自己申告に依存する。ConfirmatoryではProposal artifactと実行provenanceからA–CもController判定する必要がある。

## Ablation結果

### Prompt P0 vs P1

| Arm | Mean TSDR | Mean TSRR | Mean FSPR | Median TSDR | Persistent Discovery |
| --- | ---: | ---: | ---: | ---: | ---: |
| P0 | 0.0694 | 0.0278 | 0.1667 | 0.0000 | 0/48 |
| P1 | 0.0972 | 0.0278 | 0.0556 | 0.0833 | 1/48 |

P1は具体解を注入せず、TSDRを小幅に上げ、FSPRを下げ、唯一のPersistent discoveryを生成した。ただし1/48であり、採用を確定する再現性はない。

### Lineage S0/S1/S2

| Policy | Mean TSDR | Mean TSRR | Mean FSPR | Persistent Discovery |
| --- | ---: | ---: | ---: | ---: |
| S0 deterministic | 0.1042 | 0.0208 | 0.1458 | 0/32 |
| S1 posterior commit | 0.0833 | 0.0417 | 0.1042 | 1/32 |
| S2 two-hit maturation | 0.0625 | 0.0208 | 0.0833 | 0/32 |

S1/S2はS0よりFSPRを下げたが、TSDRを一貫して上げなかった。Deep Lineage Completionの中央値も0.582–0.587でほぼ同じで、Policy実装が想定した「深い探索」を十分に分離できていない。

## DiscoveryとTransfer

Behavioral Gateを通過したActionable Structureは8件、Positive Transferは6件だった。

```text
Pooled USTR             0.750
Median Structure Gain  +0.09431
Gain range              -0.00531 .. +0.21406
```

TransferはPassだが、少数の発見済みStructureを条件にした値である。`median_ustr=1.0`はAgent別USTRの中央値で、分母がないAgentを除くため上方に偏る。PrimaryにはPooled USTR 0.75を用いる。

## Calibration

Raw Confidence C0だけを評価した。Median Agent Brier 0.2614でFail、Median ECE 0.1826はPassだった。Agent 01のBrier/ECEは0.3204/0.2733で特に悪い。

Development-only Isotonic Map（C1）とCalibration-adjusted Evidence Gate（C2）は実装・Unit Test済みだが、専用Development Agent runを行っていないため**UNMEASURED**である。Qualification TruthをCalibration fitへ再利用していない。

## Reliabilityと限界

1. Artifact Contractは24/24、Truth leakageは0/24、Lock SHA再照合はPassした。
2. 全288 Packが5–30回のfull-refitを自己申告したが、per-replicate feature/fold/model/OOF hashを保存していない。Full-refit provenanceは**PARTIAL**である。
3. 24評価は6 LLM trajectory × 4 Suiteであり、24 fresh-context runではない。
4. Wilson intervalはPack independenceを仮定する。ConfirmatoryではSuite/Family cluster bootstrapまたは階層Modelが必要である。
5. Agent申告のFailure A–C、Lineage follow-up、null preserved-statisticsは完全には監査できない。
6. 共有HostのPath Policy隔離であり、Container mount隔離ではない。
7. Synthetic Generator系統内のPilotであり、未使用Real Benchmark一般化は未測定である。
8. Communication M0–M4は、個体Gate Failのため実行していない。

## 判定と次の試行

今回の結果はCase A/Cの混合である。

- TSDR/TSRRが低く、Evidence-based resolution能力が不足
- 一度正しくValidatedできたStructureは比較的高率で性能へ転送
- P1は有望だが効果は小標本
- S1/S2は設計意図どおりのDeep exploration差を作れていない

次の優先順位は次とする。

1. Agentごと・Suiteごとのfresh LLM context化
2. Null Replicate provenance artifactの必須化
3. P1を固定してS1/S2の継続をControllerが履歴から強制・監査
4. Matched Negativeを含むEvidence-based Falsification bundleの改善
5. C1/C2をDevelopment Suiteだけでfitして新Qualification Suiteへ適用
6. Container mount隔離
7. 新Generator/未使用Real Benchmark

Agent単体Gateを通過する前にCommunicationやAgent scalingへ進まない。

## 再現コマンド

```bash
uv run python scripts/build_v037_reproducibility_suites.py --rows-per-context 900
uv run python scripts/audit_v037_blindness.py
# Agent実行後
uv run python scripts/lock_v037_agent_runs.py
uv run python scripts/finalize_v037_reproducibility.py --output-root docs
```

Suite IDとTruthは一度開封済みのため再利用禁止である。
