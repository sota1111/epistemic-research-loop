# C-lite v0.4.7 方針 — 実Kaggle late submission検証環境(1日5件×2競技)

**作成日:** 2026-08-31
**status:** 方針草案+基盤実装中。**実際の`kaggle competitions submit`はまだ一度も実行していない**
——ユーザーの最終確認を得てから初回実行する(§7参照)。
**前提:** [v0.4.6結果](verification/v046_low_effort_opus_results.md)、
[c_lite_v046_policy.md](c_lite_v046_policy.md)

## 0. 背景・ユーザー指示

> それぞれのコンペを用いて一日5回のlate submittionを行う検証環境を構築してください。
> solはlowとxhighを両方同数用いること。エージェントを実行する数とどのエージェントの
> 提出物をlate submittionするかの基準を検討して報告してください。

これまでの盲検agent研究ライン(v0.4.1〜v0.4.6)は一貫して「疑似採点による代替」を
採用し、実際のKaggle submissionは行ってこなかった。一方、本リポジトリには**別の、
より古い研究ライン**(ERL v0.3.x時代のepistemic-vs-exploiter比較)による**実際の
IEEE-CIS submission履歴が既に存在する**——`kaggle competitions submissions
ieee-fraud-detection`で確認したところ、2026-08-24〜26に計14件超の実submissionがあり、
public/privateスコア双方が記録されている(例:`docs/verification/ieee_cis_arm_comparison.md`の
0.934969/0.938967は実際のsubmissionから来ている)。**Kaggleアカウント連携・API認証は
既に機能済み**(`~/.kaggle/kaggle.json`確認済み、両コンペとも`userHasEntered: True`)。
Santander側は本アカウントでの実submission履歴が0件(`kaggle competitions submissions
santander-customer-transaction-prediction`が空)。

**確認した日次submission上限:** APIから直接の上限情報は取得できなかったが、
2026-08-25のIEEE-CIS submission履歴から**同一日に正確に5件**(00:44:13〜00:45:51の
約90秒間に5件)が行われている実績を確認した——ユーザーの想定する「1日5回」と一致する。
Santanderについては同様の実績記録がなく、上限は未確認のまま5件/日と仮定して開始し、
初回実行時にKaggle側のエラー有無で検証する。

## 1. これまでの盲検研究ラインとの違い、変えない部分

**変えないもの(v0.4.4〜v0.4.6の資産をそのまま流用):**
- 列の匿名化・run_idごとの独立HMAC salting(列名は引き続き非開示)
- research(5,000行・ラベル付き)+ confirmation(1,500行・疑似採点ループ、最大20回)の
  探索フェーズは無改変
- **ローカル封印済みtransfer(1,500行、既存の`build_v044_suite`と同じ機構)は
  引き続き維持する** ——実データの一部を「模擬テスト」として保持し、Kaggleの
  結果が返ってくるまでの間、内部指標として使う(§4参照)

**新規に追加するもの:**
- research/confirmation/(ローカル)transferに加えて、**実際のKaggle test.csv
  全行**(IEEE-CIS 506,691行・Santander 200,000行)を、同一のrun_id salt で
  列名匿名化した上でエージェントに追加提供する(`real_test.csv`、行数が大きいため
  JSONではなくCSV形式)
- エージェントは、既存の`agent_submission.json`(ローカルtransfer分の予測、契約は
  無改変)に加えて、**`final_predictions.csv`(row_id,prediction、real_test.csv
  の全行をカバー)を自分のworkdirに直接書き出す**——500,000件超の予測をLLM自身の
  出力トークンとして生成するのは非現実的なため、既存の「モデルをコードで学習・
  予測する」という自然なワークフローの最終ステップとして、pandasで直接CSVに
  書き出させる(埋め込みJSONにはしない)
- Controller側は`final_predictions.csv`のrow_idを実際の`TransactionID`/`ID_code`
  に復元し(このマッピングは一貫してController専有、エージェントには非開示)、
  `sample_submission.csv`と同一スキーマの`submission.csv`を構築する

## 2. エージェント実行数と選定基準(ユーザー要請への回答)

**結論:1競技あたり1日4体のsolエージェントを実行し、4体全ての提出物を個別に
submitし、5枠目は4体の予測をブレンドした提出とする。「除外」は行わない。**

### 2.1 4体の構成

| # | reasoning effort | prompt arm |
| --- | --- | --- |
| 1 | low | P1 |
| 2 | low | P3 |
| 3 | xhigh | P1 |
| 4 | xhigh | P3 |

