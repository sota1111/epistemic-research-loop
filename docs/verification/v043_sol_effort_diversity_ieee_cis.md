# v0.4.3-f sol reasoning-effort 多様性ラウンド — IEEE-CIS(`v042-mc-c01`)

**目的:** [c_lite_v043_policy.md](../c_lite_v043_policy.md) §10。Claude(opus)側のクォータが
枯渇したため、モデル多様性のレバー(opus vs sol)を reasoning-effort 多様性のレバー
(low/medium/high/xhigh)に置き換え、sol(codex/gpt-5.6-sol)のみで IEEE-CIS 上の
discovery population を追加観測する。1 effort レベル × 1 seed(screening 設計、
P2 再現性の確定ではなく効果の有無・方向性を見るための第一段階)。

**構成:** `V043_SOL_EFFORT_CONFIGS`(8 run)= reasoning_effort ∈ {low, medium, high, xhigh}
× prompt_arm ∈ {p1, p3}、seed は各 4 通り固定(17/42/93/124)。全 run 完了、盲検監査
クリーン(2026-08-30)。

## P2 判定・beats_capacity_matched_baseline 結果

| config_id | 生の promotion 数 | P2 満たすパック | beats_baseline true 数/promoted 数 |
| --- | ---: | --- | ---: |
| SD-low-P1 | 0 | ✗ | — |
| SD-medium-P1 | 4 | ✗ | 0/4 |
| SD-high-P1 | 4 | ✓(pack-c04) | 1/4 |
| SD-xhigh-P1 | 4 | ✓(pack-c04) | 1/4 |
| SD-low-P3 | 0 | ✗ | — |
| SD-medium-P3 | 3 | ✓(3パック) | 3/3 |
| SD-high-P3 | 3 | ✓(pack-c01) | 1/3 |
| SD-xhigh-P3 | 3 | ✗ | 0/3 |

## 発見(1):low effort は構造発見に到達しない

`SD-low-P1`・`SD-low-P3` はいずれも 4 候補パック中 0 件しか validated 系の resolution に
到達しなかった(raw promotion 数がゼロ)——reasoning effort が最低水準では、この
プロトコル(preregister → null → LOCO → attack cycle 等の手続き要求)を完走して
validated 状態まで持ち込めていない可能性が高い。medium 以上では 3〜4 件の raw promotion
に到達しており、閾値効果があることが示唆される。

## 発見(2):reasoning effort は単調に性能を改善しない

`beats_capacity_matched_baseline`(独立再計算された transfer AUC が capacity-matched
baseline を上回るか)の一致率は次の通り、**effort に対して非単調**:

- P1 系:medium 0/4 → high 1/4 → xhigh 1/4(medium だけが全滅、high 以降で頭打ち)
- P3 系:medium **3/3(全勝)** → high 1/3 → xhigh **0/3(全敗)**

特に P3 系で **xhigh が最も beats_baseline 率が低い**(0/3)——これは agent 側の自己申告
resolution(「validated」への到達)と、Controller 側で独立再計算した実際の transfer 性能が
乖離しているケースであり、reasoning effort を上げるほど自信(validated への到達率)は
上がるが、その自信が実際の性能改善と伴わない場合があることを示す。**medium effort ×
P3 が今回の 8 run 中で最も良好な結果(3/3 beats_baseline)だったことは、「効果は
reasoning effort に対して単調」という素朴な予想に対する明確な反証。**

(n=1/セルの screening 段階であり、上記の非単調性が真の効果かノイズかは追加 seed での
再現確認が必要——今回はまず sol 単独での効果の有無・方向性を見る位置づけ。)

## taxonomy 一致・探索幅分析

追記予定(promoted パックの技術クラス照合結果を取得次第)。

## 正本

- [Diagnostics](../v042_mc_c01_diagnostics.json)
- [クロスコンペ統合分析](v042_cross_competition_synthesis.md)
- [v0.4.3 方針§10](../c_lite_v043_policy.md)
