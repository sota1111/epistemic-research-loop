# Epistemic Research Loop 引き継ぎ書

**更新日:** 2026-08-28
**現在の基準:** v0.3.9 完了(FAIL・TSRR 3.3 倍)/ v0.4.0 Track A 世代 1 完了・修正済み(5 構成が世代 2 進出、codex sol 含む)
**対象リポジトリ:** `epistemic-research-loop`
**作業ブランチ:** `system/c-lite-v0.3.8`(main 未マージ)

## 1. 現在地

v0.3.7 FAIL → v0.3.8(測定是正)→ v0.3.9(契約整合性)→ **v0.4.0(方針転換)** と進行中。

- **v0.3.8 完了(FAIL、全指標改善)。** fresh context / Null provenance / Lineage 強制 / P1 固定。
- **v0.3.9 完了(FAIL、単一介入は予測どおり奏功)。** 終端 resolution 自己整合性契約により
  TSRR 0.1875→0.6250(agent-01 は 0.7083 で個体 Gate 通過)、matched_negative 失敗 27→5、
  FSPR Gate 新規 Pass。開封前の汚染検査で「repair loop による辻褄合わせ」仮説を棄却
  (13 repair 中 12 が実データ再計算、一発 Pass run の TSRR の方が高い)。
  詳細: [verification/v039_terminal_consistency_qualification.md](verification/v039_terminal_consistency_qualification.md)
- **敵対的レビュー(2026-08-28)を実施し、[v0.4.0 方針](c_lite_v040_policy.md) へ転換。**
  Gate 数値の逐次改善を止め、「発見に至るエージェント構成の発生」(P1)と「IEEE-CIS 橋」(P2)を
  Primary に再定義。目標モデル=あるべき姿の 8 能力柱(重心は柱 2 構造仮説生成・柱 3 識別実験設計)。
- **v0.4.0 Track A 世代 1 完了・修正済み。** 6 構成(fable-5×P1 / fable-5×P2 / opus-5×P1 基準線 /
  sonnet-5×P2 / codex sol×P1 / codex terra×P1)× 4 replicate = 24 run。当初 1 replicate
  (codex sol、g04)をコンテナの user namespace 遮断による codex sandbox 障害で除外・23 run で
  一度確定・開封したが、**ユーザー指摘を受けた session ログのフォレンジックで、この障害が
  除外した 1 run に限らず codex 8 スロット全体に断続的な計算阻害を与えていたと判明**
  (最終採用 attempt でもコマンド失敗率 38–45%・完走コマンド数わずか 8–17 件の重度汚染が
  4 スロット)。原因(bwrap 依存の `workspace-write` サンドボックスがこのコンテナで恒久的に
  機能しない)を `-s danger-full-access` への切替で修正し、reasoning effort の明示固定も併せて
  行った上で codex 8 スロット全て(除外していた分を含む)を再実行、**24/24 で再確定・再開封**。
  **codex sol の成績が発見イベント 1→4 件へ改善し世代 2 進出候補に浮上、terra も 0→2 件で
  閾値を通過**——「codex は終端解決を回避する」という当初の解釈は主として環境障害由来だった。
  世代 2 進出候補は **opus-5×P1(7)・fable-5×P2(5)・codex sol×P1(4)**。structure-grammar
  family(machine-composed・未知構造)での発見(7/24・12/24)は claude・codex 双方の上位構成で
  再現し CLI 非依存と確認。persistent ラダー L1–L3 は 0/24 のまま(v0.3.9: 7・1・5/24)——
  sandbox 修正後も codex 側で 0 件のため CLI 非依存の現象と判明し、implication provenance 契約が
  新しい contract-lever ボトルネックになっている疑いが強まった。旧(汚染)データは
  `.runs/v040/agent_outputs_pre_sandboxfix_backup/`(未 commit)に保全。
  詳細: [verification/v040_gen1_track_a_qualification.md](verification/v040_gen1_track_a_qualification.md)
- **v0.4 の旧 stash は指示により破棄済み**(復元不能)。
- 完全自動ループは `claude -p` / `codex exec`(CLI 認証、API key 不使用)で実行。
  累計 104 run(v0.3.8 24 + v0.3.9 24 + v0.4.0 世代 1 実行 24 + codex 8 スロット再実行)が
  人手ゼロで完走。

