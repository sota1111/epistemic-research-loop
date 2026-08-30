# C-lite v0.4.5 方針 — 交絡要因を分離する要因計画法(DOE)

**作成日:** 2026-08-30
**status:** 方針草案(ユーザーからの指摘を受けて起案。実験計画のみ、実行は段階的)
**前提:** [v0.4.4 方針](c_lite_v044_policy.md)、
[クロスコンペ統合分析](verification/v044_cross_competition_synthesis.md)

## 0. 問題:v0.4.4-bは2つの要因を同時に変えていた

v0.4.3-f(旧・10列制約)→ v0.4.4-b(新・全列)の間で、**同時に2つの要因が変化した**:

| 要因 | v0.4.3-f | v0.4.4-b |
| --- | --- | --- |
| **列数** | 10列(固定) | 全列(IEEE-CIS 106・Santander 200) |
| **フィードバック機構** | なし(全run凍結後にまとめて採点) | confirmation領域への疑似採点ループ(最大20回) |
| (副次的)契約形式 | cycle/lineage/null-provenance | 最小限(approach_summary + transfer_predictions) |

そのため、「36/36 runがbaselineを上回った」「AUCが0.5〜0.75→0.80〜0.89に改善した」という
v0.4.4-bの主要な結果は、**列数の効果なのかフィードバック機構の効果なのか、現状では
分離できていない**——エージェントが20回まで試行錯誤して最良のスコアを選べること
自体が、列数と無関係に大きな改善をもたらしていた可能性がある。

さらに、**「P3(自己批判)がadversarial validationを誘発する」という発見自体も、
「P3 × 全列 × フィードバックあり」の組み合わせでしか確認していない**——P3の効果が
列数やフィードバックと独立なのか、それらとの交互作用(interaction)なのかも未検証。

## 1. 要因(factor)の整理

| 記号 | 要因 | 水準 | 備考 |
| --- | --- | --- | --- |
| F1 | 列数(Columns) | {10, Full} | 主要な交絡要因その1 |
| F2 | フィードバック機構(Feedback) | {None(一発勝負), Iterative(疑似採点ループ)} | 主要な交絡要因その2 |
| F3 | プロンプトアーム(Arm) | {P1, P3} | 既にv0.4.4-b内で単独操作済み(列数・フィードバック固定) |
| F4 | reasoning effort | {low, medium, high, xhigh} | v0.4.3-f・v0.4.4-bで既に4水準確認済み、今回は xhigh に固定して次元を絞る |
| F5 | エージェントモデル(sol/opus等) | {sol, opus, ...} | **現在テスト不能**——Claude(opus)クォータ枯渇のため。既知の限界として記録し、opus復帰後に追加検証する |

本ラウンドでは F1・F2・F3 の3要因(2×2×2)を、F4=xhigh に固定して分離する
2^3 要因計画を実施する。F5は将来の課題として明示的に保留する。

## 2. 設計:2×2×2 要因計画(競技ごと)

reasoning effort を xhigh に固定した上で、列数×フィードバック×promptアームの
全8セルを構成する。**このうち4セルは既存データを再利用でき、新規に構築するのは
4セルのみ**——効率的な計画になっている。

| セル | F1 列数 | F2 フィードバック | F3 arm | データ源 | 既存run数(competition毎) |
| --- | --- | --- | --- | --- | --- |
| A | 10 | None | P1 | v0.4.3-f `SD-xhigh-P1` (screening+round2+round4合算) | 4件(既存) |
| B | 10 | None | P3 | v0.4.3-f 全P3 run(§5で無償確認済み) | 41 submission(既存、確認済み) |
| C | 10 | **Iterative** | P1 | — | **新規構築** |
| D | 10 | **Iterative** | P3 | — | **新規構築** |
| E | Full | None | P1 | — | **新規構築** |
| F | Full | None | P3 | — | **新規構築** |
| G | Full | Iterative | P1 | v0.4.4-b `F4-xhigh-P1` (screening+round2合算) | 4件(既存) |
| H | Full | Iterative | P3 | v0.4.4-b `F4-xhigh-P3` (screening+round2+round3合算) | 8件(既存) |

**新規構築が必要なのは C・D・E・F の4セル**——各セル n=4(この project の標準
再現性基準)× 2競技 = **32 run**。

## 3. 実装方針

既存の `v044_full_feature_pilot.py` を拡張する(過去の環境は必要に応じて変更してよい、
との既存の承認範囲内):

1. **列数制限オプション:** `select_all_generic_columns` の結果から、`column_limit`
   パラメータ(例:10)が指定された場合、決定論的にサブサンプルする関数を追加する
   (`suite_id` + `master_seed` からseed導出、既存の一般選択原則を維持——手で列を
   選ばない)。
