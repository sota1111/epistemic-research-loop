# C-lite v0.4.6 方針 — reasoning effort=low での「全列×フィードバック×アーム」再検証

**作成日:** 2026-08-31
**status:** 方針草案(ユーザー指定の制約に基づき起案。実験計画のみ、実行は未承認)
**前提:** [v0.4.5 方針](c_lite_v045_policy.md) / [v0.4.5 要因計画結果](verification/v045_factorial_design_results.md)、
[v0.4.4 方針](c_lite_v044_policy.md)

## 0. 背景・動機

直近のユーザーからの質問(「リーズニングの違いによる多様性や未知の構造の発見の性能の
違いはありますか？」)への回答で、既存データから次の2点が判明した:

1. **生の性能(transfer AUC)は reasoning effort に対してコンペ依存**——Santander は
   ほぼ単調(low<medium<high<xhigh)、IEEE-CIS は非単調(high effort が谷になる)。
2. **技術クラスの多様性・未知構造の発見は reasoning effort にほぼ左右されない**——
   adversarial validation は P3 アームの低・中・高・xhighの**全4水準**で独立に出現し、
   effort の高低は関係なかった。一方 Santander の実際の公開技術は xhigh を含む
   全水準・全ラウンド(n=22)で一度も発見されなかった。

ただし、この2点はいずれも**「全列 + フィードバックあり」という単一のフィードバック
条件下でのeffort比較**(`v044-suite-a01`/`b01` のscreeningラウンド)にとどまる。
[v0.4.5のDOE](c_lite_v045_policy.md)はフィードバック要因を分離したが、effortはxhighに
固定していたため、**「フィードバックなし条件でeffortを下げるとどうなるか」
「effortが低くてもフィードバックが性能・発見の質を補えるか」は未検証のまま**である。

今回、ユーザーから次の制約が与えられた:

1. **reasoning effort = low に固定**(高コストのxhighではなく、低コストな水準での
   再現性・実用性を検証する)
2. **フィードバック機構は{None, Iterative}の両方を要因として維持する**
3. **列数は全列のみを使う**(10列条件は本ラウンドで扱わない——v0.4.5で列数の主効果が
   明確になり、10列を維持する理由が薄れたため)

## 1. この設計が答える問い

1. **「低reasoning effort × フィードバックあり」は、xhighに迫る性能を出せるか?**
   もし出せれば、フィードバックループ(疑似採点による反復)は高価なreasoning effortの
   代替になりうる——実務上重要な知見になる。
2. **P3→adversarial validation の紐付けは、effort=lowでも(フィードバックの有無を
   問わず)成立するか?** 既存データ(`F4-low-P3`、全列+feedback)ではn=1で示唆されて
   いるのみ。フィードバックなし条件でも同じパターンが出るかは全くの未検証。
3. **v0.4.5で発見した「feedbackの主効果はコンペ依存(IEEE-CISで強・Santanderで弱)」
   は、effort=lowでも同じ方向・大きさで見られるか、それともeffortとfeedbackの間に
   交互作用があるか?** 「reasoning力が低いエージェントほど、feedbackによる反復補正の
   価値が相対的に大きくなる」という仮説は理論的にもありうる——初手の質が低いほど、
   試行錯誤による修正の余地が大きいため。

## 2. 要因の整理

| 記号 | 要因 | 本ラウンドでの扱い |
| --- | --- | --- |
| F1 列数 | 全列に固定(10列条件は本ラウンドで扱わない) |
| F2 フィードバック機構 | {None, Iterative} 可変(主要因) |
| F3 プロンプトアーム | {P1, P3} 可変(主要因) |
| F4 reasoning effort | low に固定(v0.4.5のxhigh固定と対をなす断面) |
| F5 エージェントモデル | 引き続き未検証(Claude/opus quota問題は継続、既知の限界) |

つまり本ラウンドは、v0.4.5と同じ2×2要因計画(フィードバック×アーム)を、
effort=lowという新しい断面で実施する。

## 3. 設計表

| セル | フィードバック | アーム | データ源 | 状態 |
| --- | --- | --- | --- | --- |
| I | None | P1 | — | 新規構築(n=4×2競技) |
| J | None | P3 | — | 新規構築(n=4×2競技) |
| K | Iterative | P1 | `v044-suite-a01`/`b01` の `F4-low-P1`(既存n=1/競技)+新規n=3/競技 | 一部既存、追加構築 |
| L | Iterative | P3 | `v044-suite-a01`/`b01` の `F4-low-P3`(既存n=1/競技)+新規n=3/競技 | 一部既存、追加構築 |

各セル最終的にn=4(このprojectの標準再現性基準)×2競技。
**新規実行数 = (I:4 + J:4 + K:3 + L:3) × 2競技 = 28 run。**
既存の`F4-low-P1`/`F4-low-P3`(各競技1run、盲検監査済み)をセルK/Lにそのまま合算する。

