# C-lite v0.4.7 方針 — 実Kaggle late submission検証環境(1日5件×2競技)

**作成日:** 2026-08-31
**status:** 世代1(sol 8体+opus 4体×2競技)実行完了(23/24、詳細:
[世代1結果](verification/v047_generation1_results.md))。選定基準を巡るユーザーとの
議論の末(§2.3、複数の却下案を経て確定)、世代2(crossover)は見送り、機械的な
AUC上位4体+ブレンドという基準(§2.4)で両競技とも**5枠分のsubmission.csvを
準備・検証済み**(スキーマ・行数・値域を確認、`.runs/v047/submissions/`)。
**実際の`kaggle competitions submit`はまだ一度も実行していない**——ユーザーが
明示的に「まだ許可しない」と回答済み、次の提出許可確認を待っている。運用形態は
「継続的な日次運用ではなく、今回の検証のみ(1回か数回)」とユーザーが確認済み
——cron等のスケジューリング基盤は構築しない。
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

## 2. エージェント実行数と選定基準(ユーザー要請への回答・改訂版)

**改訂の経緯:** 当初案(sol 4体全員submit+ブレンド、選抜なし)を提示したところ、
ユーザーから次の指示を得た:

> より多くのエージェントを動作検討させ、進化と探索の両方に繋がる提出方法を
> 検討してください。稼働するエージェントにはOpusも含めること。どれを提出するかの
> 判断基準を策定してください。都度、あなたが考えるでも良いです。

これを受け、**個体数を増やしopusも含めた「世代1(探索)→世代2(進化/exploitation)」の
2段階構成**に改訂する。選抜基準は固定式ではなく、その回の実際の結果を見て判断する
(ユーザーの「都度、あなたが考えるでも良い」という許可に基づく)——ただし判断の
「型」は以下の通り事前に定める。

### 2.1 世代1(探索・population):1競技あたり12体

| モデル | reasoning effort | prompt arm | 体数 |
| --- | --- | --- | --- |
| sol | low | P1 | 2 |
| sol | low | P3 | 2 |
| sol | xhigh | P1 | 2 |
| sol | xhigh | P3 | 2 |
| opus | (dial無し) | P1 | 2 |
| opus | (dial無し) | P3 | 2 |

「solはlowとxhighを両方同数用いること」(4/4)を維持しつつ、各セルにreplicate
n=2を持たせ(単一replicateのnoveltyを過信しないという[v0.4.3-fの教訓](c_lite_v043_policy.md)
を踏まえる)、[v0.4.6](c_lite_v046_policy.md)で「opusがsolにない発見(UID復元等)に
独立到達した」という知見を踏まえ、opusも本ラウンドから正式に候補プールへ加える。
12体全員が、research/confirmation/(ローカル)transferに加えて実test.csv全行の
`final_predictions.csv`を生成する(§1参照、既存インフラ無改修)。

### 2.2 世代2(進化・exploitation):1競技あたり2体

**当初計画していた「世代2(単一の最良個体をさらに改善させる)」は、実行前の
ユーザーとの議論を経て見送った。** 経緯と最終方針は§2.3で説明する。

### 2.3 選定基準の確定に至る議論(重要——後続ラウンドでも踏襲すること)

世代1完了後、「どの個体を実際に提出するか」の基準を巡ってユーザーと複数往復の
議論を行い、当初案は全て却下された。**この議論そのものが本ラウンドの重要な
成果であり、記録として残す:**

1. **却下案1:「ローカルAUC最良の1体だけを進化(世代2)させる」。** ユーザーの
   指摘:1親だけでは解法の多様性が失われる。実際、Santanderでreal/synthetic
   行判定を発見した個体(`agent-06-r1`)は最良AUC個体ではなかった。
2. **却下案2:「新規性の高い発見をした個体も追加で進化させる」。** ユーザーの
   指摘:「新規性が高い」をどう判定するのか?
3. **却下案2a:「Controller専有のtaxonomy文書と照合する」。** これは**現実の
   コンペでは参加者が持ちえない知識(実際の公開解法が何を使ったか)を使う
   先読みバイアス**であり、盲検研究の趣旨に反すると自己指摘し却下。
4. **却下案2b:「複数の独立エージェントが同じ発見に至ったことを根拠にする」。**
   ユーザーの指摘:一致した2体はどちらもopusであり、**同一モデルが共有する
   バイアス・局所解を「独立な収束」と誤認するリスク**を排除できない——鋭い
   指摘で、案2aと同様の構造的欠陥と認めた。
