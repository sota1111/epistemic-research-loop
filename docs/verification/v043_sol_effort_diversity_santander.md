# v0.4.3-f sol reasoning-effort 多様性ラウンド — Santander(`v042-mc-c02`)

**目的:** [IEEE-CIS 側](v043_sol_effort_diversity_ieee_cis.md)と対になる、同一設計
(`V043_SOL_EFFORT_CONFIGS`、sol のみ・reasoning_effort × prompt_arm の 8 run)の
Santander 版。全 run 完了、盲検監査クリーン(2026-08-30)。

## P2 判定・beats_capacity_matched_baseline 結果

| config_id | 生の promotion 数 | P2 満たすパック数 | beats_baseline true 数/promoted 数 |
| --- | ---: | ---: | ---: |
| SD-low-P1 | 2 | 1(pack-c01) | 1/2 |
| SD-medium-P1 | **0** | ✗ | — |
| SD-high-P1 | 4 | 4(全パック) | 4/4 |
| SD-xhigh-P1 | 4 | 3 | 3/4 |
| SD-low-P3 | **0** | ✗ | — |
| SD-medium-P3 | **0** | ✗ | — |
| SD-high-P3 | 4 | 3 | 3/4 |
| SD-xhigh-P3 | 4 | 4(全パック) | 4/4 |

## 発見(5):IEEE-CIS とは異なる形の非単調性——「谷」の位置がコンペごとに異なる

IEEE-CIS 側は **low** effort で 0 promotion(発見の閾値効果)だったのに対し、Santander
側は **medium** effort が P1・P3 両方で 0 promotion という谷になっている(low は部分的に
成功、high・xhigh は好調)。同じ reasoning-effort という単一のレバーが、コンペが変わると
非単調性の「谷」の位置自体が変わる——**「reasoning effort と成果の関係」はコンペ非依存の
普遍的な関数ではなく、コンペ固有の相互作用効果を持つ**ことを示す2例目の直接証拠
(1例目は既存の opus×P1 のコンペ依存性、[クロスコンペ分析](v042_cross_competition_synthesis.md)参照)。

## 発見(6):Santander は high/xhigh で ほぼ全パック promoted・ほぼ全て beats_baseline

`SD-high-P1`(4/4 P2 達成)・`SD-xhigh-P3`(4/4 P2 達成)は、単一 run としては元の
12-run バッチの最良構成(MC-opus-P1 4/4、MC-sol-P3 3/4)に匹敵するかそれを上回る結果。
Santander の構造(200特徴のほぼ独立性・線形分離可能性)は比較的単純であるため、
reasoning effort が一定水準を超えれば model 側の探索余地が少なくても安定して発見できる、
という以前からの解釈([クロスコンペ分析](v042_cross_competition_synthesis.md)の
「解法の多様性」節)と整合する。

## taxonomy 一致・探索幅分析

追記予定(promoted パックの技術クラス照合結果を取得次第)。

## 正本

- [Diagnostics](../v042_mc_c02_diagnostics.json)
- [IEEE-CIS 側(対になる分析)](v043_sol_effort_diversity_ieee_cis.md)
- [クロスコンペ統合分析](v042_cross_competition_synthesis.md)
- [v0.4.3 方針§10](../c_lite_v043_policy.md)
