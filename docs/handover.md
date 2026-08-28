# Epistemic Research Loop 引き継ぎ書

**更新日:** 2026-08-28
**現在の基準:** v0.3.9 完了(FAIL・TSRR 3.3 倍)/ v0.4.0 Track A 世代 1 完了(3 構成が世代 2 進出)
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
- **v0.4.0 Track A 世代 1 完了。** 6 構成(fable-5×P1 / fable-5×P2 / opus-5×P1 基準線 /
  sonnet-5×P2 / codex sol×P1 / codex terra×P1)× 4 replicate を preregistration。うち 1 replicate
  (codex sol、g04)はコンテナの user namespace 遮断による codex sandbox 恒久障害のため開封前に
  preregistration deviation として除外し、23 run で確定・開封。**発見イベント数で 3 構成
  (opus-5×P1=7、fable-5×P2=5、fable-5×P1=2)が世代 2 進出の閾値(>=2)を通過。**
  structure-grammar family(machine-composed・未知構造)での発見が実際に発生(5/23・9/23)した
  一方、persistent ラダー L1–L3 は 0/23 に退行(v0.3.9: 7・1・5/24)——新設の implication
  provenance 契約が新しい contract-lever ボトルネックになっている可能性を含め未解明。
  詳細: [verification/v040_gen1_track_a_qualification.md](verification/v040_gen1_track_a_qualification.md)
- **v0.4 の旧 stash は指示により破棄済み**(復元不能)。
- 完全自動ループは `claude -p` / `codex exec`(CLI 認証、API key 不使用)で実行。
  累計 101 run(v0.3.8 24 + v0.3.9 24 + v0.4.0 世代 1 実行 24・評価対象 23)が人手ゼロで完走。

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

1. **v0.4.0 Track A 世代 2。** 上位 3 構成(C1 fable-5×P1・C2 fable-5×P2・C3 opus-5×P1 baseline)を
   新規生成した別 Suite インスタンス(新 master seed、選抜に使った Suite は再利用しない)で
   各 6–8 run 再現確認する(policy §3.2)。世代 2 を通過した構成のみ P1 判定(独立 2 run 再現)へ。
2. **persistent L1–L3(clear/noisy_proxy/delayed_history)の 0/23 退行を transcript 差分診断で
   切り分ける**(policy §3.3、構造語彙を足さない範囲)。候補要因:(a) implication provenance
   契約(0.95 null 位置)自体が新しい contract-lever ボトルネックになっている、(b) Suite 内の
   attention 配分が grammar-composed family 追加で変化した、(c) この世代の master seed 固有の
   難度。世代 2 の新 Suite で再現するかどうかが最初の切り分け材料になる。
3. codex(sol/terra)の終端解決回避パターンの定量化は継続。terra は世代 1 で 4 replicate 24 pack
   全てが非終端。世代 2 では reasoning-effort ablation(sol/terra/luna 内の水準違い)を候補に含める
   かを検討(v0.4.0 の deferred_to_generation_2 に記載済み)。
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
