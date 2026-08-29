# v0.4.1 Track B — IEEE-CIS Blind Bridge, First Suite

## 結論

12 run(opus×P1・opus×P3・sol×P3×xhigh、各4 replicate)全て契約エラーなくLock通過、盲検監査もview・transcriptとも0件でクリーンだった。しかし **P2判定では、どの構成も再現要件(独立2 run以上でP2の4条件を満たす)を満たさなかった**(opus×P1: 0/4、opus×P3: 1/4、sol×P3: 1/4)。

不合格の主因は「候補構造が発見できなかった」ことではなく、**Matched Negativeパック(Controllerが意図的に構造を破壊したはずの対照)が、12 run中9 runで最低1件昇格した**ことによるFSPR条件の不成立だった。合成側Track Aでclaude系が0/50+ replicateで一度もfalse promotionを起こさなかったのと対照的に、Track Bではopus(claude系)も含めて頻繁にMatched Negativeを昇格している。**この結果は「opus×P1が実データへ転移しなかった」という単純な結論ではなく、Track B自身のMatched Negative構築方法に統計的な欠陥がある疑いが強いという、suite設計側の問題を強く示唆している。** 詳細は「重要な発見」節を参照。

## 実行記録

- 1 Suite(`v041-trackb-01`)、3構成×4 replicate=12 run。全run `danger-full-access`/`xhigh`(sol)/cycle=4で実行。
- 12/12 run正常完了(バッチ失敗0件)。全run Lock通過(`validate_v040_submission`のcontract error 0件、null_summary/implication_provenanceとも整合)。
- 盲検監査:view 12・transcript 23、findings 0(生列名・isFraud・TransactionID/DT・データセット識別語、いずれも検出なし)。

## 構成別結果

| 構成 | P2満足run | 再現(≥2/4) |
| --- | ---: | --- |
| TB-opus-P1 | 0/4 | 不成立 |
| TB-opus-P3 | 1/4 | 不成立 |
| TB-sol-P3 | 1/4 | 不成立 |

## 重要な発見:Matched Negativeの系統的な昇格

12 run中9 runで、4つのMatched Negativeパック(`pack-n01`〜`n04`)のうち最低1つが昇格された(`pack-n01`×3、`pack-n02`×3、`pack-n03`×2、`pack-n04`×3——延べ11件、特定の1パックへの集中ではなく4パック全てで発生)。エージェントが提出したtransfer AUCを個別に確認すると、2つの異なるパターンが見える:

- **`pack-n01`(3件)は transfer AUC が一貫して chance 付近(0.47〜0.57、平均0.51〜0.53)** なのに `validated_actionable_transferred` へ昇格されている。これは統計的サポートがほぼ無いにもかかわらず昇格しており、**エージェント側の判定閾値の甘さ**(v0.4.0 discovery ledger§7で確認したcodex系のnull検定の粗さと同型の問題)の疑いが強い。claude系(opus)でも起きている点が合成側と異なる。
- **`pack-n02`/`n03`/`n04`(残り8件)は transfer AUC が 0.55〜0.71(平均0.55〜0.65)** と、chanceを明確に上回る水準で複数run・複数モデル(opus/sol双方)にわたって再現している。単一runの偶然ではなく、**Controller側のMatched Negative構築方法(decile-stratified permutation、baselineが線形ロジスティック回帰)が、非線形な残差構造を破壊しきれていない**疑いが強い——構築時のdecile数(10分割)や baseline モデルの表現力が粗すぎた可能性がある。

**この2つの原因は切り分けて記録する必要がある。** 前者はエージェント側の較正問題(v0.4.0 discovery ledger§7の延長線上の論点)、後者はController側のsuite設計の欠陥であり、後者は次のTrack B再挑戦の前に修正すべき技術的負債である。

## P2criterion 1(capacity-matched baseline超え)の限界

候補パックの多くが `beats_capacity_matched_baseline=True` だったが、これは「未知構造を発見した」ことの十分な証拠ではない可能性がある——ControllerのbaselineがC=0.5の単純なロジスティック回帰である一方、エージェントはP3 scaffold(複数候補比較+自己批判)や非線形モデルを使うため、**単に「より表現力の高いモデルを使った」だけでbaselineを超えられる可能性がある。** この基準を「真に未知の連結構造を見つけた」ことの証拠として使うには、baseline自体をエージェントが典型的に使うモデルクラスに近づける(capacity-matchingをより厳密にする)か、構造破壊プローブ(Matched Negative側)の精度を上げて識別力を負担させる設計が必要——現状は後者(Matched Negative)の精度が不十分だったことが今回の主要な限界である。

## 判定(初回時点)