## 2. 最重要結果(v0.3.8)

| 指標 | v0.3.7 | v0.3.8 | Gate | 判定 |
| --- | ---: | ---: | ---: | --- |
| Median Agent TSDR | 0.0833 | 0.1875 | >= 0.50 | Fail |
| Median Agent TSRR | 0.0208 | 0.1875 | >= 0.67 | Fail |
| Worst Agent FSPR | 0.3333 | 0.2083 | <= 0.20 | Fail(僅差) |
| Shared Blind-spot Rate | 0.7917 | 0.7083 | <= 0.20 | Fail |
| Minimum LOAO TSRR | 0.0000 | 0.0000 | >= 0.67 | Fail |
| Pooled USTR | 0.7500 | 1.0000 | >= 0.50 | Pass |
| Median Structure Gain | +0.0943 | +0.2209 | > 0 | Pass |
| Median Structure Brier | 0.2614 | 0.1813 | <= 0.20 | Pass(新規) |
| Median Structure ECE | 0.1826 | 0.1055 | <= 0.20 | Pass |
| Persistent Ladder | 1/4 levels, 1/3 agents | 4/4, 2/3 | 3/4, 2/3 | Pass(新規) |

構造 family 別の個体発見(24 反復中):

```text
observation_routing_composition  23/24   ほぼ完全(v0.3.7: 7/24)
persistent_clear                  2/24   (matched_negative 段階の失敗が別途 12)
persistent_noisy_proxy            1/24
persistent_delayed_history        1/24
persistent_compositional          1/24
stable_structure_nonactionable    1/24
```

**ボトルネックの特定:** 負例 144 件中 122 件が `falsified` 申告なのに Evidence-based 棄却は 27 件。
阻止 95 件のうち 73 件は「falsified と主張しながら同じ提出物の independent implication strength が
2 Context 以上で 0.05 超」という**自己矛盾**であり、証拠不足ではない。persistent_clear の
matched-negative 失敗 12 件も同経路。これが v0.3.9 の唯一の介入対象である。

False promotion 15 件のうち 8 件は `useful_encoding_without_structure`(予測利得あり・構造なし)への
昇格で、「予測利得 ≠ 構造」の罠が残る。v0.3.7 の「agent-01 だけが寄与」の偏りは解消し、
Rejection Complementarity 0.021→0.125、population union TSRR 0.083→0.458。

## 3. 実装マップ(v0.3.8 / v0.3.9 追加分)

### Benchmark

- `src/epistemic_loop/benchmark/v038_repro_suite.py` — 新 Suite ID(qual c01..c04 / dev d01..d02)、
  P1 単独、Lineage 3 policy の均衡回転、`build_versioned_suite()`(以後の版が再利用する共有 Builder)
- `src/epistemic_loop/benchmark/v039_repro_suite.py` — `v039-qual-e01..e04`、master seed 20260903

### Agent Contract

- `src/epistemic_loop/controller/v038_agent.py` — Null provenance(replicate ごとの
  permutation/feature/fold/model/OOF hash + preserved statistics、件数・gain 整合・一意性検証)、
  Lineage 継続検証(S1/S2 で open lineage 放棄を拒否)、Failure stage A–C の Controller 判定
- `src/epistemic_loop/controller/v039_agent.py` — 終端 resolution 自己整合性検証

### Execution(fresh `claude -p` ランナー)

- `scripts/run_v038_agent.py` / `run_v039_agent.py` — 1 run = 1 fresh `claude -p`。隔離 workdir
  (`~/erl-v03x-runs/`)、deny rule(リポジトリ/Truth/network)、stream transcript 保存、
  契約 repair retry(最大 3、validation error のみフィードバック)、BLAS 2 thread 固定
- `scripts/run_v038_batch.py` / `run_v039_batch.py` — 並列実行(完了分スキップで再開可能)

### Pipeline

- `scripts/build_v038_suites.py` / `build_v039_suites.py`(一括生成・Lock)
- `scripts/lock_v038_agent_runs.py`(--group development|qualification)/ `lock_v039_agent_runs.py`
- `scripts/fit_v038_calibration.py`(Dev truth のみで C1/C2、Lock)
- `scripts/audit_v038_blindness.py` / `audit_v039_blindness.py`(view + transcript 監査)
- `scripts/finalize_v038.py` / `finalize_v039.py`(Lock 照合 → 開封 → docs 出力)