## 4. 参照比較(既存データ、再実行不要)——effort×feedbackの交互作用を追加コストゼロで評価

同一の列数・フィードバック条件でeffort=xhighの結果が既にあるため、再実行せず
参照点として使う:

- セルG/H(`v044-suite-a01/a02/a03`・`b01/b02/b03`、全列+feedback+xhigh、
  P1:n=4/競技・P3:n=11/競技) vs 本ラウンドK/L(全列+feedback+low)
- セルE/F(`v044-suite-a05`・`b05`、全列+no-feedback+xhigh、各n=4/競技)
  vs 本ラウンドI/J(全列+no-feedback+low)

これにより、新規構築ゼロで「effort×feedback×アーム」の3元交差を評価できる
——4つの新規セル(I・J・K・L)と4つの既存セル(E・F・G・H)を組み合わせた、
実質2×2×2(effort×feedback×アーム、列数=全列固定)の分析になる。

## 5. 分析計画

- **応答変数1(連続値):transfer AUC。** 4象限(low×no-fb=I/J、low×fb=K/L、
  xhigh×no-fb=E/F、xhigh×fb=G/H)のセル平均を比較し、feedbackの効果量が
  effort水準で変わるか(交互作用)を見る。特に問い1(低effort+feedbackがxhighに
  迫れるか)は、K/LのAUCをG/Hと直接比較することで判定する。
- **応答変数2(二値):adversarial validation出現率。** P3アーム限定で、
  low×no-fb(J)・low×fb(L)・xhigh×no-fb(F)・xhigh×fb(H)を比較する。
  「P3さえあれば、effort・feedbackの組み合わせに関係なく出現するか」を検証する
  ——もしJ・Lがいずれも高頻度で出現すれば、「P3が唯一のゲート条件であり、
  effortもfeedbackも出現の有無そのものには影響しない(出現率の微調整のみ)」という
  v0.4.5の結論がeffort軸でも成り立つことになる。

## 6. 実装方針

既存インフラ(`build_v044_suite`の`column_limit=None`・`enable_confirmation_scoring`
パラメータ、v0.4.5-bで実装済み)がそのまま使える。新規に必要なのは設定データのみ:

1. `v044_full_feature_pilot.py`に新しいconfig辞書を追加:
   - `V046_LOW_NOFB_CONFIGS`(セルI/J用、新規4 seed×2アーム、
     `reasoning_effort="low"`固定、`column_limit=None`)
   - `V046_LOW_FB_CONFIGS`(セルK/L用、`F4-low-P1`/`F4-low-P3`の既存seedと
     重複しない新規3 seed×2アーム、`reasoning_effort="low"`固定)
2. `build_v044_suite.py`/`run_v044_batch.py`/`audit_v044_suite.py`/
   `finalize_v044_suite.py`に`--config-set low-nofb`・`low-fb`を追加
   (v0.4.5の`10col-fb`/`full-nofb`と全く同じパターン)。
3. `build_v044_suite`自体の関数シグネチャ変更は不要——`column_limit=None`
   (デフォルト)・`enable_confirmation_scoring`の真偽を切り替えるだけ。
4. 既存セルK/Lの「既存n=1」を含めた集計は、`finalize_v044_suite.py`実行後、
   `v044-suite-a01`/`b01`の診断JSONから該当run(`F4-low-P1`/`F4-low-P3`)を
   抽出して新規run群と結合する(新規コード不要、既存JSONの読み出しのみ)。

## 7. 実行順序(案)

```text
v0.4.6-a  基盤整備(config辞書追加・CLI配線、単体テストは不要見込み——
          v0.4.5-bのbuild_v044_suite拡張をそのまま使うため新規ロジックなし)
v0.4.6-b  セルI・J構築(全列×フィードバックなし×low、P1・P3)
          → build-only preflight → 盲検監査 → 実行(n=4×2競技=8run)
v0.4.6-c  セルK・L構築(全列×フィードバックあり×low、P1・P3)
          → 同上(n=3×2競技=6run、既存n=1/競技と合算しn=4に)
v0.4.6-d  分析:4象限(low/xhigh × no-fb/fb)のAUC比較・adversarial validation
          出現率比較。問い1〜3への回答をレポート化。
```

## 8. 不変条件

[c_lite_v045_policy.md §7](c_lite_v045_policy.md)までの全不変条件を継続。追加なし
(本ラウンドは新しい機構を導入せず、既存機構をeffort=low断面で再検証するのみ)。

## 9. ユーザーへの確認事項

1. **この設計(セル定義I〜L・サンプルサイズn=4/セル/競技・既存データ再利用方針)でよいか。**
2. **実行してよいか。** 新規28 run(既存インフラそのまま流用のため実装コストは
   小さいが、real API costが発生する)。
