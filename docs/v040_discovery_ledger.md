# v0.4.0 累積発見台帳(gen1 + sol ablation + scaffold-ladder Stage1/2 + cycle-budget ablation, 102 run 時点)

未知構造発見という目的に対する評価基準として、「どの構造 family がこれまでに一度でも真に
発見されたか」を run・構成・study 横断で追跡する。単一 study 内の発見率だけでは、同じ
family を何度発見しても「新しい発見」にはならないことが見えない。数字はスクリプトで
diagnostics.json を集計し直したもの(手計算ではなく実測値)。

## family 別・累積発見回数(2026-08-29 時点、102 run:gen1 24 + sol ablation 24 +
scaffold-ladder Stage1 24 + Stage2 18 + cycle-budget ablation 12)

| family | 累積発見回数 | 主な発見元 |
| --- | ---: | --- |
| grammar_composed_b | 59 | 全 study で継続的に発見 |
| grammar_composed_a | 56 | 同上 |
| observation_routing_composition | 53 | 同上(v0.3.x 由来、既知構造相当) |
| persistent_clear (L1) | 6 | sol ablation×2 / scaffold-ladder Stage1×2 / Stage2×1 / cycle8×1 |
| persistent_compositional (L4) | 4 | gen1×2 / scaffold-ladder Stage1×1 / Stage2×1 |
| persistent_noisy_proxy (L2) | 2 | scaffold-ladder Stage1×1 / Stage2×1 |
| persistent_delayed_history (L3) | 3 | **Stage2×2 / cycle8×1**(gen1・sol ablation・Stage1 では 0) |

persistent ラダー全 4 段階が、複数の study にまたがって独立に発見されている。発見率は
いずれも低い(最頻の persistent_clear でも 102 run 中 6 件 ≈ 5.9%)。

## 読み取れること

1. **grammar-composed 系(未知構造生成器)と observation_routing は「解けた」。** 多数の
   構成が繰り返し到達しており、この家族に関しては「未知の構造の発見」というより「既知に
   近い定常的発見」になっている。今後の評価では、この 3 family での発見を主指標から
   薄めるか、diversity 指標(semantic_family_count 等)側で評価する方が情報量が高い。
2. **persistent ラダーは「壁」ではなく「低確率事象」。** L1〜L4 いずれも複数の異なる経路
   (sol の high/xhigh effort、opus/sol の P3 scaffold、opus×P1×cycle8、replicate 数の
   増量)で少なくとも一度は破られている。
3. **P3(自己批判)scaffold がモデルを問わず主要な発見経路になった。** Stage2 で opus×P3 は
   persistent_clear + persistent_delayed_history、sol×P3 は persistent_compositional +
   persistent_noisy_proxy を発見。**P2(仮説列挙強制)は persistent 系を一度も割っていない**
   (gen1・scaffold-ladder のどちらでも)。低 sol effort(low/medium)も同様に皆無。
4. **evidentiary capacity の 2 つのレバーは質的に異なる効果を持つ。** reasoning effort を
   上げると発見・多様性ともに増加する(sol ablation)。一方 **cycle 予算を増やすと発見は
   横ばい、多様性はむしろ低下する**(cycle-budget ablation:opus 3.75→2.67、sol 1.67→1.17)
   ——「広く探索する」のではなく「同じ仮説を深く詰める」方向に働く。両者を同じ
   「evidentiary capacity」という言葉でまとめるのは不正確だった。
5. **Stage 1(n=4)→ Stage 2(n=6)で opus×P3 の多様性ブーストが 8.75→4.33 に縮小した。**
   小 n のスクリーニング推定値は効果量を過大評価しうるという教訓——本台帳の「累積発見回数」も
   同じ注意が必要:1〜3 回の発見は「再現性が確認された」ことを意味しない。
6. **false promotion は codex 系(sol・terra)に完全に限定される。** 全 5 study・102 run を
   精査した結果、**claude 系(fable・opus・sonnet)は false promotion が一度もゼロから
   外れていない**(0/50+ replicate)。false promotion 26 件は全て sol か terra から発生し、
   うち 4 件が単一 suite instance に集中する「暴走」型(gen1 terra/v040-genA-g03=5、
   sol ablation high/v040-solE-b05=5、Stage1 sol×P3/v040-scaf-c04=7、
   cycle8 sol/v040-cyc8-e05=4)、残りは散発的。suite instance の性質ではなく、**codex 系
   モデルの calibration に固有の問題**である可能性が高い(v0.4.1 方針§4.1 の保留課題)。

## 7. codex 系 false promotion の機序調査(2026-08-29、read-only transcript/コード分析)

