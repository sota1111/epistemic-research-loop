# データ形式非依存メタ技術taxonomy(層2)— Controller専有

**分類:** Controller専有・エージェント非開示。[c_lite_v043_policy.md](../c_lite_v043_policy.md)
§2(v0.4.3-b)で定義した2層構造の層2。個別コンペの
[technique taxonomy](.)(層1、列意味論・データ形式に依存する具体技術)を補完する、
**コンペを跨いで繰り返し観測された、データ形式に依存しない技術クラス**。discovery 後の
post-hoc スコアリングにのみ使う。プロンプト・契約・データ・エージェント可視のいかなる
ファイルにも複製しないこと。

**出典:** v0.4.2 で完了した IEEE-CIS(`v041-trackb-03`)・Santander(`v042-mc-b02`)の
discovery ログの事後分析([cross-competition synthesis](../verification/v042_cross_competition_synthesis.md))。
**layer2 のこの2クラスは、それが観測されたラウンド自体のスコアリングには遡及適用していない**
(taxonomy はスコアリング前に固定されるべきという原則に基づく——circular を避けるため)。
本ドキュメントは、それ以降に preregister される新規コンペの taxonomy に**当初から**組み込む
ためのものである。

## 層2 技術クラス

1. **Context プーリング/leave-one-context-out 汎化。** パック内の複数(通常3つ)の独立に
   抽出された context が、別々の regime ではなく単一の共有機構に支配されているという
   claim。エージェントは pack-level の観測単位ではなく、context を跨いで安定な
   risk mapping / 係数 / 変換を仮定し、leave-one-context-out で汎化を検証する。
   IEEE-CIS では promoted 27件中 17件(63%)、Santander では promoted 38件中 38件
   (100%)がこの claim を含んでいた——[v0.4.3-a 検証](../verification/v042_cross_competition_synthesis.md#追記v043-acontext-プーリング発見は-artifact-か実データの構造か)
   により、この claim は Matched Negative(構造破壊済み)データではほぼ確実に正しく
   falsified される(IEEE-CIS 100%・Santander 98%)ことを確認済み——**artifact ではなく、
   実データに構造が存在する場合にのみ通過する健全な発見パターン**と判定した。
2. **Occurrence/sparsity-profile 集約。** 個々の特徴の値そのものではなく、「どの特徴が
   非ゼロ/非欠損か」という occurrence パターン自体を予測力のある集約特徴として使う
   (hurdle 型 occurrence/log-magnitude 分解、active-channel breadth count、
   identity-free row-profile aggregate 等)。IEEE-CIS で複数 run・複数モデル・複数
   seed にわたり独立に再現(`agent-01-s42`・`agent-02-s42`・`agent-02-s93`、および
   v041-trackb-01 の `opus×P3` run)。実務的な fraud detection 技術(非欠損列数等)と
   構造的に近いが、匿名化された任意の疎な表形式データ一般に適用できる水準の記述。

## 使用方法(新規コンペへの適用)

新規コンペ(Rossmann 含む、[v0.4.3-c](../c_lite_v043_policy.md) 参照)の taxonomy 文書は、
preregister 時点から層1(コンペ固有)と層2(本ドキュメントへの参照)の両方を持つ形式で
作成すること。層2は固定リストとして扱い、新規コンペの discovery ログ照合でも同じ2クラスを
まず適用する——コンペ跨ぎで別の層2パターンが独立に複数回観測された場合のみ、次ラウンドの
taxonomy 更新候補として追加検討する(単一コンペでの初出だけでは層2に昇格させない)。

## 正本

- [クロスコンペ統合分析](../verification/v042_cross_competition_synthesis.md)
- [IEEE-CIS technique taxonomy(層1)](ieee_cis_technique_taxonomy.md)
- [Santander technique taxonomy(層1)](santander_technique_taxonomy.md)
- [Rossmann technique taxonomy(層1)](rossmann_technique_taxonomy.md)
