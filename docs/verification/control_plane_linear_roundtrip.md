# 実機検証: ai_dev_control_plane executor ↔ Linear 往復 (SOT-3053)

実施日: 2026-08-24 / 実施者: ai-dev-control-plane solo worker (claude:opus) / 対象 Issue: SOT-3053

推測は書かない。以下はすべて実際に実行したコマンドと、その出力・Linear API の応答・control plane の
ログから確認した事実である。到達しなかった部分は「到達しなかった」と明記する。

## 検証条件

| 項目 | 値 |
| --- | --- |
| 設定 | `configs/competition.example.yaml`（実 ID を投入したもの） |
| run | `sot3053-verify`（competition slug `erl-control-plane-verification`） |
| 実験 | `EXP-3053-roundtrip`（`docs/verification/sot-3053/experiments.json`） |
| executor | `ai_dev_control_plane` / worker `claude:opus` / `target_repo=/workspaces/epistemic-research-loop` |
| `LINEAR_API_KEY` | ai-dev-control-plane 側 `.env` から環境変数として供給（本文・ログ・成果物には出力していない） |
| `ANTHROPIC_API_KEY` | **値が空**のため `erlctl run loop`（完全自動）は実行できず、検証対象から外した |

自動ループを使わず、手動ステップ `init` → `run start` → `hypotheses record` → `experiments propose`
→ `experiments select` → `experiments dispatch` → `experiments import-result` で 1 件を流した。

## 実測 1: `issueSearch` は Linear API で廃止されており、dispatch が必ず失敗していた

`_existing()` が使っていた `issueSearch` クエリは、実 API に対して次を返す。

```
RuntimeError: Linear GraphQL error: deprecated
```

冪等性検索は `submit()` の最初の呼び出しであるため、**この状態では ai_dev_control_plane executor 経由の
dispatch は 1 件も起票できない**（ユニットテストは本文生成しか見ていないため検出できていなかった）。

同一 API キーで代替クエリを実測した結果:

| クエリ | 結果 |
| --- | --- |
| `issueSearch(query:)` | `deprecated` エラー |
| `searchIssues(term:)` | 成功。ただし全文検索のため無関係なイシュー（SOT-3053 本体）も一致した |
| `issues(filter: { description: { contains: } })` | 成功。完全一致の部分文字列フィルタで 0 件を正しく返した |

冪等キーは完全一致で引きたいので、`issues(filter: { description: { contains: $marker } })` を採用した
（`searchIssues` のランク付き曖昧検索では、目的のイシューが `first: 10` から押し出されうる）。取得後に
description へマーカーが含まれることを再確認する後段フィルタは残している。回帰テストは
`tests/integration/test_control_plane_contract.py` に追加した。

## 実測 2: 起票（1 件のみ）

修正後に `erlctl experiments dispatch --run-id sot3053-verify --experiment-id EXP-3053-roundtrip` を実行:

```json
{"adapter": "ai_dev_control_plane", "experiment_id": "EXP-3053-roundtrip",
 "external_ref": "SOT-3054", "idempotency_key": "sot3053-verify:EXP-3053-roundtrip:attempt-1",
 "run_id": "sot3053-verify", "status": "queued"}
```

起票先: **SOT-3054** <https://linear.app/sota-dev/issue/SOT-3054>
（dispatch 前の同一マーカー検索は 0 件、team=Sota / project=ai-dev-control-plane / state=**Todo** で作成）。

起票されたイシュー本文を Linear API から読み直し、control plane のパース規約と突き合わせた結果は 7/7 合格:

| チェック | 結果 |
| --- | --- |
| 1 行目が `workers: solo=claude:opus, handoff=off` | ✅ |
| `TARGET_REPO=/workspaces/epistemic-research-loop` 行がある | ✅ |
| 契約マーカー `<!-- epistemic-research-loop:experiment-request:v1 -->` | ✅ |
| `ERL-IDEMPOTENCY: sot3053-verify:EXP-3053-roundtrip:attempt-1` | ✅ |
| `## 目的` / `## 変更範囲` / `## 実装内容` / `## 検証内容` / `## 受け入れ条件` | ✅ |
| 末尾の `ExperimentRequest` JSON ブロックがパースでき、冪等キーが一致 | ✅ |
| JSON の `command` / `seeds` が dispatch した契約と一致 | ✅ |

## 実測 3: 冪等性（重複起票なし）

同一 `ExperimentRequest`（冪等キー `...:attempt-1`）で `adapter.submit()` を再実行した:

* 戻り値の `external_ref` は **SOT-3054**（新規作成なし、既存を再利用）
* マーカー一致イシュー数は再送後も **1 件**

CLI からの再 dispatch は adapter に届く前にループ状態機械が拒否する（実測: `experiment
EXP-3053-roundtrip is completed and may not be dispatched`, exit 2）。`--attempt 2` は冪等キー自体が
`attempt-2` に変わるため、意図的な再試行として**別チケットになる**（コード上の仕様。実機では新規チケットを
増やさないため実行していない）。

## 実測 4: control plane 側が実際に拾ったこと

ai-dev-control-plane の webhook ログ（`docs/ai/auto_logs/auto_runner.log`）に、この起票が届いていた:

```
16:09:48 [WEBHOOK] Issue event: identifier=SOT-3054 action=create state.name=Todo state.type=unstarted
16:09:48 [WEBHOOK] issue=SOT-3054 validated experiment request run=sot3053-verify experiment=EXP-3053-roundtrip
16:09:48 [QUEUE]   issue=SOT-3054 trigger=webhook enqueued
```

つまり「起票 → webhook 受信 → 実験リクエストとして検証 → 実行キュー投入」までは**実測で到達している**。

**ワーカーによる実行は意図的に行っていない。** SOT-3054 は検証用の合成チケットであり、これを実行させる
ことは意図しない自律 run になるため、上記の確認を終えた作成 25 秒後に Canceled にした。control plane は
これを正しく扱った:

```
16:10:13 [WEBHOOK] issue=SOT-3054 ignored: ... state.name=Canceled reason=terminal state
16:10:13 [QUEUE]   issue=SOT-3054 removed
```

## 実測 5: `ExperimentResult` → `Observation`

ワーカーが書くのと同じ場所・同じスキーマで `result.json` を result store
（`.results/sot3053-verify/EXP-3053-roundtrip/result.json`、内容は `docs/verification/sot-3053/result.json`）
に置き、取り込みを実行した:

```json
{"experiment_id": "EXP-3053-roundtrip", "metrics": {"contract_checks_passed": 7.0, "issues_created": 1.0},
 "observation_id": "OB-ce817a937ee4", "status": "completed"}
```

`erlctl run status --run-id sot3053-verify` は `experiments.completed=1` / `observations=1` /
`state=parsing` / `violations=0` を返した。

**限界（推測で埋めていない点）**: この `result.json` は**ワーカーが実行して書いたものではなく、検証者が
ワーカーの代わりに置いた**。したがって「executor → Linear → webhook → キュー投入」と「result store →
`Observation`」の 2 区間は実測できているが、その間の「ワーカーがチケットを読んで実験を実行し result store
へ書く」区間は本検証では**未実測**である。

## 残る未検証項目

1. ~~ワーカーが実チケットを消化して `result.json` を書く区間~~ → SOT-3055 で実測済み（`worker_experiment_execution.md`）。
2. `erlctl run loop` による完全自動運転（`ANTHROPIC_API_KEY` が空のため実行不能）。
3. `--attempt 2` の再試行が別チケットを作る挙動（実機ではチケットを増やさないため未実施）。
