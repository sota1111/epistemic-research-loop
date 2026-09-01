# v0.4.4 全特徴量 + 疑似採点ループ pilot — 結果(`v044-pilot-a01`)

**目的:** [preregistration](v044_full_feature_pilot_preregistration.md)。1エージェント・
1回の実行で、(1) 全特徴量(106列、既存の10列制約を撤廃)を渡せるか、(2) confirmation
領域へのローカル疑似採点ツール経由の submit→score ループが機能するか、(3) 盲検原則が
破られないか、を検証した。

**構成:** IEEE-CIS、sol(codex/gpt-5.6-sol)、reasoning_effort=high、1 run のみ
(`v044-pilot-a01/agent-01-s1`)。research 5,000行(ラベル付き)・confirmation 1,500行
(ローカルツールで繰り返し採点可能、上限20回)・transfer 1,500行(完全封印、
Controller側で最終採点)。

## 結果:機構は完全に機能した

| 項目 | 結果 |
| --- | --- |
| 全特徴量選択 | 106列(既存の10列から10倍以上) |
| 疑似採点ツールの呼び出し回数 | 20回(自己申告・実ログとも完全一致、上限まで使い切った) |
| confirmation AUC の推移 | 中央値0.757、最終5回は0.78〜0.785で収束 |
| **最終 transfer AUC(封印領域、Controller独立採点)** | **0.8315** |
| Reference baseline(capacity-matched、全106列使用) | 0.7739 |
| **baseline超え** | **✓(+0.0576)** |
| 盲検監査 | クリーン(view・transcript とも) |

## 発見(1):疑似採点ループは実際に機能し、汎化性能の改善に使われた

approach_summary(エージェント自身の報告)によれば:
- 内部CV(5-fold stratified)では CatBoost/LightGBM ブレンドが最良に見えたが、
  forward validation(時系列的な holdout)は random forest 系がより良く汎化することを
  示唆していた——**この矛盾を、confirmation の疑似採点で直接検証した**(初期 random
  forest が 0.7619、最強のブースター群は 0.739〜0.753 と、疑似採点が forward
  validation の示唆を裏付けた)。
- class weighting を外すことで confirmation AUC が 0.7799 に改善、その後 unweighted
  Gini forest と weighted entropy forest の 75/25 rank blend で 0.7852 まで到達——
  この最終ブレンドが transfer 領域の最終提出に使われた。

これは実際の Kaggle での「public LB を見ながら手法を絞り込む」という行動を模した
ものであり、**単なる技術的な feasibility 確認を超えて、疑似採点フィードバックが
実際に意思決定(内部CVとforward validationの矛盾の解消)に使われたことを示す**。

## 発見(2):confirmation でのフィードバックは transfer 領域への汎化にも繋がった

confirmation(疑似採点対象)の最終スコアは 0.7852、transfer(完全封印、疑似採点の
対象外)の最終スコアは **0.8315**——confirmation の改善が過学習ではなく、封印領域
でも(それ以上に)再現した。これは、疑似採点ループが単に「confirmation だけに
オーバーフィットする」危険な設計ではなく、健全な汎化改善のシグナルとして機能した
ことを示す一つの証拠(n=1 のため断定はできないが、少なくとも今回は過学習の兆候が
見られなかった)。

## 発見(3):106列(既存の10列)でも layer1(上位解法技術)への到達は未確認のまま

approach_summary には UID復元・時間因果集約等の layer1 技術クラスを示唆する記述は
見られない(「correlated feature families」という表現はあるが、明確な entity
resolution のようなアプローチではない)——列が匿名化されている以上、たとえ106列に
増やしても、エージェントは「どの列が card1/addr1 か」を知る術がなく、その組み合わせを
意図的に選んで UID復元的な特徴を作ることは引き続き困難と考えられる。**列数を増やす
ことは baseline 性能の改善には直結したが、layer1 技術クラスへの到達を保証するもの
ではない**——この点は次段階でより明示的に検証する価値がある(例:相関構造から
implicit なエンティティ識別子を発見できるか、というのが本当に UID復元と同等の
発見かどうかを taxonomy と照合する)。

## 盲検性への影響評価

- 静的な view・packet・prompt に禁止トークンなし。
- transcript にも禁止トークンなし——ただし監査スクリプトの初版では、エージェント
  自身の作業ディレクトリ名(`erl-v044-runs`、by design 可視)を誤って禁止トークンに
  含めてしまい、10件の偽陽性を検出した(全て単なる自分のファイル書き込みパス)。
  実際に守るべきトークン(`/workspaces/epistemic-research-loop` という実リポジトリの
  絶対パス、暗号化ラベル・鍵のパス)には一切の出現がなかった——env var 経由の
  パス注入(argv にもファイルにも書き込まない設計)が意図通り機能したことを確認。
- 疑似採点ツールは20回全て正常に呼び出され、コンペ識別子やラベル内容が返り値・
  ログに含まれていないことを確認済み。

## 結論と次のステップ

**pilot の3つの検証目標は全て達成された。** 機構としては本格スタディへ進める準備が
整った。次段階として検討すべき事項:

1. 複数 seed・複数 reasoning_effort での再現性確認(今回は n=1 の feasibility
   チェックのみ)。
2. Santander への横展開(200列全てを渡す設計への拡張)。
3. layer1 taxonomy 一致率が106列でも変わらず低いままかどうかの明示的な検証
   (今回は approach_summary の自由記述からの示唆のみ)。
4. 疑似採点回数の上限(20回)が結果に与える影響の検証(上限を変えて比較する等)。
5. 一度この設計が複数 run で確認できれば、v0.4.3-f と同様の taxonomy 照合・
   多様性測定の枠組みをこのトラックにも適用する。

## 正本

- [Preregistration](v044_full_feature_pilot_preregistration.md)
- [Diagnostics](../v044_v044_pilot_a01_agent-01-s1_diagnostics.json)
- 生データ:`.runs/v044/agent_outputs/v044-pilot-a01/agent-01-s1/`
