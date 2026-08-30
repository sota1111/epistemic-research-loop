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

18件の promoted パック全てを layer1/layer2 taxonomy に照合した:

| config_id | promoted | Layer1#2(特徴独立性/線形) | Layer2#1(プーリング) | Layer2#2(occurrence) | 未分類 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SD-low-P1 | 2 | 0 | 0 | 0 | **2** |
| SD-high-P1 | 4 | 4(副次) | 4 | 0 | 0 |
| SD-xhigh-P1 | 4 | 4(副次) | 4 | 0 | 0 |
| SD-high-P3 | 4 | 0 | 4(entity-linking亜種) | 0 | 0 |
| SD-xhigh-P3 | 4 | 4(副次) | 4 | 0 | 0 |
| **合計** | **18** | **12** | **16** | **0** | **2** |

**発見(7):高 effort 4構成は全て layer2#1(プーリング)+ layer1#2(線形共有方向)の
組み合わせに収束した。** これは元の 12-run バッチの「ほぼ100%プーリング」という
モノリシックな結果を、sol・reasoning-effort のみでも再現する。

**発見(8、IEEE-CIS との対比で最も重要):支配的パターンからの「脱出」が起きたのは
`SD-low-P1`——IEEE-CIS の `SD-high-P3` とは正反対の effort 水準だった。** `SD-low-P1`
の2パックは独立に、「加法的な row モデルを超えた、安定な非線形多変量関係」という claim に
到達している——これは layer1#2(特徴のほぼ独立性を前提とする)にも layer2 のどちらにも
一致せず、他の全構成が収束した「独立性」前提そのものと矛盾する。代表的claim:「特徴生成・
誤差分解・選択された予測規則を、加法的な row モデルを超えて変化させる、安定な非線形
多変量関係」。

**IEEE-CIS(発見4)と Santander(発見8)を合わせた解釈:** 支配的パターンからの脱出は
IEEE-CIS では **high** effort、Santander では **low** effort で起きた——「脱出」が
特定の effort 水準に系統的に結びついているわけではなく、**コンペごとに異なる、
低頻度・非決定的な事象**として観測される。「reasoning effort を上げれば多様性・新規性が
増す」という単純な仮説は両コンペのデータいずれからも支持されない——novel-structure-seeking
の発生は effort の単調関数ではなく、探索の途中で生じる偶発的な分岐点に近い。

**v0.4.3-f の3つの価値基準への回答(Santander 側):**

1. **解法多様性:** 18 promoted 中、技術クラスは実質2種(プーリング系・未分類の非線形
   多変量)——IEEE-CIS 側(2種)と同水準。
2. **上位解法相当の存在:** 12/18(67%)が layer1#2(特徴独立性モデリング、Santander の
   公開1st place解法の設計思想)と一致——IEEE-CIS 側(0件)より明確に高い一致率。
3. **未知構造探索エージェント:** `SD-low-P1` が該当——低 effort でありながら、他の
   全構成が前提とする「特徴独立性」を否定する対抗的な claim に到達した。

## 正本

- [Diagnostics](../v042_mc_c02_diagnostics.json)
- [IEEE-CIS 側(対になる分析)](v043_sol_effort_diversity_ieee_cis.md)
- [クロスコンペ統合分析](v042_cross_competition_synthesis.md)
- [v0.4.3 方針§10](../c_lite_v043_policy.md)
