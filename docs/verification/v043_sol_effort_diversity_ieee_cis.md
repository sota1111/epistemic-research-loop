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

21件の promoted パック全てを layer1/layer2 taxonomy に照合した結果:

| config_id | promoted | Layer1 | Layer2#1(プーリング) | Layer2#2(occurrence/sparsity) | 未分類 |
| --- | ---: | ---: | ---: | ---: | ---: |
| SD-medium-P1 | 4 | 0 | 4 | 0 | 0 |
| SD-high-P1 | 4 | 0 | 4 | 0 | 0 |
| SD-xhigh-P1 | 4 | 0 | 4 | 0 | 0 |
| SD-medium-P3 | 3 | 0 | 3 | 0 | 0 |
| SD-high-P3 | 3 | 0 | **0** | **3** | 0 |
| SD-xhigh-P3 | 3 | 0 | 3 | 0 | 0 |
| **合計** | **21** | **0** | **18(86%)** | **3(14%)** | **0** |

**発見(3):layer1(コンペ固有・列意味論依存)に一致した promoted パックは 0 件。**
匿名化により列意味論依存の技術クラス(UID復元・カテゴリエンコーディング等)への到達経路が
構造的に塞がれているという既存の解釈([best-of-population遡及分析](v042_best_of_population_ieee_cis_retrospective.md))が、sol・reasoning effort を変えても揺るがないことを追加確認した。

**発見(4):reasoning effort は「発見するか否か」を左右するが、「何を発見するか」は
ほぼ左右しない——ただし1つの例外(`SD-high-P3`)がある。** promoted に到達した6構成中
5構成(medium-P1・high-P1・xhigh-P1・medium-P3・xhigh-P3)は全て layer2#1(context
プーリング)に収束した。唯一 `SD-high-P3` の3パック全てが独立に layer2#2
(occurrence/sparsity 集約、代表的claim:「行はスムーズな独立測定値ではなく
zero-state/heavy-tail の activity bundle として扱うべきで、これは観測単位・特徴生成・
検証層別化・誤差分解の全てを変える」)に到達し、プーリングという「アトラクタ」から
唯一脱出した run だった。この脱出は effort に対して単調ではない(xhigh-P3 は再び
プーリングに戻った)——「high effort × P3」という特定の組み合わせでのみ観測された
一回性の逸脱であり、effort を上げれば必ず多様性が増す、とは言えない。

**v0.4.3-f の3つの価値基準への回答(IEEE-CIS 側、暫定):**

1. **解法多様性:** 21 promoted 中、技術クラスの種類は 2 種(プーリング・occurrence
   集約)に限られる——元の 12-run 混合構成バッチ(opus 含む、多様性指数6)より明確に
   低い。sol・reasoning-effort のみを振っても、opus を含めた場合ほどの多様性は
   再現されなかった。
2. **上位解法相当の存在:** 0件(layer1 一致なし)——元のバッチと同じ結果。
3. **未知構造探索エージェント:** `SD-high-P3` が該当——プーリング以外の構造
   (occurrence/sparsity)に到達した唯一の run。効果の単調性を示さない一回性の
   発見であり、reasoning effort を安易に「上げれば良い」という単純な結論を退ける
   材料になる。

## 追記:Round 2(確認ラウンド、`v042-mc-d01`)——発見4は再現し、発見2の一部は再現しなかった

Round 1(screening、各セル n=1)が示した「SD-medium-P3 が最良(3/3 beats_baseline)」
「SD-high-P3 がプーリングから脱出した唯一の run」という2つの観測について、それぞれ新規
seed(155・186・217)を3件追加し、n=4(本プロジェクトの標準的な再現性基準)で確認した。

| config_id | round1(seed93/42) | round2(新規3 seed) | 合計 n=4 での P2 達成数 |
| --- | --- | --- | ---: |
| SD-medium-P3 | ✓(3/3 beats_baseline) | **✗ 0/3(FSPR汚染1件含む)** | **1/4(未達)** |
| SD-high-P3 | ✓(1/3 beats_baseline) | **✓ 3/3(FSPR汚染ゼロ)** | **4/4(達成)** |

**発見(9、最重要):round 1 単体では「medium effort が最良」に見えたが、これは再現しなかった
——n=1 の screening 結果を過信してはならないという直接的な教訓。** `SD-medium-P3` は
round 2 の新規3 seed で 0/3 が P2 を満たさず、うち1件(`agent-01-s186`)では **Matched
Negative パック(`pack-n04`)が誤って promoted される FSPR 汚染**が発生した——round 1 の
「3/3 全勝」という結果は統計的なブレ(運の良い draw)だった可能性が高い。

**発見(10):`SD-high-P3` は 4 seed 全てで P2 を達成し(4/4)、FSPR 汚染はゼロ——sol×
reasoning_effort=high×P3 は、この 8 セル探索の中で最も頑健な構成だったと確定した。**
round 1 だけを見ると「medium が良く見えて high は今ひとつ(1/3)」という逆の印象を
与えていたが、round 2 で完全に逆転した。**単一 seed のスクリーニング結果から実行構成の
優劣を判断することの危険性を、この対比が定量的に示している。**

taxonomy 再現性(発見4の脱出パターンが再現するか)は別途フォローアップ分析中——
[Santander 側](v043_sol_effort_diversity_santander.md)の round 2 と合わせて追記する。

## 正本

- [Diagnostics(round1)](../v042_mc_c01_diagnostics.json) / [Diagnostics(round2)](../v042_mc_d01_diagnostics.json)
- [クロスコンペ統合分析](v042_cross_competition_synthesis.md)
- [v0.4.3 方針§10](../c_lite_v043_policy.md)
