# v0.4.0 累積発見台帳(gen1 + sol ablation + scaffold-ladder screen/Stage 2, 90 run 時点)

未知構造発見という目的に対する評価基準として、「どの構造 family がこれまでに一度でも真に
発見されたか」を run・構成・study 横断で追跡する。単一 study 内の発見率だけでは、同じ
family を何度発見しても「新しい発見」にはならないことが見えない。数字はスクリプトで
diagnostics.json を集計し直したもの(手計算ではなく実測値)。

## family 別・累積発見回数(2026-08-29 時点、90 run:gen1 24 + sol ablation 24 +
scaffold-ladder Stage1 24 + Stage2 18)

| family | 累積発見回数 | 主な発見元 |
| --- | ---: | --- |
| grammar_composed_b | 51 | 全 study で継続的に発見 |
| grammar_composed_a | 47 | 同上 |
| observation_routing_composition | 47 | 同上(v0.3.x 由来、既知構造相当) |
| persistent_clear (L1) | 5 | sol ablation(high×2)/ Stage1(opus×P1, opus×P3)/ Stage2(opus×P3) |
| persistent_compositional (L4) | 4 | gen1(C2, C3)/ Stage1(opus×P1)/ Stage2(sol×P3) |
| persistent_noisy_proxy (L2) | 2 | Stage1(opus×P3)/ Stage2(sol×P3) |
| **persistent_delayed_history (L3)** | **2** | **Stage2 のみ(opus×P1, opus×P3)——初発見** |

**2026-08-29: persistent ラダー全 4 段階が、少なくとも一度は真に発見された。** 「一度も
発見がない family」は、この Suite generator の範囲では現時点で存在しない。ただし発見率は
いずれも低い(最頻の persistent_clear でも 90 run 中 5 件 ≈ 5.6%)。

## 読み取れること

1. **grammar-composed 系(未知構造生成器)と observation_routing は「解けた」。** 多数の
   構成が繰り返し到達しており、この家族に関しては「未知の構造の発見」というより「既知に
   近い定常的発見」になっている。今後の評価では、この 3 family での発見を主指標から
   薄めるか、diversity 指標(semantic_family_count 等)側で評価する方が情報量が高い。
2. **persistent ラダーは「壁」ではなく「低確率事象」だった。** L1〜L4 いずれも複数の異なる
   経路(sol の high/xhigh effort、opus/sol の P3 scaffold、replicate 数の増量)で少なくとも
   一度は破られている。単純な「ラダーの高さ」による難易度差ではなく、条件が揃えば確率的に
   発見される性質に近い。
3. **P3(自己批判)scaffold がモデルを問わず主要な発見経路になりつつある。** Stage2 で
   opus×P3 は persistent_clear + persistent_delayed_history の 2 family を同時発見、
   sol×P3 は persistent_compositional + persistent_noisy_proxy の 2 family を新規発見。
   **P2(仮説列挙強制)は persistent 系を一度も割っていない**(gen1・scaffold-ladder の
   どちらでも)。低 sol effort(low/medium)も同様に皆無。
4. **Stage 1(n=4)→ Stage 2(n=6)で opus×P3 の多様性ブーストが 8.75→4.33 に縮小した。**
   小 n のスクリーニング推定値は効果量を過大評価しうるという教訓——本台帳の「累積発見回数」も
   同じ注意が必要:1〜2 回の発見は「再現性が確認された」ことを意味しない。

## 次の評価基準

- persistent 系は「発見したかどうか」の二値ではなく、**累積発見回数と母数(何 run 試したか)**
  を常に併記する(発見率が依然として低いことを見失わないため)。
- grammar-composed / observation_routing の発見は基準値扱いとし、false promotion が 0 で
  あることの確認程度に格下げする。
- cycle-budget ablation(4→8、実行予定)は、persistent 系の発見「率」そのものを引き上げ
  られるかを見る——「壁を破る」から「低確率事象の頻度を上げる」への焦点移行。

本台帳は study が完了するたびに更新する。
