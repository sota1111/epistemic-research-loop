# IEEE-CIS v0.3.2 verification result

v0.3.2の凍結Hidden評価と因果分解を実施した。Private AUCはArchive Best `0.909654`、W02 Single `0.899993`、Locked Nested Ensemble `0.914784`である。

```text
delta_single   = -0.009661
delta_ensemble = +0.005130
```

LocalではW02 Single `0.909749`、Ensemble `0.917213`だったが、PrivateではW02単体順位が逆転した。W02はStandaloneなHidden改善ではなく、Archiveとの補完要員としてのみ転送した。Local→Private Spearmanは`0.4`である。

DebtはPD-1 Resolved、PD-2 Partial（Effective Rank `1.116561 < 1.2`）、PD-3 Resolvedと判定した。

W02 A–F FactorialではMissingness TopologyがLightGBMで`+0.002025`、ExtraTreesで`+0.002469`、Category hashがLightGBMで`+0.023077`、ExtraTreesで`+0.034721`だった。Topology差の500回Temporal block bootstrap CIは両Learnerで正だが、主要因はHashである。W02をStructural Hypothesisへ昇格せず、`USEFUL_REPRESENTATION_WITH_PREREGISTERED_SLICE_SUPPORT`を維持する。

Eligibility分離ではW01はEnsembleのみPass、W02はStandalone/EnsembleともPass、W03はSeed instabilityにより両方Failだった。

Structure ControlはPositive 3/3をPromotionし、Negativeは3 Seed全体GateでRejectしたが、per-seedでは1/3を誤Promotionした。このためTrue Structure DiscoveryはPartial Passとする。

B/B+/Cは36-run sealed policy preflightまで完了したが、実測CPUが一致せず、同一LLMを使うIEEE-CIS live matched-budget比較ではない。`incremental_value_over_strong_qd`はUnmeasuredのままである。

最終Acceptance:

- Control Plane / Artifact / Common Cross-fit / Semantic Diversity: Pass
- Quality-conditioned Predictive Diversity: Pass
- Archive-wide Breadth: Partial
- Structural Falsification: Pass
- True Structure Discovery: Partial Pass
- Primary Hidden Endpoint: Pass
- Incremental Value over Strong QD: Unmeasured
