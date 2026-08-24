# 実機検証: ワーカーが実チケットを消化して result store に書く区間 (SOT-3055)

実施日: 2026-08-24 / 実施者: ai-dev-control-plane solo worker (claude:opus) / 対象 Issue: SOT-3055

`control_plane_linear_roundtrip.md`（SOT-3053）で **未実測** として残していた区間、すなわち
「ワーカーがチケットを読んで事前登録実験を実行し、`ExperimentResult` を result store へ書く」を、
合成チケットではなく**研究ループ自身が起票した実チケット**で実測した記録である。推測は書かない。
到達しなかった部分は「到達しなかった」と明記する。

## 検証条件

| 項目 | 値 |
| --- | --- |
| run | `erl-live-001`（competition slug `synthetic-shift`） |
| 実験 | `E-SPLIT-001`（仮説 `H-VALIDATION-001` / diagnostic） |
| チケット | SOT-3055（`AiDevControlPlaneAdapter` が起票、`workers: solo=claude:opus`） |
| 冪等キー | `erl-live-001:E-SPLIT-001:attempt-1` |
| 実行契約 | チケット本文の機械可読 JSON をそのまま `ExperimentRequest` として検証・使用 |
| result store | `.results/erl-live-001/E-SPLIT-001/`（`executor.result_root=.results`） |

## 実測 1: 事前登録物を一切変更していないこと

* 実行したコマンドは契約どおりの `python3 examples/local_mock/run_experiment.py`。
* 契約の `base_commit_sha` は `4831900`、実行した作業ツリーは `cf4d834`（`main`）。両者で
  実行対象スクリプトが同一であることを確認した:

  ```
  $ git diff 483190062e07041d3f5fcafe294c9d4ccfe9478f..HEAD -- examples/local_mock/run_experiment.py
  (差分なし)
  ```

  `4831900..cf4d834` の差分は Linear アダプタ・テスト・ドキュメントのみで、実験の予測・判定規則・
  シード・split には触れていない。
* `E-SPLIT-001` の `predicted_outcomes` / `decision_rule` / `seeds` / `split_strategy` と
  `examples/local_mock/run_experiment.py` は本検証で編集していない（`git status` 上も未変更）。

## 実測 2: 実行

リポジトリ自身の実行経路（`LocalExecutor`）に契約を渡して実行した。これにより `ERL_OUTPUT_DIR`、
result store のレイアウト、`ExperimentResult` のスキーマが repo の定義そのものになる。

```
status=completed  exit_code=0  failure_class=null  wall_seconds=0.0230
```

`ERL_OUTPUT_DIR` に出力されたファイル:

| ファイル | 内容 |
| --- | --- |
| `metrics.json` | `{"score": 0.75}`（必須成果物） |
| `fold_metrics.json` | `{"folds": [0.74, 0.76]}`（必須成果物） |
| `predictions.parquet` | 16 bytes（モックスクリプトが書く付随物） |
| `run_manifest.json` | `{"mock": true}`（同上） |
| `stdout.log` / `stderr.log` | いずれも 0 bytes |
| `result.json` | `ExperimentResult`（下記） |

`result.json` の写しは `docs/verification/sot-3055/result.json`、必須成果物の写しは同ディレクトリの
`metrics.json` / `fold_metrics.json` に置いた。`external_ref` には実行元チケット `SOT-3055` を
記録している（研究ループ側から実行を辿れる唯一のハンドルであるため）。

## 実測 3: 実行環境と、宣言との差分

宣言どおりに再現できなかった点は隠さず記録する。いずれも着手前に判明し、Linear に明示したうえで
安全な既定で続行した。

| 契約 | 実際 | 根拠 |
| --- | --- | --- |
| `container_image: python:3.11-slim` | コンテナ不使用。`.venv/bin/python3` = **CPython 3.11.15** を `python3` として解決 | 本 DevContainer に `docker` が存在しない（`command -v docker` → 不在）。宣言と同じ 3.11 系を使用した |
| `network_policy: disabled` | カーネルによるネットワーク分離は**不可**。コマンドが外部通信を持たないことを静的検査で担保 | `unshare -rn true` → `Operation not permitted`。実行スクリプトは標準ライブラリのみ・ファイル書き出しのみ |
| `dataset_mounts: [competition-data]` | 実体化せず | 宣言コマンドはデータを読まない（`ERL_OUTPUT_DIR` へ書くだけ） |
| `seeds: [101, 202]` | 宣言コマンドを 1 回実行 | `LocalExecutor` はシードを環境変数として渡さず、契約もシード別実行を定義していない。シードは事前登録の記録として `ExperimentRequest` に保持される |
| `resources.timeout_seconds: 3600` | 0.023 秒で完了 | タイムアウト到達なし |

`dataset_fingerprint` は `LocalExecutor` が返す `local-executor-unverified` のまま。データを読まない
実験であり、フィンガープリントを検証していないという事実をそのまま残している。

## 実測 4: 品質ゲート（対象リポジトリ）

本検証で `src/` は変更していないが、実行環境が健全であることを確認するため実行した。

専用 worktree（本ブランチの変更のみを含む作業ツリー）で実行した。

| ゲート | 結果 |
| --- | --- |
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 143 files already formatted |
| `uv run mypy` | Success: no issues found in 91 source files |
| `uv run pytest --cov` | 88 passed / coverage 93.09%（閾値 85%） |
| `scripts/export_schemas.py` + `git diff --exit-code -- schemas` | 差分なし |
| `scripts/secret_scan.py` | Secret scan passed: 0 findings |

## 残る未検証項目（更新）

1. ~~ワーカーが実チケットを消化して `result.json` を書く区間~~ → **本検証で実測済み**。
2. `erlctl run loop` による完全自動運転（`ANTHROPIC_API_KEY` が空のため実行不能）。
3. `--attempt 2` の再試行が別チケットを作る挙動（実機ではチケットを増やさないため未実施）。
4. **本検証でも未到達**: result store からの `experiments import-result`（= `Observation` 生成と
   run 状態の `executing` → `parsing` 遷移）は**研究ループ側の責務**であり、ワーカーは実行していない。
   `erl-live-001` は本検証終了時点で `executing` のままである。SOT-3053 の実測 5 で、同じ場所・
   同じスキーマの `result.json` からの取り込みが成立することは既に確認済み。
5. コンテナ隔離・ネットワーク遮断・データセットマウントを宣言どおり強制する実行基盤（上表の差分）。

## 付随観測（実行環境）

検証中、同一作業ツリー `/workspaces/epistemic-research-loop` に本ワーカー以外の書き込みが並行して
発生していた（`src/epistemic_loop/domain/validation.py` の変更と、`controller/phase_evidence.py` /
`holdout/adaptivity.py` の新規追加。いずれも本ワーカーの成果物ではない）。混入を避けるため、本検証の
コミットは専用の `git worktree` で行い、共有作業ツリーは `main` に戻して未コミットの変更をそのまま
残している。
