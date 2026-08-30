# v0.4.4-b 全特徴量 sol reasoning-effort ラウンド — IEEE-CIS(`v044-suite-a01`)

**目的:** [c_lite_v044_policy.md](../c_lite_v044_policy.md)。10列制約を撤廃した全特徴量
設計(106列)で、v0.4.3-fと同じ8構成(sol・reasoning_effort × prompt_arm)の
screeningラウンドを実施し、10列制約下との結果を直接比較する。

**構成:** `V044_SOL_EFFORT_CONFIGS`(8 run)= reasoning_effort ∈ {low, medium, high,
xhigh} × prompt_arm ∈ {p1, p3}、sol(codex/gpt-5.6-sol)のみ、全106列、research
5,000行・confirmation 1,500行(疑似採点ループ、上限20回)・transfer 1,500行(封印)。
盲検監査クリーン(2026-08-30)。

## 結果:8/8構成が reference baseline を上回った(10列制約下とは対照的)

| config_id | transfer AUC | reference baseline (0.7903) 超え | confirmation呼び出し回数 |
| --- | ---: | :---: | ---: |
| F4-low-P1 | 0.8262 | ✓ | 19 |
| F4-medium-P1 | 0.8294 | ✓ | 20 |
| F4-high-P1 | 0.8029 | ✓ | 20 |
| F4-xhigh-P1 | **0.8397**(最良) | ✓ | 20 |
| F4-low-P3 | 0.8233 | ✓ | 18 |
| F4-medium-P3 | 0.8278 | ✓ | 17 |
| F4-high-P3 | 0.8283 | ✓ | 20 |
| F4-xhigh-P3 | 0.8183 | ✓ | 20 |

**発見(1、最重要):10列制約下の v0.4.3-f では reasoning effort に対して非単調・
不安定な成否パターン(低effortで0promotion、medium effortでFSPR汚染等)だったのに
対し、全特徴量下では8/8構成全てが安定して baseline を上回った。** 列制約という
ボトルネックが外れたことで、effort/arm の違いによる成否のばらつき自体が大幅に縮小した
——「reasoning effortの非単調性」という v0.4.3-f の主要な発見の多くは、列制約という
別のボトルネックが効いていたことによる artifact だった可能性が高い。

## 発見(2):layer1(上位解法技術クラス)一致率が 0% から大きく改善した

| 技術クラス | 10列制約下(全ラウンド累計) | 全特徴量下(本ラウンド、8 run) |
| --- | ---: | ---: |
| Layer1 #5(adversarial validation) | 0/90+ run | **4/8 run** |
| Layer1 #6(複数GBMアンサンブル) | (部分的に既存) | 8/8 run |
| Layer1 #1〜4(UID復元・時間集約・時間差・カテゴリエンコーディング) | 0 | 0(引き続き未到達) |

**IEEE-CIS の公開1st place解法が明示的に採用する技術クラス#5(train/test の
adversarial validation)に、8run中4runが独立に到達した**——`agent_submission.json`の
`approach_summary`に「Adversarial cohort classifiers had AUC only 0.5207 for
research-vs-confirmation...」等、定量的な分布シフト検定として明確に記述されている。
これは10列制約下では一度も観測されなかった技術クラスであり、**匿名化そのものではなく
列数不足が主要な阻害要因だった**という[インシデント記録](v044_ten_column_constraint_incident.md)
の仮説を直接裏付ける結果である。

## 発見(3):新しい技術クラス候補——正確重複行の既知ラベル照合

taxonomy未収載の新パターンが4/8 runで独立に観測された:confirmation/transfer領域の
特徴ベクトルが research 領域の行と完全一致する場合、その既知ラベル(research内での
正解)を使って予測を補正する、という手法。代表例(agent-01-s93、high-P1):「Exact
feature-vector duplicate analysis found that all labeled research duplicates were
consistently negative; lowering predictions for exact matches to labeled negatives
improved depth 7 to 0.8433.」——実データにおいて実際に重複行が存在すること
(IEEE-CISの実データ特性)を突き止め、それを悪用ではなく正当な統計的補正として
活用した。UID復元(layer1#1)そのものではないが、「同一実体を特徴ベクトルの一致から
再構成する」という構造的に近い発見であり、**列数を増やしたことで初めて意味を持つ
ようになった技術**(10列では偶然の一致が起きやすく、意味のある重複検出にならない)。
今後の taxonomy 拡張候補として記録する。

## 発見(4、プロンプト設計への示唆):adversarial validation の出現は reasoning effort
ではなく prompt_arm(P3)と完全に相関していた

Layer1#5(adversarial validation)を用いた4 runは **P3configの4run全て**であり、
P1configの4runには1件も出現しなかった。**「自身の最良解を攻撃せよ」という P3 の
自己批判指示が、adversarial validation という具体的な検証手法を誘発した**と解釈
できる——reasoning effort の高低とは無関係。これは v0.4.3-f 側では見えなかった、
全特徴量下で初めて明確になった知見である。

## 正本

- [Diagnostics](../v044_v044_suite_a01_diagnostics.json)
- [10列制約インシデント記録](v044_ten_column_constraint_incident.md)
- [c_lite_v044_policy.md](../c_lite_v044_policy.md)
