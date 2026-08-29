# Santander v1(`v042-mc-b01`)——参考情報のみ、正式判定は v2 で行う

**分類:** 参考記録。**正式な P2 判定は `v042-mc-b02`(修正版 permutation)で行う。**

## 経緯

`v042-mc-b01` は [decile-stratified permutation の設計欠陥](v041_track_b_qualification.md)
が特定される前に構築・実行された(Santander の Kaggle 規約同意が下りた直後、IEEE-CIS 側の
根本原因調査と並行して着手)。12 run 完了・盲検監査クリーン・Lock 済みだが、**Matched
Negative の FSPR 判定は同じ欠陥の影響を受けており信頼できない。** 修正版 `v042-mc-b02` を
別途 construct・実行中——そちらを正式結果とする。

## 参考情報として記録する点

- **P2 再現要件は 3 構成とも 0/4**(IEEE-CIS 側と同型の不成立パターン)。
- **Matched Negative の agent 申告 transfer AUC は 0.486〜0.582(中央値 0.522)** —
  IEEE-CIS(`v041-trackb-02`:0.48〜0.73、中央値 0.602)より明確に chance に近い。
  これは根本原因仮説(decile-stratified permutation の漏洩量は baseline が捉える真の
  信号の強さに比例する)と整合する——Santander の confirmation/transfer gain
  (0.003〜0.07)は IEEE-CIS(0.10〜0.23)よりずっと小さく、baseline risk 自体が弱いため
  decile 間の陽性率相関も弱く、漏洩幅が小さい。**設計欠陥そのものは同じだが、severity は
  データセット依存**——Santander が「低〜中計算量の強い stress test」というユーザーの
  当初の評価([v0.4.2 方針§7](../c_lite_v042_policy.md))と方向性が一致する。
- 候補パックの昇格は 48 件中 28 件(58%)——一部(pack-c01・pack-c03)は
  `beats_capacity_matched_baseline=False` のまま `validated_non_actionable` 等で昇格して
  おり、baseline を明確に上回れていない構造も一定数含まれる。これも Santander の信号の
  弱さと整合する。

## 正本

- [Diagnostics](../v042_mc_b01_diagnostics.json)
- 正式結果:[v042-mc-b02 finalize 待ち](v041_track_b_qualification.md)