2. **フィードバック無効化オプション:** `build_v044_suite` に
   `enable_confirmation_scoring: bool = True` を追加。`False` の場合:
   - `confirmation.json`・疑似採点関連のpacket フィールド(`confirmation_scorer_*`)を
     一切生成しない。
   - `research.json`・`transfer.json` のみ渡す(confirmation領域の1,500行は
     このablationでは使用しない——研究行5,000・封印行1,500で統一し、他条件との
     transfer AUC比較可能性を保つ)。
   - ランナー側(`run_v044_agent.py`)は packet に `confirmation_scorer_command` が
     存在しない場合、`score_confirmation.py` のコピー・環境変数注入をスキップする
     (packet の有無で自動判定、追加のCLIフラグ不要)。
   - プロンプトも専用のvariant(`v044_p1_noscore.md`・`v044_p3_noscore.md`、
     confirmation関連の記述を除いたもの)を用意する。
3. **既存4セル(A・B・G・H)の再利用:** 診断JSONから該当runのtransfer AUC・
   claim/approach_summaryを抽出し、新規4セルと同じ形式で集計できるようにする
   (新規コードは不要、既存 diagnostics JSON の読み出しのみ)。

## 4. 分析計画

**主効果・交互作用の分解(2^3要因計画の標準的な分析):**

- 応答変数1(連続値):transfer AUC。競技ごとに、F1・F2・F3の主効果と
  F1×F2・F1×F3・F2×F3・F1×F2×F3 の交互作用を、セル平均の比較(2^3計画なので
  符号表による効果推定、あるいは単純に完全交差表の平均差)で評価する。
- 応答変数2(二値):adversarial validation の出現有無。同じ2^3構造で、F3(arm)の
  主効果がF1・F2から独立かどうかを、セルごとの出現率(existing dataのB・H、
  新規のD・Fを比較)で判定する——**これが今回のユーザーの問いに直接答える**。
- 解釈の指針:
  - もしC・D(10列×フィードバックあり)がA・B(10列×フィードバックなし)より
    大きく改善していれば、**フィードバック機構の主効果が大きい**。
  - もしE・F(全列×フィードバックなし)がA・B より大きく改善していれば、
    **列数の主効果が大きい**。
  - もしD(10列×フィードバックあり×P3)でadversarial validationが出現すれば、
    **P3の効果は列数と独立**。出現しなければ、**列数とP3の交互作用**。
  - もしF(全列×フィードバックなし×P3)でadversarial validationが出現すれば、
    **P3の効果はフィードバック機構と独立**。出現しなければ、**フィードバック機構
    との交互作用**。

## 5. 事前の無償チェック(実施済み)——セルBを強く確定させた

新規実験着手前に、v0.4.3-f(10列・フィードバックなし)の**全P3 run**(IEEE-CIS・
Santander双方、opus/sol両モデル、全4ラウンド、41 submission・328パック)の claim
テキストを adversarial validation の兆候について再検索した。

**結果:0/328パック・0/41 submissionでadversarial validationは一度も出現しなかった
(§2表のセルBを、想定していた8件よりはるかに強い41件のサンプルで確定)。**
キーワード一致は6件あったが、精読の結果全て「context プーリング」(層2#1、pack内の
3 context間の判別可能性検定)の誤検出で、adversarial validation(research/
confirmation/transfer分割間の判別可能性検定)とは別物と判明した。

**これにより「P3単体で、列数・フィードバックと無関係に効果を発揮する」という仮説は
棄却された**——41件という大きなサンプルでも一度も出現しなかったことは、
列数かフィードバック機構(あるいはその両方)がP3の効果発現に必要な前提条件である
ことを強く示唆する。ただし「列数」と「フィードバック」のどちらが(あるいは両方が)
必要条件なのかは、この無償チェックだけでは切り分けられない——**これが、以下の
セルC・D・E・Fを構築する直接の動機である。**

## 6. 実行順序

```text
v0.4.5-a  既存データ探索(セルB・H・A・Gのadversarial validation出現率・AUC集計)
          — 新規実行不要、まず実施
v0.4.5-b  基盤整備(column_limitオプション・feedback無効化オプション・
          専用プロンプトvariant実装、単体テスト)
v0.4.5-c  セルC・D構築(10列×フィードバックあり、P1・P3)
          → build-only preflight → 盲検監査 → 実行(n=4×2競技=8run)
v0.4.5-d  セルE・F構築(全列×フィードバックなし、P1・P3)
          → 同上(n=4×2競技=8run)
v0.4.5-e  分析:2^3要因計画の主効果・交互作用を算出し、
          「列数が効いたのか・フィードバックが効いたのか・P3が効いたのか」を
          定量的に切り分ける。レポート作成。
```

## 7. 不変条件

[c_lite_v044_policy.md §7](c_lite_v044_policy.md)・[c_lite_v043_policy.md §7](c_lite_v043_policy.md)の
全不変条件を継続。追加:

10. **要因計画のセルは事前登録した設計表(本ドキュメント§2)から逸脱しない。**
    結果を見てからセルを追加・削除しない(v0.4.3-fの教訓と同じ、事後の場当たり的な
    設計変更を避ける)。
