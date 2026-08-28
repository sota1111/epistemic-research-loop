# v0.3.9 Terminal-resolution Consistency Qualification

## 結論

v0.3.9 Engineering Qualification は **FAIL**(9 Gate 群のうち 5 Pass / 4 Fail)だが、単一介入
(終端 resolution の自己整合性契約)は preregistration の主予測どおりの効果を示した:

- **Median Agent TSRR 0.1875 → 0.6250(3.3 倍)**。agent-01 は 0.7083 で個体として Gate
  (>= 0.67)を通過。Evidence-based 棄却は 27/144 → **93/144**。
- **matched_negative 段階の失敗 27 → 5**(予測どおりの解消)。
- **Worst Agent FSPR 0.2083 → 0.0833 で FSPR Gate が新規 Pass**。False promotion 15 → 9。
- Persistent discovering agents **3/3**(2/3 → 全員)。
- 懸念された「inconclusive への逃げ」は発生せず(negative の falsified 申告 122 → 125)。

| 指標 | v0.3.8 | v0.3.9 | Gate | 判定 |
| --- | ---: | ---: | ---: | --- |
| Median Agent TSDR | 0.1875 | 0.2292 | >= 0.50 | Fail |
| Median Agent TSRR | 0.1875 | **0.6250** | >= 0.67 | Fail(僅差) |
| Worst Agent FSPR | 0.2083 | **0.0833** | <= 0.20 | **Pass(新規)** |
| Shared Blind-spot Rate | 0.7083 | 0.5625 | <= 0.20 | Fail |
| Minimum LOAO TSRR | 0.0000 | 0.5000 | >= 0.67 | Fail |
| Pooled USTR | 1.0000 | 0.9714 | >= 0.50 | Pass |
| Median Structure Gain | +0.2209 | +0.1866 | > 0 | Pass |
| Median Structure Brier | 0.1813 | 0.2043 | <= 0.20 | **Fail(退行)** |
| Median Structure ECE | 0.1055 | 0.1417 | <= 0.20 | Pass |
| Persistent Ladder | 4/4, 2/3 | 4/4, **3/3** | 3/4, 2/3 | Pass |

補足値:

```text
Mean Population-union TSDR   0.2917 -> 0.4375
Mean Population-union TSRR   0.4583 -> 0.9583
Failure funnel               evidence 88 / promotion 16 / matched_negative 5
Negative 144 件の内訳       falsified 申告 125 / Evidence-based 棄却 93 / False promotion 9
```

### Agent 別(8 反復 pooled)

| Agent | TSDR | TSRR | FSPR |
| --- | ---: | ---: | ---: |
| 01 | 0.2708 | **0.7083**(個体 Gate 通過) | 0.0833 |
| 02 | 0.2292 | 0.6042 | 0.0625 |
| 03 | 0.2292 | 0.6250 | 0.0417 |

### Family 別の個体発見(24 反復中、v0.3.8 → v0.3.9)

```text
observation_routing_composition  23 -> 19   (昇格慎重化による退行)
persistent_clear                  2 ->  7
persistent_delayed_history        1 ->  5
persistent_compositional          1 ->  3
persistent_noisy_proxy            1 ->  1
stable_structure_nonactionable    1 ->  0   (implication 要件の直撃)
```

## 汚染検査(開封前に実施、Truth 不使用)

敵対的レビュー(2026-08-28)が指摘した「repair feedback による契約適合の学習が TSRR を
人工的に押し上げる」懸念を 2 系統で検査した。

1. **Repair 挙動の transcript 分析:** repair retry を要した 10 run・13 attempt のうち、
   **12 attempt は実データの再計算を伴い**、提出 JSON の書き換えのみは実質 0
   (1 件は空 attempt 後、次 attempt で再計算)。差し戻しは再検証を誘発している。
2. **層別 TSRR:** repair を要した run の TSRR 0.567(34/60)に対し、**一発で契約 Pass した
   run の TSRR は 0.702(59/84)と高い**。TSRR 上昇は repair loop 内の学習ではなく、
   契約文書を読んだ上での初回からの整合的な棄却行動が主経路である。

以上から、TSRR 改善の大部分は実質と判断する。ただし「契約が要求する形式を最初から満たす能力」
と「証拠に基づく棄却能力」の区別は原理的に完全にはできない(v0.4.0 の implication provenance で
さらに締める)。

## 興味深い副次効果

1. **Persistent 系の発見が動いた:** clear 2→7、delayed 1→5、compositional 1→3(24 反復中)。
   整合性圧力が implication 測定への真剣な取り組みを誘発し、発見側にも波及した可能性がある。
2. **退行 2 件:** observation_routing 23→19、nonactionable 1→0。validated 昇格に
   implication >= 2 contexts を要求したことで、昇格が全体に慎重化した(nonactionable の発見は
   implication 経由でしか成立しないため、直撃を受けた)。Brier の悪化(0.1813→0.2043)も
   resolution の厳格化に confidence 申告が追随していないことを示す。
3. Failure funnel が上流へ移動:matched_negative と promotion が解消に向かい、残る失敗の
   76%(88/116)が evidence 段階に集中。**契約レバーは使い切った**という敵対的レビューの
   予測どおりであり、v0.4.0(能力レバー:構成探索・モデル多様化)への移行根拠が確定した。

## 実行記録

- 24 fresh `claude -p` run(claude-opus-5)。途中 2 回のセッション上限(429)を挟み再開、
  最終 24/24 契約 Pass。repair retry 使用は 10/24。
- Blindness 監査:view 24・transcript 49 とも findings 0。
- 24 run Lock → SHA 再照合 → 開封・集計(評価コードは v0.3.7 以来不変)。
- C1 は v0.3.8 Development fit を preregistration どおり再利用。

## 判定

- 単一介入の効果検証としては**成功**(主予測 2 件的中、リスク予測は不発)。
- Engineering Gate 全体は FAIL のまま。残る欠落は (1) TSDR(evidence 段階 88 件、
  とくに persistent 系と nonactionable)、(2) SBR/LOAO(同一モデル集団の構造的限界)、
  (3) 較正の retuning。
- 次版は [v0.4.0 方針](../c_lite_v040_policy.md) に従い、契約レバーを凍結して
  構成探索(Track A)と IEEE-CIS 橋(Track B)へ移行する。Checkpoint 1(汚染検査)は通過。

## 正本

- [Preregistration](../v039_preregistration.json)
- [Qualification Result](../v039_qualification_result.json) /
  [Scorecards](../v039_agent_reproducibility_scorecards.json) /
  [Blind Spots](../v039_population_blind_spot_report.json) /
  [Failure Traces](../v039_structure_failure_traces.json) /
  [Null Audit](../v039_full_refit_null_audit.json)
