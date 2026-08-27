# v0.3.7 Final Acceptance

**Overall: FAIL — Engineering Pilot only**

| Layer | Status |
| --- | --- |
| Blindness / Hash lock | PASS |
| Artifact contract | PASS |
| Independent research diversity | PARTIAL |
| Median Agent TSDR | FAIL |
| Median Agent TSRR | FAIL |
| All-agent FSPR | FAIL |
| Shared blind spots | FAIL |
| Leave-one-agent-out rejection | FAIL |
| Persistent ladder | FAIL |
| Raw calibration | FAIL |
| Structure transfer | PASS |
| Full-refit provenance | PARTIAL |
| 24 fresh-context independence | FAIL |
| Communication ablation | UNMEASURED |
| Unused real benchmark | UNMEASURED |

厳格評価ではMedian Agent TSDR 0.0833、TSRR 0.0208、Worst FSPR 0.3333、SBR 0.7917だった。Actionable StructureのPooled USTR 0.75とMedian Gain +0.09431はPassしたが、前段の発見・反証能力がGate未達である。

P1 Assumption ChallengeはP0よりMean TSDRが高く、Mean FSPRが低かったが、Persistent discoveryは48件中1件だけである。Deep-lineage S1/S2にも一貫したTSDR改善はなく、Communicationへ進む根拠は不足している。

詳細は[verification report](verification/v037_agent_reproducibility_and_blind_spots.md)を参照する。
