# v0.4.0 累積発見台帳(gen1 + sol ablation + scaffold-ladder screen, 88 run 時点)

未知構造発見という目的に対する評価基準として、「どの構造 family がこれまでに一度でも真に
発見されたか」を run・構成・study 横断で追跡する。単一 study 内の発見率だけでは、同じ
family を何度発見しても「新しい発見」にはならないことが見えない。

## family 別・累積発見回数(2026-08-29 時点、88 run)

| family | 累積発見回数 | 発見した構成(要約) |
| --- | ---: | --- |
| grammar_composed_a | 32 | ほぼ全構成が到達可能(未知構造だが「解けた」) |
| grammar_composed_b | 34 | 同上 |
| observation_routing_composition | 32 | 同上(v0.3.x 由来、既知構造相当) |
| persistent_compositional (L4) | 3 | gen1: C2, C3 / scaffold-ladder: opus×P1 |
| **persistent_clear (L1)** | **4** | sol ablation: high, xhigh / scaffold-ladder: opus×P1, opus×P3 |
| **persistent_noisy_proxy (L2)** | **1** | scaffold-ladder: opus×P3 のみ |
| **persistent_delayed_history (L3)** | **0** | **一度も発見なし** |

## 読み取れること

1. **grammar-composed 系(未知構造生成器)と observation_routing は「解けた」。** 多数の
   構成が繰り返し到達しており、この家族に関しては「未知の構造の発見」というより「既知に
   近い定常的発見」になっている。今後の評価では、この 3 family での発見を主指標から
   薄めるか、diversity 指標(semantic_family_count 等)側で評価する方が情報量が高い。
2. **persistent ラダーは L1(clear)から順に難易度が上がるわけではない。** L2(noisy_proxy)が
   L1(clear)より発見回数が少なく、**L3(delayed_history)に至っては皆無**——単純な
   「ラダーの高さ」ではなく、family ごとに固有の障壁がある。delayed_history 特有の統計量
   (window 内の履歴平均)が、他の family と異なる形で証拠を積みにくくしている可能性がある。
3. **これまで発見に成功した経路は限られている:** sol の high/xhigh effort、opus の
   P1/P3 scaffold。**P2(仮説列挙強制)は persistent 系を一度も割っていない**(gen1・
   scaffold-ladder のどちらでも)。低 sol effort(low/medium)も同様に皆無。

## Stage 2 の評価基準への反映

- 主指標(発見イベント数)に加え、**「未発見 family(特に persistent_delayed_history)を
  割ったか」を個別に追跡する二値指標**を新設する。
- grammar-composed / observation_routing の発見は「解けた」ものとして基準値扱いとし、
  false promotion が 0 であることの確認程度に格下げする。
- persistent_delayed_history が Stage 2(opus×P1・opus×P3・sol×P3×xhigh、各 6 replicate)
  でも 0 のままなら、cycle 予算(4→8)の ablation を最優先候補に格上げする。

本台帳は study が完了するたびに更新する。
