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
6. **単発の suite instance が false promotion を集中的に生む現象が繰り返し観測されている**
   (gen1 terra/g03、sol ablation high/b05、Stage1 sol×P3、cycle8 sol×cycle8/e05)。特定モデル・
   scaffold・effort に依存せず、ある種の suite instance が「過剰確信を誘発しやすい」性質を
   持つ可能性があり、今後の調査対象になりうる。

## 次の評価基準

- persistent 系は「発見したかどうか」の二値ではなく、**累積発見回数と母数(何 run 試したか)**
  を常に併記する(発見率が依然として低いことを見失わないため)。
- grammar-composed / observation_routing の発見は基準値扱いとし、false promotion が 0 で
  あることの確認程度に格下げする。
- 「evidentiary capacity」を単一概念として扱わず、reasoning effort(発見・多様性を押し上げる)
  と cycle 予算(深さに振れ多様性を下げる)を別レバーとして評価する。

本台帳は study が完了するたびに更新する。次段階(v0.4.1)ではこの台帳を初期状態として
引き継ぐ。
