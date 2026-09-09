# 表形式コンペ横断メタ技術 taxonomy(層2・解法技術)— Controller専有

**改名(2026-09-06):** 旧題は「**データ形式非依存**メタ技術taxonomy」。
**その名前は証拠が支えていなかった。**根拠は IEEE-CIS と Santander の 2 件、
**どちらも表形式予測**である。1 つの問題クラスの中で 2 回観測したことは、
その問題クラスについての証拠であって、データ形式非依存の証拠ではない
([ERL を完成させるための引き継ぎ書](../v050_course_correction.md) §3 の 9)。
旧ファイル名 `meta_technique_taxonomy_layer2.md` は本ファイルに置き換わった。

**昇格条件も上げた。**旧規則は「コンペ跨ぎで独立に複数回」= **2 コンペ**だった。
新規則は次の 3 つを**すべて**満たすことを要求する。

| 条件 | 値 |
| --- | ---: |
| 直接観測が跨ぐ**問題クラス**数 | **2 以上** |
| 直接観測が跨ぐコンペ数 | 2 以上 |
| 直接観測が跨ぐエージェントモデル数(全観測がエージェント由来のとき) | 2 以上 |

**規則は文章ではなくコードで当たる。**登録簿は
[layer2_registry.json](layer2_registry.json)、判定は `src/epistemic_loop/taxonomy/layer2.py`、
表示は `erlctl taxonomy status`。

## 新規則を当てた結果 — **本ファイルの 2 クラスはどちらも候補へ降格**

| クラス | 旧 | 新 | 理由 |
| --- | --- | --- | --- |
| 1. Context プーリング | 昇格 | **候補** | 直接観測が 1 問題クラス(表形式予測)・1 モデル(opus) |
| 2. Occurrence/sparsity 集約 | 昇格 | **候補** | 直接観測が **1 コンペ(IEEE-CIS)**・1 問題クラス・1 モデル |
| 3. 加法性の限界(元から候補) | 候補 | 候補 | 1 問題クラス・1 モデル(sol) |

**2 は旧規則(2 コンペ)でも昇格条件を満たしていなかった。**
複数 run・複数 seed での再現を「独立に複数回」と読んだが、**コンペは 1 つである。**

**降格は失敗ではなく、条件を上げたことの費用である。**クラスの記述と観測は残る。
消したのは「これは出題非依存だ」という主張のほうだけである。

**問題クラスを跨いで昇格した層2 は別ファイルにある** ——
[装置クラス層2](apparatus_taxonomy_layer2.md)。

---

## 層2 技術クラス(観測の記述。昇格状態は上表を見ること)

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

## 候補クラス(未昇格、追加確認待ち)

3. **加法性/特徴独立性の限界("beyond additive marginals")。** 「特徴ごとの寄与を
   加法的に足し合わせるモデルでは不十分で、特徴間の joint な非線形相互作用こそが
   構造の本質である」という claim——layer2#1(プーリング。context を跨いだ機構の
   共有)や layer2#2(occurrence/sparsity。値の有無パターン)とは異なる、**単一
   context 内での特徴間関係の形**についての対抗仮説。v0.4.3-f の sol reasoning-effort
   多様性ラウンドで、事後の全数検索により**独立4件**が確認された:
   `v042-mc-c01/agent-01-s42`(IEEE-CIS、SD-medium-P1、7パック中4件promoted)・
   `v042-mc-c02/agent-01-s17`(Santander、SD-low-P1、8パック中2件promoted)・
   `v042-mc-d02/agent-02-s186`(Santander、SD-low-P1、8パック中0件promoted——claim
   自体は再現したが検証には失敗)・`v042-mc-e01/agent-01-s402`(IEEE-CIS、SD-high-P3、
   8パック中4件promoted)・`v042-mc-f01/agent-01-s512`(IEEE-CIS、SD-high-P1、
   4パック全てpromoted、うち3件は`validated_actionable_transferred`まで到達)。
   両コンペ・4種の effort/arm 構成(medium-P1・low-P1・high-P3・high-P1)で確認され、
   単一の effort/prompt arm には普遍的には紐づかない——ただし**コンペごとに条件が
   異なる**:IEEE-CIS では medium/high 双方の effort・P1/P3 両 arm で出現する一方、
   **Santander ではこのパターンが `SD-low-P1`(低effort)にのみ観測され、高effort
   構成(`SD-high-P1`・`SD-xhigh-P3`、いずれも n=4 で確認済み)では一貫して不在**
   (`SD-xhigh-P3` の11 promoted パック全てが、逆に「加法的な」機構を明示的に
   主張していた)。
   **未昇格の理由:** 5件全てが **sol(codex/gpt-5.6-sol)単独ラウンドでのみ**観測され、
   元の opus+sol 混合バッチ(`v041-trackb-03`・`v042-mc-b02`)には1件も出現しなかった
   ——「データ形式非依存の構造発見パターン」ではなく「sol 特有の仮説生成スタイル」
   である可能性を否定できない。opus での再現が確認されるまでは正式な層2クラスに
   昇格せず、候補のまま保持する。

## 使用方法(新規コンペへの適用)

**(旧規則の記述。上の新規則が優先する。)**
新規コンペ(Rossmann 含む、[v0.4.3-c](../c_lite_v043_policy.md) 参照)の taxonomy 文書は、
preregister 時点から層1(コンペ固有)と層2(本ドキュメントへの参照)の両方を持つ形式で
作成すること。層2は固定リストとして扱い、新規コンペの discovery ログ照合でも同じ2クラスを
まず適用する——コンペ跨ぎで別の層2パターンが独立に複数回観測された場合のみ、次ラウンドの
taxonomy 更新候補として追加検討する(単一コンペでの初出だけでは層2に昇格させない)。
**——この段落の「コンペ跨ぎ」は新規則で「問題クラス跨ぎ」に置き換わった。**

## 正本

- [層2 登録簿(判定の入力)](layer2_registry.json) / `src/epistemic_loop/taxonomy/layer2.py`
- [装置クラス層2](apparatus_taxonomy_layer2.md)

- [クロスコンペ統合分析](../verification/v042_cross_competition_synthesis.md)
- [IEEE-CIS technique taxonomy(層1)](ieee_cis_technique_taxonomy.md)
- [Santander technique taxonomy(層1)](santander_technique_taxonomy.md)
- [Rossmann technique taxonomy(層1)](rossmann_technique_taxonomy.md)