5. **却下案2c:「Controller(私)が実データに対して独立に再計算し、主張を
   直接検証する」。** 実際に検証を実施し(Santanderのreal/synthetic分割・
   IEEE-CISの分布シフトを、エージェントのコードを使わず生データから再現、
   §1・§2参照)、主張自体は真実だったと確認できた。しかしユーザーの指摘:
   これも結局「私が解法を見て判断している」ことに変わりはなく、実世界の
   フィードバック(実リーダーボードスコア)を経ずに価値判断を下している点で
   同じ問題を抱えている。
6. **転換点:「進化と探索は提出そのものを通じて両立させる」。** 事前に
   Controllerが「どれが価値ある発見か」を判定しようとすること自体をやめ、
   **世代1の多様な候補をそのまま提出し、返ってきた本物のスコアを次ラウンドの
   判断材料にする**、という方針に転換した。世代2(crossover)は見送り、
   提出前の追加エージェント実行は行わない。
7. **最後の疑問:「sealed transfer AUCも結局、答えを知っているから採点できる
   基準ではないか?」** これも重要な区別を要した——sealed transfer AUCは
   train.csv由来の(エージェントには見せていない)ラベルを使うが、これは
   **実際のKaggle参加者も普通に行う手元検証(自分のtrainデータの一部を
   ホールドアウトする)と同じ操作**であり、実コンペの正解そのもの(taxonomy)
   を覗き見るのとは性質が異なる、と整理した。ただし本プロジェクト自身の
   過去の知見(`docs/progress.md`「Local CV had no rank correlation with the
   public leaderboard」)を踏まえ、**sealed transfer AUCが実スコアを予測できる
   保証はない**——これは不正な基準ではないが、絶対的に正しい基準でもなく、
   **それ自体が今回検証したい仮説の一部**である、という位置づけで合意した。

### 2.4 確定した選定基準(v0.4.7-e実行分)

1日5枠(1競技あたり)を、事前登録済みの機械的基準のみで埋める。**approach_summaryの
内容を読んでの主観的選抜は行わない:**

| 枠 | 基準 |
| --- | --- |
| 1〜4 | ローカルsealed transfer AUC上位4個体(盲検インシデントでタイントと
  判定された個体は事前に除外——[env var盲検インシデント](verification/v047_env_var_blindness_incident.md)) |
| 5 | 有効な全個体(タイント除く)の`final_predictions.csv`をrow_id単位で
  rank-averageしたブレンド |

**この基準の下で、新規性の高い発見をした個体は結果的に含まれた**(IEEE-CISの
`agent-05-r2`はAUC3位、Santanderの`agent-06-r1`・`agent-05-r2`はAUC2位・3位)
——事前に「新規性」を判定する主観的なステップを挟まなくても、今回はAUC順位
だけで両立した。ただし**これは今回たまたま両立しただけであり、常に成り立つ
保証はない**——次ラウンド以降、AUC上位に多様性が反映されない場合の対応は
改めて検討する。

**実提出後の運用:** 実際のリーダーボードスコアが判明した後、どの系統を
残す・改善する・打ち切るかは、**改めてユーザーの確認を得た上で決定する**
(ローカルAUCでもController判断でもなく、実スコアを主たる根拠とする)。

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
4. 世代1(sol 8体+opus 4体=12体/競技)を実行 → ローカルsealed transfer AUCで
   最良個体を特定 → 世代2(親から分岐した改善試行、sol+opus各1体/競技)を実行
5. §2.3の型に沿って5枠(exploitation×2・exploration×2・ensemble×1)の
   具体的な候補individualをその都度選定し、`submission.csv`を生成
   ——**この時点でもまだ実Kaggle APIを一切呼ばない**
6. 生成した5件の候補(と選定理由)をユーザーに提示し、**実行許可を得てから**
   実際の`kaggle competitions submit`を行う

## 7. ユーザーへの確認事項(更新履歴)

1. ~~エージェント数・選定基準(§2)の設計でよいか~~ → **回答済み(2026-08-31)**:
   「より多くのエージェントを動作させ、進化と探索の両方に繋がる提出方法を検討し、
   opusも含め、判断基準は都度考えてよい」——§2を改訂版に更新済み。
2. **初回の実`kaggle competitions submit`実行の許可** → **未許可(2026-08-31時点)**:
   「まだ許可しない」との回答。世代1・世代2の実行とsubmission.csv生成までは進め、
   実際のsubmitの直前で改めて確認する。
3. ~~「1日5回」を継続運用にするか~~ → **回答済み(2026-08-31)**:「今回の検証のみ
   (1回か数回)」——cron等の日次スケジューリング基盤は構築しない。
