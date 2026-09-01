# Epistemic Research Loop 引き継ぎ書

**更新日:** 2026-08-27
**現在の基準:** C-lite v0.3.8 完了(FAIL・全指標改善)/ v0.3.9 実行中
**対象リポジトリ:** `epistemic-research-loop`
**作業ブランチ:** `system/c-lite-v0.3.8`(main 未マージ)

## 1. 現在地

v0.3.7(PR #17、`879812e`)の Engineering Qualification FAIL を受け、同一の Generator・Gate のまま
測定・契約の欠陥だけを直す是正回を実施した。

- **v0.3.8 完了(結論 FAIL、ただし全 Gate 指標が改善し 3 Gate 群が新規 Pass)。**
  介入は 4 点のみ:①24 評価 = 24 個の独立 `claude -p` fresh context(CLI 認証、API key 不使用)、
  ②Null replicate ごとの provenance artifact 契約必須化、③S1/S2 の Lineage 継続を Controller 強制、
  ④P1 単独 Prompt 固定 + C1/C2 を Development Suite のみで fit。
- **v0.3.9 実行中。** 介入は 1 点のみ:終端 resolution の自己整合性契約
  (falsified ⇔ implication>0.05 / 自己 Null 超え research gain の共存、validated ⇔ implication
  不足を Lock 前に差し戻す。Truth 不使用)。Suite `v039-qual-e01..e04`、C1 は v0.3.8 Dev fit を再利用。
- **v0.4 の stash は指示により破棄済み**(`git stash drop` 実行、復元不能)。
- 完全自動ループは `claude -p`(CLI 認証)で実行する方針が確定しており、実際に 54+ run が
  人手ゼロで完走している。

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

1. **v0.3.9 の完走・Lock・開封**(実行中)。予測:TSRR 大幅上昇、persistent 系の matched-negative
   失敗解消。リスク:falsified が inconclusive へ逃げて resolution rate 低下。
2. 残る本質課題は **persistent 系 family の evidence 段階**(46/116)。介入は Prompt へ構造語彙を
   足さずに設計すること(例:cycle 予算・Null 設計の一般的強化)。
3. `useful_encoding_without_structure` への false promotion(8 件)対策は v0.3.9 の
   validated ⇔ implication 契約で部分的に当たる。効果を開封後に確認。
4. Worst FSPR 0.2083 は Gate 0.20 と僅差。agent-02 の false promotion 集中を確認する。
5. 個体 Gate へ十分近づいた段階で **IEEE-CIS 実データの Blind Suite**(`.data/ieee-cis` にデータあり)
   へ移行。解法・構造を Agent へ教えない原則は不変。
6. Container 隔離、Null の独立再実行検証、新 Generator family は Confirmatory 前の必須項目。

## 7. 再現・確認コマンド

```bash
make ci          # 388 tests / coverage 85.28% / ruff / mypy / schema / secret / audit 全 Pass

# v0.3.9 パイプライン(Suite は生成・Lock 済み)
uv run python scripts/run_v039_batch.py --parallel 4      # 再開可能
uv run python scripts/audit_v039_blindness.py
uv run python scripts/lock_v039_agent_runs.py
uv run python scripts/finalize_v039.py                    # 全 24 Lock 後のみ
```

`.runs/` `.state/` `.controller_truth/` は Git ignore 対象。開封済み Suite ID
(`v037-repro-*`, `v038-qual-*`, `v038-dev-*`)は再利用禁止。v0.3.9 Suite は Agent 実行中のため
Truth 開封は 24 run Lock 後のみ。

## 8. 正本文書

- [研究設計](research_basis_and_design_rationale.md)
- [v0.3.8 差分仕様](c_lite_revision_v0.3.8.md) / [Preregistration](v038_preregistration.json)
- [v0.3.8 検証](verification/v038_fresh_context_qualification.md)
- [v0.3.8 Qualification Result](v038_qualification_result.json) /
  [Scorecards](v038_agent_reproducibility_scorecards.json) /
  [Blind Spots](v038_population_blind_spot_report.json) /
  [Failure Traces](v038_structure_failure_traces.json) /
  [Null Audit](v038_full_refit_null_audit.json)
- [v0.3.9 Preregistration](v039_preregistration.json)
- [進捗ログ](progress.md)

## 9. Git 状態

```text
ブランチ  system/c-lite-v0.3.8(main 未マージ、PR 未作成)
main      879812e(= PR #17、v0.3.7)
v0.4      stash はユーザー指示で破棄済み(2026-08-27)
```