### Evaluation

- `src/epistemic_loop/evaluation/v038.py` — v0.3.7 評価器を verbatim 再利用 + Provenance 監査、
  Controller 判定 A–C、Suite×Seed cluster bootstrap、C1 適用、operator Jaccard。v0.3.9 も同じ評価器。

### Tests

- `tests/unit/test_v038_repro_suite.py` / `test_v038_agent_contract.py` / `test_v038_evaluation.py`
- `tests/unit/test_v039_contract.py`

## 4. 運用で判明した落とし穴(新規)

v0.3.7 の評価 7 項目(旧引き継ぎ書 §5)に加えて:

1. **`uv run` 経由でランナーを起動すると repo venv が PATH に入り、Agent の `python3` が
   venv interpreter を解決する。** データ・Truth への情報流はないが、numpy 警告が venv パスを
   stderr へ出し transcript 監査に hit する。監査側で `<interpreter-site-packages>` として
   allow-list 済み(実 path 言及は引き続き Fail)。interpreter 隔離は Container 隔離と併せて未了。
2. **アカウントのセッション使用上限(HTTP 429)で並列バッチが途中失敗する。** バッチは完了分
   スキップの再開可能設計。上限リセット後に同じコマンドを再実行すればよい。中断 run の workdir
   には部分成果物が残るが、新 fresh context がそのまま完走できる(文脈の持ち越しはない)。
3. **`claude -p` は `--dangerously-skip-permissions` + settings deny rule で運用。** deny は
   bypass でも強制される。ネットワークは WebFetch/WebSearch/curl/wget/git を deny。
4. 契約 repair feedback には Truth 情報を含めないこと(validation error 文字列のみ)。

## 5. 既知の制約

1. **Null provenance は Agent 計算値の構造監査**(件数・gain 整合・hash 一意性)であり、独立
   再実行検証ではない。「検証済み Full-refit」とは表現しない。
2. **Container / mount / namespace 隔離は未実装。** workdir 隔離 + deny rule + 暗号化 Truth +
   transcript 監査まで。Confirmatory claim には Container 隔離が必要。
3. **v0.3.9 の C1 は v0.3.8 Dev fit の再利用**(Preregistration 明記)。整合性契約が確信度分布を
   シフトさせる可能性があるため、calibrated 指標は secondary 扱い。
4. Wilson / cluster bootstrap とも Engineering 用記述値。
5. Synthetic Generator 系統内の評価であり、IEEE-CIS 等 Real Benchmark 一般化は未測定。
6. Communication M0–M4 は個体 Gate 通過まで封印(方針維持)。

## 6. 次の推奨作業

1. **v0.4.0 Track A 世代 2。** 上位候補(C3 opus-5×P1 baseline・C2 fable-5×P2・**C5 codex sol×P1**、
   tie-break 次第で C1 fable-5×P1 も検討)を新規生成した別 Suite インスタンス(新 master seed、
   選抜に使った Suite は再利用しない)で各 6–8 run 再現確認する(policy §3.2)。terra(C6)は
   false promotion 5 件(1 replicate 集中)を再現するか要観察——世代 2 で再現しなければ単発の
   暴走と判断してよい。世代 2 を通過した構成のみ P1 判定(独立 2 run 再現)へ。
2. **persistent L1–L3(clear/noisy_proxy/delayed_history)の 0/24 退行を transcript 差分診断で
   切り分ける**(policy §3.3、構造語彙を足さない範囲)。sandbox 修正後のデータで **CLI 非依存
   (claude・codex とも 0 件)と判明した**ため、implication provenance 契約(0.95 null 位置)が
   新しい contract-lever ボトルネックになっている疑いが強まった。世代 2 の新 Suite で再現するか
   どうかが最初の切り分け材料になる。
3. **codex sol の reasoning-effort ablation を独立 side-probe として実行**(low/medium/high/xhigh
   × 3 replicate、新 Suite、P1 固定、v0.4.0 の deferred_to_generation_2 に記載済み)。単に
   discovery event 数だけでなく、semantic_family_count・effective_family_count・eecr・
   deep_lineage_completion_rate 等の多様性指標も水準ごとに追跡し、「effort が高いほど良い」という
   単調仮定を置かずに非単調な関係(発見率は上がるが多様性は下がる、等)の有無を検証する。
   **必ず `-s danger-full-access` と `-c model_reasoning_effort` 明示指定を使うこと**
   (`scripts/run_v040_agent.py` で修正済み、`~/.codex/config.toml` の既定値には依存しない)。
