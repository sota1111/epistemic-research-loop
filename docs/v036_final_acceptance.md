# v0.3.6 Final Acceptance

## 判定

**Phase 1 Engineering Qualification: PASS**

3実LLM Agentは、固定Niche、Family/Polarity、Generator、Reference Probe、Sealed Label、他Agent情報、人間によるHypothesis/Code修正なしで、各8 Pack × 4 Cycleを完了した。全3 SubmissionをHash Lockした後にのみController Truthを復号した。

| Acceptance | 結果 | 判定 |
| --- | ---: | --- |
| Blindness leakage | 0 | Pass |
| IRD | 1.000 | Pass |
| Population Effective Family | 9.642 | Pass |
| Dominant Family Fraction | 0.219 | Pass |
| Action Types | 4 | Pass |
| EECR | 0.375 | Pass |
| Population Union TSDR | 0.750 | Pass |
| Population Union TSRR | 1.000 | Pass |
| Population Union FSPR | 0.000 | Pass |
| Structure Resolution Rate | 0.792 | Pass |
| Brier | 0.1789 | Pass |
| ECE | 0.1515 | Pass |
| USTR | 0.875 | Pass |
| Median Structure Sealed Gain | +0.01960 | Pass |
| Artifact / OOF / Sealed Isolation | 100% | Pass |
| Human-assisted Primary Runs | 0 | Pass |

Wilson 95%区間はTSDR `[0.301, 0.954]`、TSRR `[0.510, 1.000]`、FSPR `[0.000, 0.490]`である。Pack数が4+4のPilotであるため、不確実性は大きい。

## Agent別

| Agent | TSDR | TSRR | FSPR | USTR | SRR | Brier | ECE | Mean Regret |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 0.50 | 0.00 | 0.00 | 0.50 | 0.75 | 0.176 | 0.187 | 0.00289 |
| 02 | 0.75 | 0.00 | 0.00 | 1.00 | 0.625 | 0.340 | 0.341 | 0.00257 |
| 03 | 0.75 | 1.00 | 0.00 | 1.00 | 1.00 | 0.020 | 0.109 | 0.00055 |

Population Passは各Agentが同程度に強いことを意味しない。Negative Packの明示的FalsificationはAgent 03に依存し、Agent 01/02は多くを`INCONCLUSIVE`または`USEFUL_ENCODING_UNVALIDATED`に留めた。Agent 02は発見Recallが高い一方でCalibration Gateを個別には通過していない。

## Structure結果

- changing temporal relation、observation-regime interaction、conditional/compositional mechanismの3/4 Positive PackをPopulationがValidatedした。
- persistent-unit dependenceは3 AgentともValidatedへ到達せず、Population Union TSDRは0.75に留まった。
- Agent 03は4 Negative Packすべてを明示的にFalsifyした。全AgentでFalse Promotionは0だった。
- 8つのBehaviorally Validated Agent×Packのうち7つがPositive Sealed Gainを持ち、USTRは0.875だった。
- Agent 01のTemporal StructureはResearch上ValidatedだったがMedian Sealed Gain `-0.01446`で、構造発見と性能転送が同義でない反例になった。

## Selection

- Population Selectable mean AUC: `0.51933`
- Population Oracle mean AUC: `0.52055`
- 差: `0.00122`
- Shadow Candidate Recovery Rate: `0.625`

Raw AUCは異なるSynthetic Packの平均であり、Competitionスコアとして解釈しない。ここで重要なのはAgent-selectedとShadow Oracleの差、およびMatched Structure Gainである。

## 結論境界

本結果はBlind Synthetic Qualificationに対するEngineering Passである。次はまだ未測定である。

- Confirmatory 8 Positive + 8 Negative Suite
- Kernel/containerによるAgent Runtimeの物理隔離
- Evidence/Debt/Candidate/Full Sharingの効果
- IEEE-CISへの新しいHidden Transfer
- 未使用Real Benchmarkへの転送
- System CのB/B+に対するOutcome Advantage

Phase 2はM0 IndependentのみMeasuredで、M1–M4はUNMEASUREDのままとした。Phase 1のPassを見て同じSuite上で共有Policyを調整すると汚染するため、Communication Claimは行わない。
