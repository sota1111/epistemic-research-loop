# C-lite v0.4.4 方針 — 全特徴量設計での sol reasoning-effort 多様性ラウンドのやり直し

**作成日:** 2026-08-30
**status:** ユーザーが承認(2026-08-30)。「IEEE-CIS・Santander両方を列数限定なしで、
解法多様性・上位解法相当の存在・未知構造発見の両方を目指す環境を構築し、sol の
reasoning-effort 違いで、7時間の間、仮説立案・検証・試行錯誤・レポート作成を承認不要で
実行してよい」との指示を得た。v0.4.4-a(基盤整備:Santander対応・複数run対応)完了。
**v0.4.4-b(screening+確認ラウンド、計28 run×2コンペ)完了。** 8/8構成が両コンペで
baselineを上回り(10列制約下の不安定さから一変)、adversarial validation が
prompt_arm(P3)に完全に決定される形で両コンペ・両ラウンド通算14/14 P3・0/14 P1と
確定した。詳細:
[クロスコンペ統合分析](verification/v044_cross_competition_synthesis.md)。
**前提:** [v0.4.3 方針](c_lite_v043_policy.md)、
[10列制約インシデント記録](verification/v044_ten_column_constraint_incident.md)、
[v0.4.4 pilot preregistration](verification/v044_full_feature_pilot_preregistration.md) /
[結果](verification/v044_full_feature_pilot_results.md)

## 0. 背景(なぜこの方針が必要か)

[10列制約インシデント記録](verification/v044_ten_column_constraint_incident.md)の通り、
v0.4.1〜v0.4.3 の全 real-data 実験(本セッションだけで 90 run 以上)は、合成データ用
生成器から無改変で継承した固定10列スキーマの下で行われていた——この制約はユーザーの
承認を得ずに導入され、開示すべきリスクとしても記録されていなかった。v0.4.4 pilot
(全106列 + ローカル疑似採点ループ、1エージェント・1回)は、この制約を撤廃した設計が
機構として機能し、実際に発見の質を引き上げる(reference baseline AUC 0.774 → 実
エージェント最終スコア 0.8315)ことを確認済み。

本方針は、直前に行った **v0.4.3-f(sol reasoning-effort 多様性ラウンド、4ラウンド・
34 run)を、この修正済み全特徴量設計でやり直す**計画を定める。v0.4.3-f 自体が導いた
結論(diversity 指数・layer1/layer2 一致率・「加法性の限界」候補等)は、10列という
上限の中でのみ妥当であり、全特徴量下でどうなるかは別問題として再検証する必要がある。

## 1. v0.4.4-a:全特徴量設計への完全移行(基盤整備)

pilot は IEEE-CIS・1エージェント・1回のみだったため、本格運用に向けて以下を整備する:

1. **Santander への横展開。** `select_all_generic_columns` は `CompetitionSpec` を
   受け取る汎用関数のため、Santander(200列)にもそのまま適用できる——コンペ固有の
   追加実装は不要と見込まれる(pilot と同様、build-only preflight で確認してから
   実行に進める)。
2. **複数 run 対応。** pilot は単一 run(`agent-01-s1`)のみを想定した設計だった。
   v0.4.3-f と同じ 8 run(reasoning_effort × prompt_arm)を1つの suite として build
   できるよう、`build_v044_pilot` を複数 run_id に対応させる(内部的には同じ処理を
   run_id ごとに繰り返すだけで、大きな設計変更は不要と見込む)。
3. **疑似採点ツールの呼び出し上限(20回)の妥当性。** pilot では1エージェントが
   ちょうど上限まで使い切った——上限が窮屈すぎて途中で打ち切られた可能性を否定できない。
   本格運用前に上限を緩和する(例:50回)か、あるいはそのまま据え置くかを検討する
   (据え置く場合も、上限到達が結果に与える影響を diagnostics に記録する)。

## 2. v0.4.4-b:sol reasoning-effort 多様性ラウンドの再実施

v0.4.3-f と**同一の段階的設計**(screening n=1 → 確認 n=4 → population拡大 n=8)を、
全特徴量設計の上でやり直す。既存の8セル(low/medium/high/xhigh × p1/p3)構成・sol
単独・seed 系列も含め、そのまま踏襲する(実行構成そのものに問題があったわけではない
——問題は列数のみだったため)。

**新たに追跡する軸(v0.4.3-f にはなかった、今回追加する検証項目):**

1. **layer1(上位解法技術クラス)一致率が全特徴量下で変化するか。** IEEE-CIS の
   0% という結果が、匿名化単体によるものか、列数不足との合わせ技だったのかを直接
   検証する——列数を増やしても 0% のままなら「匿名化が主要因」、有意に増えるなら
   「列数不足が主要因だった」と判定できる。
2. **疑似採点ループの利用パターンの diversity への影響。** confirmation フィード
   バックを使った反復的な精緻化が、promoted パックの技術クラス多様性にどう影響するか
   (pilot は数値スコアの改善に使われたことは確認できたが、技術クラスの多様性への
   影響は単一 run では判定できない)。

## 3. 実行順序

```text
v0.4.4-a  基盤整備(Santander対応・複数run対応・呼び出し上限の検討)
v0.4.4-b1 IEEE-CIS screening(8run、n=1/セル)→ build-only preflight → 盲検監査 → 実行
v0.4.4-b2 Santander screening(8run、n=1/セル)→ 同上
v0.4.4-b3 (b1・b2の結果を見て)確認ラウンド・population拡大ラウンドを v0.4.3-f と
          同じ基準で計画・実施
v0.4.4-c  結果を既存の v0.4.3-f ドキュメントと対比し、
          クロスコンペ統合分析・taxonomy を更新
```

## 4. 不変条件(v0.4.0〜v0.4.3 から継続、今回1件追加)

1〜8(既存、[c_lite_v043_policy.md §7](c_lite_v043_policy.md) 参照)に加え:

9. **既存コードの無改変での流用が、後から見て「発見の上限・射程を左右する」性質を
   持つ場合、それが自明な実装詳細に見えても、preregistration 文書の「開示するリスク」
   節に明記し、可能な限りユーザーに一言確認を取ること。** 「コードを再利用できるから」
   という理由だけで、スコープを左右する設計を無審査のまま採用しない
   ([10列制約インシデント記録](verification/v044_ten_column_constraint_incident.md)の教訓)。

## 5. ユーザーへの確認事項

1. **この優先順位(まず基盤整備→IEEE-CIS→Santanderの順)でよいか。**
2. **疑似採点ツールの呼び出し上限(20回)を緩和するか、据え置くか。**
3. **v0.4.3-f の既存ドキュメント(diversity指数・taxonomy一致率等)を「10列制約下の
   結果」として明示的に格下げ・注記した上で保持する方針(削除はしない)でよいか。**
