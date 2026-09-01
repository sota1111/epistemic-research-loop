# v0.4.2 — Santander Customer Transaction Prediction blind bridge(`v042-mc-b02`)

## 結論

**修正済み permutation(`_destroy_target_structure`)のもとで、3構成全てが P2 再現要件を
達成した——IEEE-CIS(2/3構成)よりもさらに強く、クリーンな結果。** 12 run 中 11 run が
P2 を満たし(MC-opus-P1:4/4、MC-opus-P3:4/4、MC-sol-P3:3/4)、Matched Negative の
agent 申告 transfer AUC は 48 パック中 47 パックが chance 付近(中央値 0.503、平均
0.507)、昇格は 1 件のみ(該当 run のみ P2 不成立)。

これは v0.4.2 の 2 つの claim(§0)の**両方**が、**2 つ目のコンペで独立に再現された**ことを
意味する——単一コンペ(IEEE-CIS)の結果が偶然や suite 固有の統計的アーティファクトでは
ないことの直接証拠。

## 経緯

`v042-mc-b01`(旧 decile-stratified permutation)を Santander の Kaggle 規約同意直後に
先行実行したが、[IEEE-CIS 側で特定された同じ設計欠陥](v041_track_b_qualification.md)の
影響を受けるため参考記録に留めた([記録](v042_santander_v1_informal_note.md))。修正版
`v042-mc-b02` を construct・実行・開封した結果が本ドキュメントの対象。

## 実行記録

- 1 Suite(`v042-mc-b02`、iid_random split——Santander の行に意味のある時間順序はない)、
  3構成×4 replicate=12 run。
- 12/12 run 正常完了(バッチ失敗0件)。全run Lock通過。
- 盲検監査:view 12・transcript 21、findings 0。

## 構成別結果

| 構成 | P2満足run | 再現(≥2/4) |
| --- | ---: | --- |
| MC-opus-P1 | 4/4 | **成立** |
| MC-opus-P3 | 4/4 | **成立** |
| MC-sol-P3 | 3/4 | **成立** |

唯一 P2 不成立だった `agent-03-s17`(MC-sol-P3)は、48 パック中で Matched Negative が
昇格した唯一のケース(`pack-n02`、`validated_non_actionable`)と一致する——FSPR 条件の
不成立がその run だけの P2 判定を落としている。

## 構造面:一貫した「文脈間で共有される線形方向」の発見

12 run 中の promoted パックの claim テキストを確認すると、**構成・seed を問わず驚くほど
一貫した discovery パターン**が見られた:「3つの独立した context は別々の regime では
なく、単一の共有された線形機構に支配されている——観測単位は context ではなく pack
population であり、context を跨いで正しく汎化する検証幾何は leave-one-context-out で
ある」という趣旨の claim が、opus×P1・opus×P3・sol×P3 のいずれからも独立に得られた。

これは [Santander technique taxonomy](../controller_reference/santander_technique_taxonomy.md)
の**技術クラス#2(特徴間独立性を前提としたモデリング)と部分的に一致する**——匿名化された
数値列だけからでも、「単一の共有線形方向が文脈を越えて汎化する」という構造(200 特徴の
ほぼ独立性から来る、per-feature線形寄与の合成という実際の上位解法の設計思想)に
到達している。IEEE-CIS 側の遡及分析([結果](v042_best_of_population_ieee_cis_retrospective.md))
では taxonomy 6 クラスと 0/6 一致だったのに対し、**Santander では taxonomy との部分一致が
初めて観測された**——匿名化データでも、コンペの構造タイプによっては上位解法の技術クラスに
到達可能であることを示す最初の直接証拠。

一部のパック(`agent-01-s17` 系列)は、内部の `sequence_coordinate` 由来特徴(iid split
のため行位置ベースの非情報特徴)を正しく非共変量として特定・除外しており、decoy特徴に
惑わされない判断ができていた。

## 性能面:capacity-matched baseline との差

promoted 候補パック 48 件中 37 件(77%)。population 最大 gain は **+0.0904 AUC**
(`pack-c02`、agent AUC 0.639 vs baseline 0.549、sol×P3 で達成、opus×P1/P3 でもほぼ
同水準の gain が独立に再現)。IEEE-CIS の population 最大 gain(+0.21)より小さいが、
これは Santander の元々の signal-to-noise が弱いこと(preflight 時点の confirmation/
transfer gain も 0.003〜0.10 と IEEE-CIS の 1/2〜1/3)と整合する——「低〜中計算量の
強い stress test」というユーザーの当初評価([v0.4.2 方針§7](../c_lite_v042_policy.md))
どおりの性質を示した。

## opus×P1 の挙動:コンペ依存の非対称性

**IEEE-CIS では opus×P1(合成側 P1 達成構成)は 1/4 のみで P2 不成立だったが、Santander
では 4/4 で完全成立した。** 同じ実行構成が、コンペの構造タイプによって全く異なる成功率を
示した——これは v0.4.2 claim 1(diverse population 中にベスト解が存在する)の検証において
「diversity のレバー」がコンペ依存であることを示す新しい知見であり、今後の方針(複数
コンペでの検証を続ける根拠、単一コンペでの構成選択を過度に一般化しない)に直結する。

## 正本

- [事前登録(修正版、v042-mc-b02が対象)](../v042_trackb_matched_negative_fix_preregistration.json)
- [Diagnostics(v042-mc-b01、参考記録)](../v042_mc_b01_diagnostics.json)
- [Diagnostics(v042-mc-b02、正式結果)](../v042_mc_b02_diagnostics.json)
- [Santander technique taxonomy](../controller_reference/santander_technique_taxonomy.md)
- [IEEE-CIS Track B qualification(同一 permutation 修正の起点)](v041_track_b_qualification.md)
- Suite/Lock/Submission: `.runs/v042/`(gitignore対象、ローカル実行物)
