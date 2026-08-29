# v0.4.2 best-of-population 指標の遡及適用 — IEEE-CIS Track B(v041-trackb-01)

**目的:** [c_lite_v042_policy.md](../c_lite_v042_policy.md) §1 で定義した best-of-population
近似度(構造面・性能面)を、既に完了済みの v041-trackb-01(12 run)に遡及適用する。新規
データ取得を必要とせず、修正後の評価枠組みが実データでどう機能するかを検証できる。

**前提:** [v041_track_b_qualification.md](v041_track_b_qualification.md) の通り、v041-trackb-01
全体は Matched Negative 構築の欠陥により P2 再現要件を満たさなかった。ただし個々の
run 単位で見ると、12 run中 3 run は FSPR 条件(Matched Negative 非昇格)を満たしており
(`agent-02-s42`・`agent-03-s93`含む)、この 2 run の候補パック昇格は Matched Negative の
欠陥に汚染されていない——[docs/v041_track_b_diagnostics.json](../v041_track_b_diagnostics.json)
の `fspr_clean: true` で確認済み。この 2 run の promoted パックのみを対象とする。

## population(この遡及分析の対象)

P2 を満たした 2 run・のべ 5 パック昇格:

| run | config | promoted packs |
| --- | --- | --- |
| agent-02-s42 | TB-opus-P3 | pack-c04, pack-c03 |
| agent-03-s93 | TB-sol-P3 | pack-c04, pack-c03, pack-c02 |

## 構造面:技術クラス照合

[ieee_cis_technique_taxonomy.md](../controller_reference/ieee_cis_technique_taxonomy.md) の
6 技術クラス(UID復元・時間因果集約・時間差特徴・カテゴリエンコーディング・adversarial
validation・GBMアンサンブル)に対し、2 run の claim テキストを照合した:

- **agent-02-s42(opus×P3):** 「重尾な利用量列を occurrence(非ゼロ判定)成分と
  log-magnitude 成分に分解する hurdle 型decomposition」——cross-fitted occurrence-pattern
  separation(Cohen's d、volume-preserving permutation で null 参照)。
- **agent-03-s93(sol×P3):** 「label-free な context 単位 rank/zero 正規化後に共有される
  semantic-coordinate risk mapping」——複数 context 間で安定した risk mapping の存在を
  quintile enrichment で検証。

**結果:一致数 0/6。** どちらの discovery も、taxonomy の 6 クラスのいずれとも一致しない。
これは「上位解法に近づけなかった」ことを直接意味するとは限らない——Track B は列名を
完全に匿名化・汎用ラベル化しており(`_visible_column_map` によるハッシュ化)、taxonomy の
多くのクラス(UID復元・カテゴリエンコーディング)は実列の意味論(card1・addr1・D-columns
等)に強く依存する。匿名化された数値列だけを見るエージェントが同じ技術クラスに到達する
経路は構造的に塞がれている可能性が高い。

**今後の方針への示唆(1):** taxonomy を「列の意味論に依存する具体技術」水準と「データ形式に
依存しないメタ技術(分布形状の分解・文脈間正規化による汎化・アンサンブル設計等)」水準に
分けて記録し直すべきかもしれない。現在の 2 discovery は後者に近い——「重尾分布の
occurrence/magnitude 分解」「文脈間で安定な risk mapping の正規化」は、匿名化された
表形式データ一般に適用できる技術クラスであり、Rossmann・Santander の taxonomy にも
同水準の項目を追加検討する価値がある(例:Santander taxonomy の #2「特徴独立性前提の
モデリング」は既にこの水準に近い)。

## 性能面:capacity-matched baseline との差

| run | pack | agent transfer AUC | baseline AUC | gain |
| --- | --- | ---: | ---: | ---: |
| agent-03-s93 | pack-c04 | 0.8094 | 0.6636 | **+0.1458** |
| agent-02-s42 | pack-c04 | 0.7685 | 0.6636 | +0.1049 |
| agent-03-s93 | pack-c02 | 0.7410 | 0.5311 | +0.2099 |
| agent-03-s93 | pack-c03 | 0.7360 | 0.6265 | +0.1095 |
| agent-02-s42 | pack-c03 | 0.7112 | 0.6265 | +0.0847 |

**population 最大 gain:** `agent-03-s93`(sol×P3)の pack-c02、**+0.2099 AUC**
(baseline 0.5311 → agent 0.7410)。

policy §1.2 の通り、この gain を「上位解法相当の性能との差の何割を埋めたか」という換算は
**行わない**——IEEE-CIS の公開 LB スコアは全 434 列・完全なラベル付き test セットに対する
評価であり、本 Suite の transfer 区間評価(10 匿名化列・1800 行/context の内部分割)とは
評価対象が異なるため、直接の換算は v0.4.1 方針§5.3 の教訓に反する。ここでは「baseline を
大きく上回る gain が、Matched Negative 汚染のない run で複数回・複数モデルにわたって
確認された」という事実のみを記録する。

## 結論と今後の方針への示唆(2)

1. **best-of-population の両方の主張(構造・性能)が、限定的ながら実データで確認できた。**
   性能面は明確な population 内の最良値が存在し(+0.21 AUC)、構造面は「上位解法の
   taxonomy とは異なるが、独立に有効な」新規技術クラスが 2 つ確認された——これは
   policy §0 claim 2(未知構造の発見)の実データでの再現でもある。
2. **taxonomy 照合が 0/6 だったことは、v0.4.2-c(taxonomy 構築)の設計を見直す契機になる。**
   匿名化データでの discovery を意味論依存の技術クラスと直接比較するのは構造的に無理が
   ある。今後の taxonomy はメタ技術水準の項目を増やすべき。
3. **v041-trackb-02(Matched Negative修正版)の完了後、同じ遡及分析を再実行し、修正前後で
   population の質(promoted pack数・gain分布)がどう変わったかを比較する。** これは
   Matched Negative修正の副次的検証にもなる。

## 正本

- [v041 Track B qualification](v041_track_b_qualification.md)
- [v041_track_b_diagnostics.json](../v041_track_b_diagnostics.json)
- [IEEE-CIS technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md)
- [c_lite_v042_policy.md](../c_lite_v042_policy.md)
