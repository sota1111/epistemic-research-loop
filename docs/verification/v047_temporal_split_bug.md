# 発見:`_sample_split`の時系列分割が、v0.4.4以降ずっと機能していなかった

**発見日:** 2026-08-31(v0.4.7実提出結果を受けた「次のエージェント計画」検討中に発見)
**分類:** 盲検インシデントではなく、方法論上のバグ。エージェントへの情報漏洩はない
——research/confirmation/transferの区切り方そのものが、意図と異なっていた。

## 1. バグの内容

`src/epistemic_loop/benchmark/v044_full_feature_pilot.py`の`_sample_split`は、
`CompetitionSpec.time_column`が設定されている場合(IEEE-CISの`TransactionDT`)、
research(訓練)/confirmation/transfer(封印済み評価)の3領域を**時系列順に
分離するよう意図されていた**——`sort_values(time_column)`を呼んでいたことが
その証拠。しかし、ソート直後に無条件で`frame.sample(n=total, random_state=...)`
という**ランダムサンプリング**を呼んでいた。pandasの`.sample()`は入力の行順を
保持せず、返される行は常にランダムな順序になる——つまり**直前のソートの効果は
完全に打ち消されていた**。

実際のsuiteデータ(`v047-suite-a01`)で検証したところ、research/confirmation/
transferの3領域はいずれもTransactionDTの範囲・平均がほぼ同一(データセット全体の
時間範囲をまんべんなくカバー)していた——**時系列的な分離は一度も起きていなかった**。

## 2. 影響範囲

- **影響を受けるのはIEEE-CISのみ。** Santanderは`time_column=None`のため、この
  コードパスを通らず無関係(実際、[実提出結果](v047_real_submission_results.md)で
  Santanderのローカル-実相関が完璧だったことと整合する)。
- **v0.4.4以降の全IEEE-CIS suite**(v044-suite-a01〜a07、v047-suite-a01)が対象。
  ただし、これらのラウンドの結論(adversarial validation・compositional構造発見・
  P3との紐付け等)は「research/confirmation/transferがランダム分割だった」という
  前提でも成立する内容であり、**このバグによって過去の発見内容が無効になるわけ
  ではない**——影響するのは「sealed transferが実test.csvとの分布差を模倣できて
  いたか」という一点であり、これはまさに[実提出結果](v047_real_submission_results.md)の
  「ローカルAUCがIEEE-CISの実スコアを全く予測できなかった(ρ=-1.000)」という
  結果の**説明の一部**になる——sealed transferが時系列的な分離を伴わない
  ランダム分割だった以上、実test.csv(訓練データより後の時期)との分布差を
  そもそも観測しようがなかった。

## 3. 修正

`_sample_split`を修正し、`time_column`が設定されている場合は、ソート済みフレームから
**連続した窓(`total`行)を直接スライスする**方式に変更した(`frame.iloc[start:start+total]`)。
窓の開始位置はseed由来(`suite_id`+`master_seed`)で決定論的に選ぶため、suiteごとに
異なる時期の窓を見ることになるが、**suite内では常にresearch < confirmation < transfer
の時系列順**が保たれる。`time_column`が設定されていない競技(Santander等)の挙動は
無変更。

実データで再検証:research(TransactionDT 4126136–4247144)< confirmation
(4247190–4305443)< transfer(4305448–4333312)——連続的で重複のない時系列窓に
なっていることを確認した。回帰テストも追加(`test_sample_split_with_time_column_is_genuinely_temporal`)。

## 4. 次への示唆

この修正により、**IEEE-CISの「sealed transfer」が初めて、実test.csvとの関係性
(訓練データより時系列的に後)を模倣する構造になった**。[次のエージェント計画](../c_lite_v048_policy.md)では、
この修正版を使ってIEEE-CIS向けに新しいsuiteを構築し、「時系列的に正しいsealed
transferなら、ローカルAUCの実スコア予測力が回復するか」を検証する。

## 正本

- [c_lite_v047_policy.md](../c_lite_v047_policy.md) / [実提出結果](v047_real_submission_results.md)
- [c_lite_v048_policy.md](../c_lite_v048_policy.md)(次ラウンド計画)