- **P2再現要件は3構成とも不成立。** ただしこれは v0.4.0方針の「停止規則1」(合成の構成がTrack Bへ転移しなかった)を単純に発動させる根拠にはならない——上記の通り、不成立の主因はTrack B自身のMatched Negative設計の統計的な甘さである可能性が高く、suiteの欠陥を確認せずに「転移しなかった」と結論するのは時期尚早。
- **次に必要な作業:** Matched Negativeの構築方法を強化した上で(baseline modelをより表現力の高いもの——例えばHistGradientBoosting等——に変更する、decile数を増やす、あるいは全く別の構造破壊手法を検討する)、新しいSuiteで再試行する。これは実データを再度扱う判断であり、**ユーザー確認を得てから実行する。**

## 再検証 v1(v041-trackb-02、baseline model 強化のみ)——2026-08-29

ユーザー承認を得て baseline を `HistGradientBoostingClassifier` に変更した新 Suite
(`v041-trackb-02`、decile-stratified permutation 自体はそのまま維持)で 12 run 再実行。

**結果:P2 再現要件は 3 構成とも 0/4 で不成立——初回よりむしろ悪化。** Matched Negative
パック(48 件中)の 12 件(25%)が昇格し、**昇格の有無に関わらず全negativeパックの
agent申告 transfer AUC は 0.480〜0.731(中央値 0.602、平均 0.598)** と、初回
(0.55〜0.71)からほぼ変化なし。baseline モデルの表現力を上げても Matched Negative の
「破壊力」は改善しなかった。

## 根本原因の特定:decile-stratified permutation 自体の設計欠陥

baseline model 強化が効かなかった理由を数学的に確認した。`_decile_stratified_permutation`
は「risk decile(10 分位)内でのみラベルをシャッフルする」設計だった。これは
**decile 内の微細な相関のみを破壊し、decile 間の陽性率相関(=risk decile の bucket
membership と target rate の関係)は完全に温存する**——bucket 内シャッフルは
bucket の陽性件数を不変に保つため、これは permutation の数学的性質として必然である。
AUC は順位統計量であり、10 段階の decile 間の相関だけで十分に chance を超えるスコアが
出せてしまう。しかも decile は baseline model 自身の risk score から定義されているため、
**同じ特徴量で学習した別モデルは高確率で同じ decile 構造を復元できる**——エージェントが
研究区間の permuted ラベルで独自にモデルを再学習した場合、破壊されたはずの信号が
decile 単位で漏れ出す。

**合成データでの再現実験(HistGradientBoostingClassifier、held-out split):**

```text
AUC(risk, decile-permuted target)                    = 0.988  (ほぼ破壊されていない)
AUC(held-out独立モデル, decile-permuted target)        = 0.700  (実測レンジ0.55-0.73と整合)
```

baseline modelを線形→非線形(HistGradientBoosting)に変更しても Matched Negative の
AUC分布がほぼ変わらなかった理由はこれで説明できる——**欠陥は baseline の表現力ではなく、
permutation のstratification設計そのものにあった。**

## 修正:decile-stratified → full random permutation

`_decile_stratified_permutation` を `_destroy_target_structure`(区間内の完全ランダム
permutation、stratificationなし)に置き換えた。区間全体の陽性率は完全に保存される
(陽性の総数は不変、割り当てる行だけがランダム化される)一方、risk と target の統計的
独立性が(期待値において)成立する——`AUC(任意のrisk score, permuted target) → 0.5`。
新 Suite `v041-trackb-03` を construct・再検証中([修正コミット](../../src/epistemic_loop/benchmark/v042_multi_competition_suite.py)、
`_destroy_target_structure` のdocstringに数学的根拠を記載)。

## 判定(2026-08-29 時点の最終)

- **P2 再現要件は v041-trackb-01・02 とも 3 構成全て不成立。ただし主因は Controller 側の
  Matched Negative 構築(decile-stratified permutation)の設計欠陥であり、「合成が実データへ
  転移しなかった」という結論の根拠にはならない。** 欠陥の根本原因を数学的・実験的に特定し、
  修正を実装済み。
- **次のステップ:** `v041-trackb-03`(full random permutation)の 12 run 再検証完了後、
  Matched Negative の agent 申告 transfer AUC が chance 水準(~0.5)に戻ったかを一次判定
  基準として再評価する。

## 正本

- [事前登録](../v041_track_b_preregistration.json)
- [Diagnostics(v041-trackb-01)](../v041_track_b_diagnostics.json)
- [Diagnostics(v041-trackb-02)](../v041_trackb_02_diagnostics.json)
- [Matched Negative 修正 v1 事前登録(baseline強化のみ、不十分と判明)](../v042_trackb_matched_negative_fix_preregistration.json)
- Suite/Lock/Submission: `.runs/v041/`(gitignore対象、ローカル実行物)
