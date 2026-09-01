# v0.4.2 クロスコンペ統合分析 — IEEE-CIS(`v041-trackb-03`)× Santander(`v042-mc-b02`)

**目的:** [c_lite_v042_policy.md](../c_lite_v042_policy.md) §0 の 2 つの claim(best-of-
population 近傍到達・未知構造発見)を、修正済み permutation のもとで完了した 2 コンペの
**クリーンな全データ**で統合評価する。IEEE-CIS 側は
[v042_best_of_population_ieee_cis_retrospective.md](v042_best_of_population_ieee_cis_retrospective.md)
(v041-trackb-01 の汚染された 2 run のみが対象)を置き換える、より完全な分析。

## サマリ

| 指標 | IEEE-CIS(v041-trackb-03) | Santander(v042-mc-b02) |
| --- | --- | --- |
| P2 再現要件達成構成 | 2/3(opus×P3・sol×P3) | **3/3(全構成)** |
| Matched Negative 昇格 | 0/48 | 1/48 |
| Negative AUC 中央値 | 0.522 | 0.503 |
| Promoted 候補パック数 | 27/48(56%) | 37/48(77%) |
| Population 最大 gain(vs baseline AUC) | **+0.1878** | +0.0904 |
| opus×P1(合成P1構成)の成否 | 1/4(非達成) | **4/4(完全達成)** |
| taxonomy との構造一致 | 0/6(下記参照) | 部分一致(技術クラス#2) |

## Claim 1(best-of-population 近傍到達)への回答

**両コンペで performance 面の claim 1 は成立する**——population 内に capacity-matched
baseline を明確に上回る候補が複数・独立に存在した(IEEE-CIS 最大 +0.19 AUC、Santander
最大 +0.09 AUC)。gain の絶対値は IEEE-CIS の方が大きいが、これは元々の signal-to-noise
比の違い(§7 のコンペ選定表通り Santander は「強い stress test」)を反映しており、
「diverse population の中にベストな1つが存在する」という存在命題自体はどちらでも真である。

**構造面(taxonomy 一致)は非対称。** IEEE-CIS は
[technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md) の 6 クラスと
0/6 一致(匿名化により UID 復元・カテゴリエンコーディング等の列意味論依存クラスに到達
しにくいため、と分析済み)。Santander は
[technique taxonomy](../controller_reference/santander_technique_taxonomy.md) の技術クラス
#2(特徴独立性前提のモデリング)と部分一致した——「単一の共有線形方向が文脈を越えて
汎化する」という発見は、Santander の実際の上位解法が持つ「200特徴がほぼ独立、per-feature
線形寄与の合成」という設計思想と構造的に近い。

**両コンペを跨いで独立に繰り返し現れた、taxonomy 未収載のメタ技術パターン(新規発見):**

1. **「Context プーリング/leave-one-context-out 汎化」——最も顕著な共通パターン。**
   IEEE-CIS では 12 run 中複数(`agent-02-s17`「3つのcontextはexchangeableな shard」、
   `agent-03-s17`「context 間の invariant phenotype」、`agent-03-s93`「context-invariant
   risk surface」)、Santander では検証した全 3 run が独立に「3つのcontextは別々の
   regimeではなく単一の共有機構に支配されている」という同型の claim へ到達した。
   これは**コンペ固有の技術クラスではなく、Track B/v0.4.2 のプロトコル自体
   (research/confirmation/transferの3区間×3独立contextという設計)が誘導する、
   データ形式非依存のメタ技術**——「pack-level の観測単位が正しいか、context-level か」
   という検証幾何そのものを疑うという未知構造発見の一形態。
2. **「Activation/sparsity-profile 集約」(IEEE-CIS のみ、複数run で独立再現)。**
   `agent-01-s42`(scale-free panel-burden)・`agent-02-s42`(active-channel breadth
   count)・`agent-02-s93`(identity-free row-profile aggregate)が独立に、「どの特徴が
   非ゼロか」という occurrence パターン自体が予測力を持つという構造に到達した——v1の
   retrospective で見た「hurdle-type occurrence/log-magnitude decomposition」
   (opus×P3、v041-trackb-01)と同系統の発見が、修正済み Suite でも複数モデル・複数
   seed で独立に再現している。これは taxonomy には無いが、実際の欠損値パターン・
   カウント特徴を使う実務的な fraud detection 技術(例:非欠損 D-column 数)と構造的に
   近い——**taxonomy 側が「技術クラスの記述粒度が細かすぎる」ことを示唆する**(個別列名
   ではなく「occurrence/sparsity-pattern の集約」という水準で記述すべきだった)。

これらは**このラウンドの構造スコアには算入しない**(taxonomy はスコアリング前に固定された
参照物であるべきで、事後に見つかったパターンを遡及して taxonomy に追加するのは
circular になる)。次ラウンドの taxonomy 設計への入力として記録するに留める。

## 解法の多様性(v0.4.2 §2 のレバーが実際にもたらした多様性の実測)

promoted パックの `translation_kind`(採用された解法の要約記述)をユニーク化して数えると:

- **IEEE-CIS:promoted 27 パック中、9 通りの異なる `translation_kind`**——
  activation/sparsity 系(active-channel breadth count 等)、pooled context-invariant
  model 系(CatBoost・HistGradientBoosting をそのまま pooled fit)、burden/phenotype 系
  (signed-log・robust-scale 特徴)、threshold-state ensemble 系など、**アプローチの
  「種類」自体が複数存在する**——単一の解法が繰り返し当たっているのではない。
- **Santander:promoted 37 パック中、12 通りの異なる `translation_kind`**——ほぼ全てが
  「pooled/shared linear score」という同じ大枠のバリエーション(ridge・L2 logistic・
  z-scored・ECDF正規化・marginal-rank 等、正規化/推定方法の違い)——IEEE-CIS より
  収束度が高い。これは Santander の真の構造(特徴のほぼ独立性、線形分離可能性)が
  そもそも単純であることの反映と考えられる。

**この非対称性自体が claim 1 の重要な観測結果:** 「diverse な population の中にベストな
1つが存在する」という best-of-population の存在命題は、**構造が複雑なコンペ(IEEE-CIS)
では複数の質的に異なるアプローチが population に共存し、構造が単純なコンペ(Santander)
では同じアプローチの精緻化バリエーションが多数を占める**——多様性戦略(§2 のレバー:
reasoning effort・P3 自己批判・独立 run 数)の価値は、コンペの構造的複雑さに応じて
異なる形で発揮されるとわかった。

## Claim 2(未知構造の発見)への回答

**両コンペで成立。** 上記のメタ技術パターン(context プーリング、activation/sparsity 集約)
は、Controller が(technique taxonomy 構築時点で)事前に想定していなかった構造であり、
blind discovery の枠組みが機能した証拠である。

## opus×P1 のコンペ依存性——新しい知見

合成 Track A で P1 達成基準を満たした唯一の構成(opus×P1、cycle=4)が、実データでは
**IEEE-CIS で 1/4、Santander で 4/4** と正反対の成否を示した。P3(自己批判 scaffold)は
両コンペで安定して機能した(IEEE-CIS 3/4、Santander 4/4)。**単一の合成側最良構成を
複数の実コンペに無条件で持ち込むのはリスクが高く、P3 のような自己批判機構を伴う構成の方が
コンペを跨いだ頑健性が高い**——今後の複数コンペ展開(Rossmann 含む)では、P1 単独ではなく
P3 系構成を優先すべきという実践的な示唆。

## 今後の方針への含意

1. **v0.4.2 の 2 claim は 2 コンペで独立に実証された。** 3 コンペ目(Rossmann、回帰対応後)
   または Jigsaw の追加は、「2 コンペでの実証」を「N コンペでの一般則」に格上げするための
   次のステップとして位置づけられる。
2. **技術クラス taxonomy は、コンペ固有の具体的技術(列意味論依存)とデータ形式非依存の
   メタ技術(context プーリング、occurrence/sparsity 集約等)の 2 層で設計し直す価値が
   ある。** 現行 taxonomy は前者に偏っており、後者を捉えられていない。
3. **実行構成の選定は「合成側の最良構成」ではなく「複数コンペでの頑健性」で判断すべき。**
   P3 系(自己批判)構成を今後の多コンペ展開でも優先する。

## 正本

- [IEEE-CIS qualification](v041_track_b_qualification.md) / [Diagnostics](../v041_trackb_03_diagnostics.json)
- [Santander qualification](v042_santander_qualification.md) / [Diagnostics](../v042_mc_b02_diagnostics.json)
- [IEEE-CIS technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md)
- [Santander technique taxonomy](../controller_reference/santander_technique_taxonomy.md)
- [初期の限定分析(superseded)](v042_best_of_population_ieee_cis_retrospective.md)
