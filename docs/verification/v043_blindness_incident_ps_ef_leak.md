# 盲検リーク事例:`ps -ef` 経由のプロセス可視性リーク(2026-08-30)

**分類:** blindness incident report。[v0.4.3 方針](../c_lite_v043_policy.md) §7(不変条件)
に新規追加する教訓。

## 発見の経緯

`v042-mc-d02`(Santander sol-effort round2)の agent 出力を `scripts/audit_v042_blindness.py`
で監査した際、`agent-01-s217`(config `SD-low-P1`)の transcript に文字列 `santander` が
1回出現していることを検出した(`view_findings` は空——エージェント自身の可視ファイル
(`agent_packet.json`・prompt・データファイル)には一切含まれていなかった)。

## 根本原因

当該エージェントは作業中に `ps -ef | rg 'python3|PACK'` を実行し、**システム全体の
プロセス一覧**を取得していた。この出力には、当該エージェントのサンドボックス外で動作する
**バッチオーケストレータ自身のコマンドライン**が含まれていた:

```
python3 scripts/run_v042_batch.py --suite-id v042-mc-d02 --config-set sol-effort-r2-santander --parallel 4
```

このセッションで `--config-set` の値として `sol-effort-r2-santander`(コンペ名を含む
opaque でない文字列)を選んだことが直接の原因——`suite_id`(`v042-mc-d02`)自体は
既存の opaque 命名規則に従っていたが、**バッチオーケストレータ自身の起動引数**は
その規則の対象外になっていた。

## 重要な教訓:サンドボックス分離はプロセス一覧に対しては機能しない

このプロジェクトはこれまで「エージェントの可視ファイル」と「transcript(自身の
実行ログ)」の2面を監査してきたが、**エージェントが `ps -ef` 等でホスト上の他プロセス
(オーケストレータ・兄弟エージェントプロセス)のコマンドラインを観測できる**という
第3の露出経路がある。codex サンドボックス(`-s danger-full-access`、この container の
bwrap 依存関係が壊れているための代替設定、`scripts/run_v040_agent.py` 冒頭のコメント
参照)はファイルシステムを完全に分離しないため、プロセス空間も同様にホスト全体が
見えている可能性が高い。

**影響範囲の確認:** このセッションで実行した他の全 sol-effort バッチ(round1: `c01`・
`c02`、round2: `d01`)の transcript を再確認したが、`ps -ef`/`run_v042_batch.py` の
文字列を含む transcript は今回の1件のみだった——つまり `d01`(IEEE-CIS round2、
config-set 値 `sol-effort-r2-ieee-cis` も同様にコンペ名を含んでいた)は**構造的には
同じ脆弱性に晒されていたが、たまたまどのエージェントも `ps -ef` 相当のコマンドを
実行しなかったため露見しなかった**——「audit がクリーンだった」ことは「安全だった」
ことを意味しない、という点を明記する。

## 対応

1. `--config-set` の全選択肢をコンペ名を含まない opaque な値に改名した:
   `sol-effort-r2-ieee-cis` → `sol-effort-r2-a`、`sol-effort-r2-santander` →
   `sol-effort-r2-b`(`scripts/build_v042_suite.py`・`lock_v042_suite_runs.py`・
   `finalize_v042_suite.py`・`run_v042_batch.py`・`audit_v042_blindness.py` の5ファイル)。
2. 汚染された1 run(`v042-mc-d02/agent-01-s217`、config `SD-low-P1`)の出力を削除し、
   修正後のオーケストレータで再実行した。
3. **新しい不変条件として明文化(以後の全ラウンドに適用):** suite_id だけでなく、
   **エージェントバッチを起動するあらゆるコマンドの引数・環境変数もコンペ名や
   データセット識別子を含んではならない**——エージェントは自身のサンドボックス外の
   プロセス一覧を観測できる可能性を常に想定すること。

## この1 run の科学的な扱い

汚染が確認された `agent-01-s217`(オリジナル実行)の discovery 内容は、混入した情報が
「santander」という単語1回のみで、実際の技術的発見(claim・technique）に影響した形跡は
transcript 上確認できなかったが、本プロジェクトの保守的な blindness 原則(いかなる漏洩も
汚染として扱う——[v041 Track B の suite_id 漏洩事例](v041_track_b_qualification.md)と同じ
基準)に従い、この run のオリジナル出力は正式な分析対象から除外し、修正済みオーケストレータ
による再実行の結果のみを正本とする。

## 正本

- [Santander sol-effort 多様性ラウンド](v043_sol_effort_diversity_santander.md)
- [v0.4.3 方針§7(不変条件)](../c_lite_v043_policy.md)
