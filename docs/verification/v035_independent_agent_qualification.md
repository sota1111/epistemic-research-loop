# v0.3.5 Independent Agent Qualification verification

## Outcome

v0.3.5のAgent-local Portfolio、3-mode Proposal、Shadow Archive、Local Stagnation、個別/Population
Scorecard、Blind Structure Control、Aggregate-only Promotion、Calibration、Structure Transferを実装した。

Qualification preflightは全Engineering Gateを通過した。ただし、これはv0.3.4 IEEE-CIS Pilotの
事後監査とSynthetic Reference Probeの結果であり、新しいLLM Multi-agent RunやKaggle Hidden/Private
評価ではない。

## 試行錯誤

### Trial 0 — Blind API audit: Fail

最初のAPIはAgentメソッドへ`BlindStructureControl`全体を渡し、Opaque IDにもGenerator Seedを残していた。
学習時にSealed Labelを使ってはいなかったが、同じObject内にController Truthが存在し、型とIdentifierの
双方でBlindnessを保証できなかった。

修正:

- Agent APIを`investigate(AgentControlView)`へ限定
- Opaque IDをhash化し、Null用Analysis SeedをGenerator Seedから分離
- Agent outputはSealed PredictionとResearch Evidenceのみ
- Family/Polarity/Sealed AUC/正解Operator照合はController側でのみ実行

### Trial 1 — Uncentered temporal probe: Partial

Null、Independent Implication、Multi-context Gateを入れたGeneric Probeを8 Family × 3 Seedへ適用した。

| Metric | Result |
| --- | ---: |
| TSDR | 0.75 |
| TSRR | 1.00 |
| FSPR | 0.00 |
| USTR | 1.00 |

P1 Entity、P3 Observation、P4 Routingは発見したが、P2 Temporalを`repeated_unit_history`として選択し、
Null/Independent Gateで棄却した。原因は`signal × time`がEarly Research Windowで元の`signal`係数へ
吸収され、正しいTemporal Operatorの識別力が落ちたことだった。

### Trial 2 — Orthogonalized temporal probe: Pass

ThresholdやNegative Controlを緩和せず、Temporal interactionをEarly Research Windowで中心化した。

| Metric | Result |
| --- | ---: |
| TSDR | 1.00 (4/4) |
| TSRR | 1.00 (4/4) |
| FSPR | 0.00 (0/4) |
| USTR | 1.00 (4/4) |
| Median Structure Sealed Gain | +0.306750 |
| Brier Score | 0.060912 |
| Expected Calibration Error | 0.172518 |

全Positive Familyを3/3 Seedで正しい汎用Operatorへ対応付け、全Negative Familyを0/3 supporting
seedとして棄却した。全Positive Promotionは各Leave-one-seed-outでも維持された。

## Independent Agent retrospective

v0.3.4の3 Agent × 3 Cycleをv0.3.5 Scorecardで再評価した。

| Metric | Result |
| --- | ---: |
| Qualifying agents | 3/3 |
| IRD | 1.00 |
| Population Effective Research Family | 5.669645 |
| Dominant Family Fraction | 0.222222 |
| Action Types | 4/4 |
| Dominant Action Fraction | 0.333333 |
| Shadow candidates | 5 |
| Shadow Candidate Recovery Rate | 0.80 |

Action mixはE1=3、E2=2、E3=3、E4=1だった。island-02のLocal Parent維持はSealed Oracleに対して
`0.007600`のRegretを持ち、Shadow Archiveが必要というv0.3.4の観測を再確認した。

## Reliability

- Artifact Contract Completion: 100%（v0.3.4 Pilot 9/9 Cycle、3/3 Candidate）
- OOF Honesty: 100%（3/3 Common Cross-fit）
- Sealed Isolation: 100%
- New unit tests: 9
- Hidden / Private / Leaderboard query: なし

## Interpretation

実装したContractは、ControllerがNicheを指定せず、Agent自身のPortfolioと履歴から探索・進化・反証を
切り替える。棄却CandidateをGlobal Final Evaluationから消さないため、Agent Research Selectionと
System Final Selectionも分離した。

Control SuiteはStructure ValidatorのPrecision/Recallをテストできる状態になったが、Reference Probeは
既知の汎用Operator集合を機械実行するHarnessである。これを「LLM Agentが未知構造を発見した」と解釈しては
ならない。次の実証段階は、同じPrompt/ContractをBlind Familyを知らない実Agentへ適用し、生成仮説と実装を
人手で補助せずにTSDR/TSRR/USTRへ接続することである。

Machine-readable results:

- `docs/v035_qualification_result.json`
- `docs/v035_agent_scorecards.json`
- `docs/v035_population_scorecard.json`
- `docs/v035_structure_control_report.json`