「solはlowとxhighを両方同数用いること」という指示を、low 2体・xhigh 2体という
最小構成で満たす。P1/P3も1体ずつで揃えることで、[v0.4.4〜v0.4.6](c_lite_v046_policy.md)で
確立した「P3がadversarial validation等の発見と結び付く」という知見を毎日の
submissionでも定性的に観察できるようにする。

### 2.2 なぜ「除外」ではなく「全員採用+ブレンド」か

当初検討した代替案は「N体(例:8体、各セル2 replicate)をスクリーニングし、
ローカルのsealed transfer AUCで上位5件を選んでsubmitする」というものだった。
これを**採用しなかった理由**:

**本リポジトリ自身の過去の知見が、ローカルスコアによる選抜を疑わしくしている。**
`docs/progress.md`に記録された過去のKaggle submission検証(ERL v0.3.x時代)は、
「Local CV had no rank correlation with the public leaderboard (tau +0.00)」
——ローカル検証スコアと実リーダーボードの順位相関がゼロだったと明記している。
この過去の知見を踏まえると、**ローカルsealed transfer AUCだけを根拠に「誰を
submitするか」を決めるのは、まさに過去に失敗したのと同じ過ちを繰り返すリスクがある**。

一方、**1日5枠に対してちょうど4体+1ブレンドという構成なら、選抜(=誰かを切り捨てる
判断)を一切必要としない**——4体全員が個別に実際のリーダーボードで評価され、
5枠目は「複数の独立した発見を組み合わせると単体より強くなるか」という、本プロジェクトが
一貫して追ってきた問い(多様性→上位解法)に直接答える。**選抜が不要な設計は、
不確かなローカル指標に依存するリスクそのものを回避できる。**

その代わり、**ローカルsealed transfer AUCは「選抜」ではなく「検証」に使う**——
毎日、4体それぞれのローカルAUC順位と、後日判明する実リーダーボードスコア順位を
突き合わせ、**「本プロジェクトの封印済みtransfer方式は、過去のnaiveなlocal CVより
リーダーボードとの相関が良いか」を継続的に検証する**(§4)。これ自体が本プロジェクトの
epistemic rigorという目的に沿った、独立した検証になる。

### 2.3 ブレンド(5枠目)の作り方

4体の`final_predictions.csv`(実test set全行の予測)を、row_id単位でrank-average
(各予測を自分の分布内での順位に変換してから平均する、スケールの違いに頑健な
標準的手法)して1つのsubmission.csvを作る。Controller側の決定論的な処理のみで
追加のエージェント実行は不要——実質コストほぼゼロで5枠目を使い切れる。

## 3. 盲検性の維持

- `real_test.csv`の列名は、その run_id の既存の列salt(`key + suite_id + run_id`
  から導出、[v0.4.4](c_lite_v044_policy.md)の`_visible_column_map_generic`と
  同一関数)をそのまま適用する——research/confirmation/(ローカル)transferと
  列名が一致するため、エージェントが既に書いたコード(列名を参照する特徴量
  エンジニアリング等)がそのまま`real_test.csv`にも適用できる。
- `real_test.csv`の行には、`TransactionID`/`ID_code`ではなく、既存の行と
  衝突しない新しい範囲(1,000,000起点)の匿名`row_id`を割り当てる。
  `row_id → 実ID`のマッピングはController側のみが保持し(暗号化は不要——
  ラベルではなく単なる行識別子の対応表だが、既存の「エージェント可視ファイルに
  実データの識別子を書かない」原則は維持する)、エージェントのworkdir・
  agent_packet.json等には一切書き込まない。
- `audit_v044_suite.py`と同じ盲検監査(禁止トークン走査)を`real_test.csv`にも
  適用する新しい監査スクリプトを用意する——列は匿名化済みだが、行数が
  competition固有(506,691/200,000)であること自体が間接的な手がかりになりうる
  ため、`RUNNER.md`・プロンプトのいずれにも競技名・行数を明記しない
  (エージェントが`wc -l`等で自発的に確認するのは許容——列匿名化と同様、
  データそのものから読み取れる情報を隠す設計ではない)。

## 4. ローカル指標と実スコアの突き合わせ(副次的検証)

各submission実行後、次の3点を記録する:

1. `finalize_v044_suite.py`と同じ機構で得た、ローカルsealed transfer AUC
   (1,500行、封印済み、既存の`_fit_capacity_matched_baseline`との比較も維持)
2. Kaggleから返る public score(即時判明)
3. Kaggleから返る private score(即時判明——両コンペとも終了済みコンペのため、
   private leaderboardも即座に開示される。ERL v0.3.x時代の履歴で確認済み)