項目 6 で確定した「false promotion は codex 系(sol/terra)に完全に限定される」という事実の
**機序**を、4 件の「暴走」replicate(gen1 terra/g03=5 件、sol ablation high/b05=5 件、
Stage1 sol×P3/c04=7 件、cycle8 sol/e05=4 件)が実際に書いた `run_protocol.py` を直接読んで
調査した(新規 run は実行していない、既存 transcript・作業ディレクトリの read-only 分析)。

**確認できたこと:**

- **4 件全てが、null 分布を `N_NULL = 5`(5 回の permutation replicate)で推定していた。**
  promotion 判定は `position = (1 + #null <= observed) / (N_NULL + 1)` を計算し
  `position >= 0.95` を要求する設計だが、N_NULL=5 では position が取りうる値は
  {1/6, 2/6, ..., 6/6} の 6 通りしかなく、**`>=0.95` を満たすには position=1.0(5 個の
  null を全て上回る)以外に達成手段がない**。純粋に構造が存在しない場合でも、observed が
  5 個の null 中で最大になる確率は理論上 1/6 ≈ 16.7%(2/3 コンテキストで要求される
  validated 条件を含めるとさらに変動)——意図された ~5% 水準よりかなり緩い、解像度の粗い
  棄却検定になっている。
- 対照的に、**opus(claude 系)が自ら書いたプロトコルコードは一貫して null replicate 数が
  多い**(直接確認できた範囲で 200・200・300・400・500)。閾値も `np.quantile(draws, 0.95)`
  のような連続分布からの分位点で計算しており、5 replicate のような粗い離散化は見られない。
- ただし、**N_NULL=5 は codex 系の全 run に共通する固定値ではなく、run ごとにばらつく**
  (5・10・20・30 などを確認)。さらに、N_NULL=5 を使った codex run の中には false
  promotion が 0 件のものも多数ある(例:gen1 terra g01 の 2 replicate、sol ablation の
  複数 replicate)。自動 grep によるプロパティ横断の定量相関チェック(52 codex run 中 27 件で
  N_NULL を検出)では、N_NULL<=5 群(12 run, 平均 fspr 0.107)と N_NULL>5 群(15 run, 平均
  fspr 0.133)で明確な差は出なかった——**ただし grep ベースの検出はスクリプト構成が
  run ごとに大きく異なるため精度が低く、この定量比較自体の信頼性は高くない**(手動で
  精読した 4 件の「暴走」replicate は全て N_NULL=5 だったという事実の方が確度が高い)。

**現時点の解釈(確定ではない):** codex 系モデルは、run ごとに自分でプロトコルコード
(null replicate 数を含む)を一から書き直しており、**claude 系のように一貫して過剰な
null replicate 数(200+)を割り当てる習慣がない。** 「暴走」した 4 件は、たまたま
N_NULL=5 という粗い検定を選び、かつ observed 統計量がその粗い閾値を(真の構造の有無に
関わらず)超えてしまった run である可能性が高い。N_NULL=5 自体は false promotion の
**十分条件ではない**(多くの N_NULL=5 run は 0 件のまま)が、**必要条件に近い共通点**
ではある(4/4 の暴走 run が該当)。「codex 系モデルの確信度較正が本質的に甘い」という
より強い主張は、この調査だけでは立証できない——「自己記述する統計プロトコルの厳密さに
run 間でばらつきがあり、claude 系ほど一貫して保守的でない」という、より限定的な主張が
現時点で言えることの上限。

**Track B への含意:** sol×P3×xhigh を投入する以上、この脆弱性を個別 run で監視する
価値がある。プロンプト側で null replicate 数の最低限(例:N>=50)を明示的に要求する介入は
検討に値するが、v0.4.0 の「解法・構造を教えない」原則(証拠手続きの指定は可、答えの指定は
不可)との整合性を検討してから導入すべきであり、**未実施**(v0.4.1 の判断課題として保留)。

## 次の評価基準

- persistent 系は「発見したかどうか」の二値ではなく、**累積発見回数と母数(何 run 試したか)**
  を常に併記する(発見率が依然として低いことを見失わないため)。
- grammar-composed / observation_routing の発見は基準値扱いとし、false promotion が 0 で
  あることの確認程度に格下げする。
- 「evidentiary capacity」を単一概念として扱わず、reasoning effort(発見・多様性を押し上げる)
  と cycle 予算(深さに振れ多様性を下げる)を別レバーとして評価する。

本台帳は study が完了するたびに更新する。次段階(v0.4.1)ではこの台帳を初期状態として
引き継ぐ。
