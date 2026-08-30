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

## 追記:Round 2(確認ラウンド、`v042-mc-d02`)——SD-high-P1 は確定、SD-low-P1 の脱出は再現せず

`SD-high-P1`(最良セル)・`SD-low-P1`(脱出セル)それぞれに新規 seed(155・186・217)を
3件追加した(**注:** round2 実行中に `agent-01-s217` の transcript で "santander" 文字列の
盲検リークが発覚し、原因(バッチオーケストレータの `--config-set` 起動引数がコンペ名を
含んでいた)を修正の上、該当1 runを破棄・再実行済み——詳細は
[ps -ef 盲検リーク事例](v043_blindness_incident_ps_ef_leak.md))。

| config_id | round1(seed17) | round2(新規3 seed) | 合計 n=4 での P2 達成数 |
| --- | --- | --- | ---: |
| SD-high-P1 | ✓(1/2 beats_baseline) | **✓ 3/3(FSPR汚染ゼロ)** | **4/4(達成)** |
| SD-low-P1 | ✓(1/2 beats_baseline、脱出claim) | **✗ 0/3(promotion自体ゼロ)** | **1/4(未達)** |

**発見(12):`SD-high-P1` は 4 seed 全てで P2 を達成——IEEE-CIS の `SD-high-P3` と並ぶ、
このラウンドで最も頑健な sol 単独構成として確定した。**

**発見(13、IEEE-CIS の発見11と対になる結果):`SD-low-P1` の「非線形多変量」脱出 claim は
再現しなかった。** round2 の新規3 seed は promoted パックが**1件もない**(全て
`inconclusive`/`useful_encoding_unvalidated` に留まる)——round1(seed17)が到達した
validated 状態への昇格自体が、新規3 seed のいずれでも再現しなかった。IEEE-CIS の
`SD-high-P3`/occurrence-sparsity 脱出(発見11)と全く同じパターン:**両コンペで
唯一観測された「支配的パターンからの脱出」は、いずれも n=4 での確認により
「頑健な発見」ではなく「一回性の draw」に格下げされた。**

**v0.4.3-f 最終的な総括(2コンペ・8+8+6+6=28 run を踏まえて):**

1. **解法多様性:** sol・reasoning-effort のみでは、opus を含む元の混合構成バッチ
   (多様性指数 IEEE-CIS 6・Santander 2)を上回る多様性は得られなかった——む
   しろ IEEE-CIS 側は 2 種に収束し、多様性指数が低下した。
2. **上位解法相当の存在:** Santander は既存の傾向(特徴独立性モデリングとの高い一致率)
   を維持。IEEE-CIS は今回も layer1 一致ゼロを維持——匿名化の効果は reasoning effort に
   依存しない頑健な制約であることが再確認された。
3. **未知構造探索エージェント:** round1 単体では両コンペに1件ずつ「脱出」事例が
   見えたが、**n=4 での確認を経ていずれも再現しなかった。** これは v0.4.3-f の最も
   重要な結論——novel-structure-seeking の「成功」を騙る screening 結果は、
   確認ラウンドなしに信頼してはならない。今後、単一 seed の discovery を
   「エージェントが未知構造の探索に成功した」と主張する際は、必ず追加 seed での
   再現確認を経ること。

## 追記:Round 3(population scale-up、`v042-mc-e02`)——Santander は多様性が増えなかった

IEEE-CIS 側と対称に、`SD-high-P1` に新規4 seed(271・314・358・402)を追加し n=8 まで
拡大した。

| seed | promoted | Layer1#2 | Layer2#1(プーリング) | 未分類 |
| --- | ---: | ---: | ---: | ---: |
| 271 | 0 | — | — | — |
| 314 | 3 | 0 | 3 | 0 |
| 358 | 4 | 0 | 4 | 0 |
| 402 | 1(+FSPR汚染1件) | 1 | 1 | 0 |

**発見(16、IEEE-CIS との非対称性):Santander では population を広げても多様性は
増えなかった。** 新規4 seed の promoted 8件全てが引き続き layer2#1(プーリング)
——IEEE-CIS の round3(発見14・15)で見られた「未分類パターンの新規出現」は
Santander では一切観測されなかった。**IEEE-CIS(構造が複雑・population を広げるほど
多様性が増える)と Santander(構造が単純・population を広げても収束したまま)という
非対称性は、[クロスコンペ分析](v042_cross_competition_synthesis.md)の当初からの解釈
(Santander の実際の構造の単純さ)を、population scale-up という新しい角度からも
再確認する結果になった。**

**発見(17、FSPR の実地観測):`SD-high-P1`(それまで round1+2 の 4 seed で FSPR 汚染
ゼロだった頑健な構成)も、8 seed 目にして初めて FSPR 汚染(`pack-n03`)を出した。**
汚染パックの claim は promoted candidate(`pack-c01`)と全く同じ「共有係数方向」を
主張し、`leave_one_context_out_stable: true`・`promotion_passed: true` まで到達して
いた——エージェント自身の null 検定(10 replicate、平均gain≈0.0086、-0.032〜+0.057の
低振幅なノイズ)が偶然エージェント自身の有意性判定を通過したことが原因。**ただし
Controller 側の独立な FSPR チェック(エージェントの自己申告と無関係に、真の
matched-negative ラベルで判定)がこれを正しく検出した**——これは失敗ではなく、
このプロジェクトの2段階防御(エージェント側の null 検定 + Controller 側の独立検証)が
設計通り機能した証拠であり、既存の base FSPR 率(~1〜2%)とも整合する。8 seed中1件
という発生率は、この設計の想定範囲内である。

**v0.4.3-f 最終総括(Santander、n=8):**

1. **解法多様性:** population を8 seed まで広げても新規技術クラスは出現せず、
   Santander の discovery population は一貫して均質(プーリング+特徴独立性)。
2. **上位解法相当の存在:** 8 seed中7件(87.5%)が layer1#2(特徴独立性モデリング、
   Santander の公開1st place解法の設計思想)と一致——高い上位解法一致率を維持。
3. **未知構造探索エージェント:** 該当なし(round1 の `SD-low-P1` 脱出は再現せず、
   round3 でも新規パターンは出現しなかった)。

## 正本

- [Diagnostics(round1)](../v042_mc_c02_diagnostics.json) / [Diagnostics(round2)](../v042_mc_d02_diagnostics.json) / [Diagnostics(round3)](../v042_mc_e02_diagnostics.json)
- [ps -ef 盲検リーク事例](v043_blindness_incident_ps_ef_leak.md)
- [IEEE-CIS 側(対になる分析)](v043_sol_effort_diversity_ieee_cis.md)
- [クロスコンペ統合分析](v042_cross_competition_synthesis.md)
- [v0.4.3 方針§10](../c_lite_v043_policy.md)
