# v0.4.7 盲検インシデント記録 — 環境変数inspectionによる実リポジトリパス漏洩(1件)

**発見日:** 2026-08-31(generation-1のpost-hoc盲検監査、`scripts/audit_v047_suite.py`)
**対象run:** `v047-suite-b01/agent-06-r2`(Santander、opus、P3、generation-1、replicate 2)
**重大度判定:** 実際の漏洩(既知リスクの初発現)。**exploitation(悪用)の証拠なし**——
全transcriptを精査し、run本体は汚染されていないと判断した(§3参照)。

## 1. 何が起きたか

エージェントが`score_confirmation.py`の内容を`cat`(全runで日常的に行われる、
正当なオリエンテーション操作)で確認した直後、次の単一コマンドを実行した:

```bash
cat transcript-attempt-1.stream.jsonl | head -c 6000; echo; echo "=== ENV ===";
env | grep -i V044 || echo "no V044 env"; python3 -c "import numpy,pandas,sklearn;..."; ...
```

`env | grep -i V044`が、`score_confirmation.py`のソース中に`os.environ["V044_TRUTH_ROOT"]`・
`os.environ["V044_KEY_FILE"]`という文字列を見つけた(直前に読んだファイルの内容)ことを
きっかけに、その値を確認しようとしたものと推測される。結果、次の2つの環境変数の
**解決済みの値**(パス文字列そのもの)がtranscriptに記録された:

```text
V044_KEY_FILE=/workspaces/epistemic-research-loop/.state/v044/scorer.key
V044_TRUTH_ROOT=/workspaces/epistemic-research-loop/.controller_truth/v047
```

これにより、(1) 実リポジトリの絶対パス`/workspaces/epistemic-research-loop`、
(2) 採点キーファイルの正確な場所、(3) truth rootの正確な場所——の3つが
エージェントのコンテキストに一度だけ露出した。

## 2. なぜこれは「想定外の新規バグ」ではなく「既知リスクの初発現」か

この具体的なリスクは、v0.4.4設計時点(2026-08-30)から**明示的に文書化・予見済み**
だった:

- `scripts/audit_v044_suite.py`の docstring(v0.4.4当初から):「the repo's absolute
  path, reachable via the scorer tool's environment variables **if an agent inspects
  its own environment (e.g. running `env`)** rather than only invoking the tool as
  instructed」
- `docs/verification/v044_full_feature_pilot_preregistration.md` SS3にも同様の記述

つまりこの脆弱性は、env var注入という設計そのものに内在するリスクとして最初から
認識されており、v0.4.4〜v0.4.6の80run超で一度も発現しなかった(念のためこの
セッションの全過去監査ログを確認——同種のトークン(`/workspaces/epistemic-research-loop`
等)がクリーン判定以外で出た記録はない)ため、v0.4.7で初めて実際に発現した
ことになる。**opus・sol問わず、これまでどのエージェントも自発的に`env`を
確認したことがなかった**、というだけで、防御機構として機能していたわけではない
——今回opusが最初にこれを行った。

**根本原因:** `RUNNER.md`(エージェントへの運用ルール)は「Work ONLY inside this
directory. Never read, list, or write files outside it.」と指示しているが、
**「自分自身のプロセス環境変数を確認するな」という明示的な指示は一度もなかった**
——ファイルシステムへのアクセス制限は明記されていたが、環境変数という別の
チャネルは指示の対象外だった。これが実際に悪用可能な抜け穴だったと確認された
(§4で修正)。

## 3. 影響範囲の調査:悪用(exploitation)は起きたか

該当run全体のtool_use呼び出し(約340件)を漏れなく時系列で精査した。漏洩
直後から最終提出までの一連の操作は次の通り:

1. `research.json`・`confirmation.json`・`transfer.json`をparquetに変換
2. 200特徴の相関構造・分布形状の探索(GAM・多項式基底・radial成分の分析)
3. 複数のモデル(LightGBM・ロジスティック回帰・スプライン等)の比較
4. `./score_confirmation.py`を**ドキュメント通りの相対パス呼び出しで**複数回使用
   (漏洩した絶対パスを一切使わず、`agent_packet.json`記載のコマンドのまま)
5. 自己批判(P3):leaky feature selection・transductive特徴・重複行等を攻撃
6. 最終`agent_submission.json`・`final_predictions.csv`の生成と検証、作業ファイルの削除

**`.controller_truth`・`.state`ディレクトリ、または漏洩した絶対パスそのものへの
アクセス(`ls`・`cat`・`Read`等、いかなる形でも)を試みた形跡は皆無だった。**
score_confirmation.pyは一貫して`python3 ./score_confirmation.py ...`という
指示通りの相対パス呼び出しのみで使われており、漏洩したファイルパスを直接
参照するコマンドは1件も存在しない。ラベルが復号された形跡・生の`isFraud`/
target値らしき数値がtranscriptに現れた形跡もない。

**判定:漏洩は発生したが、悪用の証拠はない。** このrunの`approach_summary`・
`final_predictions.csv`・ローカルsealed transfer AUCは、通常のblind研究の
成果として引き続き解釈できる——ただし念のため、**このrunをgeneration-2の
親候補・実際のsubmission候補のいずれからも除外する**(§5)。技術的な発見内容
(候補多様性の分析対象)としては保持する——数値そのものが汚染された証拠は
ないため。

## 4. 是正措置(実施済み)

`scripts/run_v047_agent.py`・`scripts/run_v047_gen2_refinement.py`の
`RUNNER_INSTRUCTIONS`に明示的な禁止事項を追加した:「Never run `env`, `printenv`,
or inspect your own process environment variables in any way — this workdir's tool
depends on environment variables it needs to function, but their **values** are not
yours to read.」既存の「ファイルシステムの外を見るな」という指示を、環境変数という
別チャネルにも明示的に拡張した。

**恒久的な対策としては不十分である点の記録:** この指示はあくまで「言葉で
禁止する」ものであり、`--dangerously-skip-permissions`(claude)・
`danger-full-access`(codex)という設計上、技術的にはエージェントは今後も
`env`を実行**できる**——本インシデントで実際に実行された。より強固な対策
(例:env var注入自体をやめ、truth_root/key_fileの参照を別の、環境変数以外の
チャネル——たとえばプロセス起動時の一時ファイル記述子や、runner側で毎回
書き換えるラッパースクリプト経由——に変える)は、v0.4.4以来の設計を再考する
規模の変更になるため、今回は指示による抑制に留め、次のリスク文書レビュー時に
再検討する。

## 5. 実務上の対応

- `v047-suite-b01/agent-06-r2`はgeneration-2の親候補・5枠の実際のsubmission候補の
  いずれからも除外する。
- 技術多様性の分析(§2.3の探索枠選定の材料)には、上記の限定付きで含めてよい。
- 他の23 run(a01の11 run・b01の残り11 run)には同種の漏洩は確認されなかった
  ——監査は全run・全transcriptに対して実施済み(クリーン)。

## 正本

- [c_lite_v047_policy.md](../c_lite_v047_policy.md)
- `scripts/audit_v047_suite.py`(検出に使用した盲検監査スクリプト)
- 比較対象:[10列制約インシデント記録](v044_ten_column_constraint_incident.md)・
  [ps -ef盲検リーク事例](v043_blindness_incident_ps_ef_leak.md)(過去の同種インシデント、
  同じ「既知リスクの初発現→調査→是正」という扱い方をこのラウンドでも踏襲した)