複数日にわたってこの3指標を蓄積し、「ローカルsealed transfer AUCの順位は、
public/private スコアの順位と相関するか」を素直に計算する
(Spearman順位相関、日次4件のペアが蓄積されるごとに更新)。**もし相関が弱い/
逆転するなら、v0.4.0以降の盲検研究ライン全体が使ってきた「ローカル封印済み
transfer」という評価方法そのものの妥当性に疑問符がつく**——これは実施しない限り
検証できなかった、本プロジェクトの根幹に関わる問いである。

## 5. 実装方針

1. **`src/epistemic_loop/benchmark/v047_kaggle_submission_suite.py`(新規)。**
   `v044_full_feature_pilot.py`の`select_all_generic_columns`・
   `_visible_column_map_generic`・`_sample_split`等を再利用(cross-module
   private import、本プロジェクトで既に確立済みのパターン)。追加する関数:
   - `materialize_real_test_view(spec, key, suite_id, run_id, columns, output_dir)`:
     実test.csvを読み、同一salt・同一列集合で列名を匿名化し、`real_test.csv`と
     Controller専有の`id_map.json`(row_id→実ID)を書き出す。
   - `build_v047_suite(...)`: `build_v044_suite`と同じ構造で、4configs
     (low-P1・low-P3・xhigh-P1・xhigh-P3)に対して上記を追加実行する。
2. **`prompts/generic_research_agent/v047_p1.md`・`v047_p3.md`(新規)。**
   v044のp1/p3に、`real_test.csv`の説明と`final_predictions.csv`書き出し指示
   (「LLMの出力に予測を埋め込まず、コードで直接CSVに書き出すこと」)を追加。
3. **`scripts/build_v047_suite.py`・`run_v047_agent.py`・`audit_v047_suite.py`・
   `finalize_v047_suite.py`(新規、v044系スクリプトを土台に拡張)。**
   `run_v047_agent.py`の契約検証は、既存の`agent_submission.json`検証に加え、
   `final_predictions.csv`の行数が`real_test.csv`と完全一致することを確認する。
4. **`scripts/prepare_kaggle_submission.py`(新規)。** 完了済みrunの
   `final_predictions.csv` + `id_map.json` + `sample_submission.csv`から、
   Kaggle提出用`submission.csv`を構築する(スキーマ・行数・値域[0,1]を検証)。
5. **`scripts/blend_v047_submissions.py`(新規)。** 複数の`submission.csv`を
   rank-averageでブレンドする。
6. **`scripts/submit_kaggle.py`(新規、薄いラッパー)。** `kaggle competitions
   submit -c <ref> -f <file> -m <message>`を呼ぶだけ——**このスクリプト自体は
   実装するが、実際に実Kaggle APIへ提出する呼び出しは、ユーザーの最終確認を
   得た回のみ手動で実行する**(§7)。

## 6. 検証手順(実提出前)

1. 単体テスト(合成データ、`materialize_real_test_view`の列salt一致・
   row_id非衝突・id_map正確性を確認)
2. 実データでのbuild-only preflight(実test.csv 506,691/200,000行を実際に
   読み込み、`real_test.csv`・`id_map.json`を実際に生成、盲検監査)
3. `prepare_kaggle_submission.py`を実データのダミー予測(例:baseline
   モデルの予測)に対して実行し、生成される`submission.csv`が
   `sample_submission.csv`と行数・列名・ID集合が完全一致することを確認
   ——**この時点ではまだ実Kaggle APIを一切呼ばない**
4. 上記が全て通過した後、**ユーザーに実行許可を確認してから**、初回の
   エージェント実行(4体×2競技=8run)→submission.csv生成→実際の
   `kaggle competitions submit`(2競技×5件=10件)を行う

## 7. ユーザーへの確認事項

1. **エージェント数・選定基準(§2)の設計でよいか**——4体全員submit+
   ブレンドという「除外なし」方式か、それとも当初検討したスクリーニング+
   ローカルスコアによる上位5選抜方式にするか。
2. **初回の実`kaggle competitions submit`実行を許可するか。** 1日5件×2競技=
   10件という、当日中は取り消せない外部リソースを消費する——基盤実装・
   ローカル検証(§6の1〜3)が完了した時点で、実行直前に改めて確認する。
3. **「1日5回」を継続的な日次運用として維持するか、それとも指定日数のみの
   一時的な検証か。** 継続する場合、cron等でのスケジューリングが必要になる
   (現状は手動トリガーを想定)。