4. GLM(zai CLI、`/home/vscode/.local/bin/glm`)は API key 導入済みだが利用制限中(2026-08-28
   19:35:52 UTC 頃解除見込み)。`zai` は OS レベルのサンドボックス機構を一切持たない(ソース確認済み、
   `path.resolve()` のみで作業ディレクトリ外への読み書きを防がない)ため、隔離は claude/codex 同様
   workdir コピー+prompt 指示+transcript 監査のみに依存する設計とすること。制限解除後、まず
   isolated scratch directory での smoke test(認証・出力形式・tool 実行確認)を先に行う。
4. 世代 2 で >= 2 verified discovery event を再現する構成が出れば Track B(IEEE-CIS 橋、policy §4)
   へ。皆無なら停止規則 1 が発動し、最良構成のまま Track B へ進む(合成完璧主義を避ける)。
5. Container 隔離、Null の独立再実行検証は Confirmatory 前の必須項目のまま。
6. GLM-5.3・Kimi K3 等の追加モデル系統は世代 2 の preregistration 時点で候補プールに加える判断
   ポイント(世代途中のモデル変更はしない)。導入前提:CLI 経路の確保・認証方針(API key 例外の
   preregistration への明記)・claude/codex 相当の隔離パリティ・1 run のパイロット疎通確認。

## 7. 再現・確認コマンド

```bash
make ci          # ruff / mypy / schema / secret / audit 全 Pass(tests は都度件数変動)

# v0.4.0 Track A 世代 2(新 Suite ID を preregister してから)
uv run python scripts/build_v040_suites.py --suite-ids <gen2 suite ids>
uv run python scripts/run_v040_batch.py --parallel 3       # 再開可能。V040_GEN1_EXCLUDED_RUNS は
                                                             # スロット単位の preregistered 除外
uv run python scripts/audit_v040_blindness.py
uv run python scripts/lock_v040_agent_runs.py
uv run python scripts/finalize_v040.py                     # 実行対象全 run が Lock 済みの場合のみ
```

`.runs/` `.state/` `.controller_truth/` は Git ignore 対象。開封済み Suite ID
(`v037-repro-*`, `v038-qual-*`, `v038-dev-*`, `v039-qual-*`, `v040-genA-*`)は再利用禁止。
世代 2 は新規 suite id・新規 master seed で preregister すること(方針§3.2:世代間でのメタ過適合
防止)。`evaluate_v037_runs`/`evaluate_v038_runs` は preregistered 除外を扱うための
`excluded_pairs` 引数(デフォルト空集合)を持つ——インフラ障害等で run が実行不能になった場合は
開封前にこの引数へ追加し、preregistration に deviation エントリを残すこと。

## 8. 正本文書

- [研究設計](research_basis_and_design_rationale.md)
- [v0.3.8 差分仕様](c_lite_revision_v0.3.8.md) / [Preregistration](v038_preregistration.json)
- [v0.3.8 検証](verification/v038_fresh_context_qualification.md)
- [v0.3.8 Qualification Result](v038_qualification_result.json) /
  [Scorecards](v038_agent_reproducibility_scorecards.json) /
  [Blind Spots](v038_population_blind_spot_report.json) /
  [Failure Traces](v038_structure_failure_traces.json) /
  [Null Audit](v038_full_refit_null_audit.json)
- [v0.3.9 Preregistration](v039_preregistration.json) /
  [v0.3.9 検証](verification/v039_terminal_consistency_qualification.md)
- [v0.4.0 方針](c_lite_v040_policy.md) / [v0.4.0 世代 1 Preregistration](v040_gen1_preregistration.json)
- [v0.4.0 世代 1 検証](verification/v040_gen1_track_a_qualification.md) /
  [Selection Table](v040_gen1_selection.json) / [Diagnostics](v040_gen1_diagnostics.json)
- [進捗ログ](progress.md)

## 9. Git 状態

```text
ブランチ  system/c-lite-v0.3.8(main 未マージ、PR 未作成)
main      879812e(= PR #17、v0.3.7)
v0.4      stash はユーザー指示で破棄済み(2026-08-27)
```
