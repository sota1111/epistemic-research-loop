# Epistemic Research Loop 引き継ぎ書

**更新日:** 2026-08-29
**現在の基準:** v0.4.0 Track A 世代 1 完了・修正済み/ sol reasoning-effort ablation 完了/
scaffold-ladder Stage 1・Stage 2 完了(**persistent ラダー全 4 段階が history 上初めて破られた**)/
cycle-budget ablation 準備完了・起動待ち
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
- **codex sol reasoning-effort ablation 完了。** low/medium/high/xhigh × 6 replicate = 24 run
  (CLI/model/prompt-arm は世代 1 の C5 と同一、effort のみ変える単一介入設計。新 Suite
  `v040-solE-b01..b06`)。当初 replicate=4 は統計的根拠のない選択だったとユーザー指摘を受け
  6(policy §3.2 の下限)へ修正し、`evaluate_v037_runs`/`evaluate_v038_runs` に
  `expected_suite_count` 引数を追加(既存呼び出しは無変更)。**結果は narrowing 仮説を明確に
  棄却し capacity 仮説を支持:発見イベント low 2→medium 3→high 4→xhigh **7** と単調増加、
  diversity 指標(semantic_family_count 等)も同方向に単調増加(トレードオフなし)。
  さらに `persistent_clear` が high・xhigh でのみ計 2 件、history 上初めて真に発見された**
  (gen1・scaffold-ladder では 0 件のまま)——persistent ラダーの壁が evidentiary capacity
  (held-out 証拠を 0.95 閾値まで積む能力)の問題であるという仮説を支持する最初の肯定的証拠。
  世代 2 の codex sol 構成には xhigh を採用する根拠が得られた。
  詳細: [verification/v040_sol_effort_ablation_qualification.md](verification/v040_sol_effort_ablation_qualification.md)
- **Opus + Sol scaffold-ladder screen(Stage 1)完了。** 「Opus と Sol だけで解法の多様性・
  未知構造発見に到達できる構造」を第一優先課題とする方針のもと、P1(baseline)/ P2(仮説列挙強制)/
  P3(新規:昇格前の自己批判 cycle、既存 cycle 予算内)を opus・sol に交差させた 6 構成 × 4 replicate
  = 24 run(新 Suite `v040-scaf-c01..c04`)。**P3 が opus の仮説多様性(semantic_family_count)を
  4 replicate 全てで再現性高く約 3 倍(3.00→8.75)に押し上げ、false promotion は 0 のまま。**
  **claude 側で初めて persistent 系が真に発見された**(opus×P1:persistent_clear +
  persistent_compositional 同時発見、opus×P3:persistent_noisy_proxy)。**P2 は opus には
  効かなかった**(発見イベント P1=P3=9 > P2=7)——scaffold の効果はモデル依存と判明(事前登録した
  3 通りの予測のうち「モデル依存」が支持された)。sol×P3 の false promotion 7 件は単一 suite に
  集中する単発の暴走(terra/g03、sol ablation high/b05 と同型)。
  詳細: [verification/v040_scaffold_ladder_qualification.md](verification/v040_scaffold_ladder_qualification.md)
  Preregistration: [v040_scaffold_ladder_preregistration.json](v040_scaffold_ladder_preregistration.json)
  新規プロンプト: [v040_p3.md](../prompts/generic_research_agent/v040_p3.md)
- **Stage 2(確認世代、opus×P1・opus×P3・sol×P3×xhigh、各 6 replicate = 18 run)完了。**
  **`persistent_delayed_history`(累積発見台帳で 88 run を通じて 0 件だった唯一の family)が
  opus×P1・opus×P3 の両方で史上初めて真に発見された。** これで **persistent ラダー全 4 段階が
  少なくとも一度は破られた。** opus×P3 は同一 6 replicate 内で persistent_clear も発見(1 構成
  2 family 同時発見は初)。sol×P3 の false promotion は Stage 1 の 7 件→**0/36 に消失**(単発の
  暴走だったと確認)。一方 **opus×P3 の多様性ブーストは 8.75→4.33 に縮小**——n=4 のスクリーニング
  推定値は効果量を過大評価していたことが判明(方向は再現、規模は再現せず)。
  開封時に評価器の潜在バグ(`agent_seed_aggregates` が agent×seed の全直積を仮定しゼロ除算)を
  発見・修正——既存 3 study(gen1・Stage1・sol ablation)で再実行し bit-for-bit 完全一致を実測
  確認した上で適用。
  詳細: [verification/v040_scaffold_ladder_stage2_qualification.md](verification/v040_scaffold_ladder_stage2_qualification.md)
  累積発見台帳: [v040_discovery_ledger.md](v040_discovery_ledger.md)
- **cycle-budget ablation(4→8 cycle、opus×P1×cycle8・sol×P1×xhigh×cycle8、各 6 replicate =
  12 run)を preregister・suite build 済み、実行待ち。** `MAX_CYCLES_PER_PACK` を 4→8 に拡張
  (`src/epistemic_loop/controller/v037_agent.py`、後方互換——既存 395 test 全通過確認済み)。
  新プロンプト [v040_p1_c8.md](../prompts/generic_research_agent/v040_p1_c8.md)(P1 の「four」を
  「eight」に変えただけの単一差分)。cycle=4 の baseline は既存 study(gen1+Stage1 の opus×P1、
  sol ablation の xhigh)を再利用し、cycle=8 のみ新規実行。
  Preregistration: [v040_cycle_budget_ablation_preregistration.json](v040_cycle_budget_ablation_preregistration.json)
- **GLM(zai CLI)を runner に統合・smoke test 済み。** `/home/vscode/.local/bin/glm`
  (`ZAI_MODEL=glm-5.3` 既定、`.env` の `GLM_API_KEY` を自前で source)。ソース確認の結果、
  **OS レベルのサンドボックスが一切ない**(`text-editor.js` は `path.resolve()` のみで
  ディレクトリ外読み書きを防がない)ため、隔離は claude/codex 同様 workdir コピー + prompt 指示 +
  transcript 監査のみに依存する設計とした。`-p` headless モードは全 tool 操作を自動承認済み
  (`confirmationService.setSessionFlag("allOperations", true)`)。restricted env
  (`_environment()`と同一)下での smoke test で認証・ファイル書き込み・bash 実行・JSONL
  transcript 出力を確認済み。`scripts/run_v040_agent.py` の `_command()` に `cli: "glm"` 分岐を
  追加済み。**ただし実際の Suite・replicate 数を伴う正式な study はまだ preregister していない**
  ——導入は完了したが、どの世代・どの config 数で投入するかは次の preregistration 時点で決める。
- **v0.4 の旧 stash は指示により破棄済み**(復元不能)。
- 完全自動ループは `claude -p` / `codex exec` / `glm -p`(いずれも CLI/wrapper 認証、provider
  API key を agent プロセス環境には渡さない)で実行。累計 104+ run
  (v0.3.8 24 + v0.3.9 24 + v0.4.0 世代 1 実行 24 + codex 8 スロット再実行 + sol ablation 16)が
  人手ゼロで完走(ablation は実行中)。

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
5. **この devcontainer の作業ディレクトリは複数セッション/タスクで共有されている。**
   2026-08-28、無関係な別セッションが同じ working directory で `git checkout`/commit/PR
   マージ/`git pull` を実行し、このセッションの HEAD を無警告で `main`(v0.4.0 作業を一切
   含まない)へ移動させた。バックグラウンドバッチが新しい subprocess を起動する直前に発覚・
   復旧(`git checkout system/c-lite-v0.3.8`)。commit 自体は失われない(branch ref は残る)が、
   **長時間バックグラウンド実行中は定期的に `git branch --show-current` を確認すること。**

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

1. **Stage 2(scaffold-ladder 確認世代)を起動する。** Stage 1 の結論(opus×P3 が多様性で圧倒、
   opus×P1 と同点最高発見、sol は xhigh 固定が最良)を policy §3.2 の推奨 replicate(6)で
   新 Suite に対して再現確認する。特に (a) opus×P3 の semantic_family_count 3 倍化が再現するか、
   (b) sol×P3 の false promotion 7 件(単一 suite 集中)が繰り返すか、(c) persistent 系発見
   (opus×P1/P3 で計 3 件、sol ablation の high/xhigh で計 2 件)が偶然か構造的傾向かを見る。
2. **v0.4.0 Track A 世代 2 の設計。** Stage 2 の結果を踏まえて確定する。現時点の暫定候補:
   opus×P1・opus×P3・sol×xhigh(P1 か P3、Stage 2 の結果次第)。fable・GLM は使用量制約のため
   1 構成ずつに留める。
3. **persistent L1–L4 の壁は「evidentiary capacity」仮説がさらに補強された。** sol ablation
   (high/xhigh)に加え、scaffold-ladder でも opus×P1(persistent_clear + compositional 同時)・
   opus×P3(persistent_noisy_proxy)で claude 側初の真の発見が生じた。低 effort・P2 以外の
   条件で確率的に発見され始めている。**次の一手は cycle 予算 4→8 の ablation**
  (deferred_to_generation_2 に記載済み、まだ未実施)——Stage 2 と並行して着手を検討。
4. **GLM(zai)の正式な study 設計。** runner 統合・smoke test は完了しているが、
   世代・config 数・replicate 数を伴う preregistration はまだない。次の preregistration
   (世代 2、または独立 GLM probe)で候補プールに加える判断ポイント。GLM-5.3 のみが確認済みで、
   Kimi K3 等の別系統は別途 CLI 導入・smoke test が必要。なお `Dockerfile`/`scripts/glm-cli`
   として GLM/codex/claude CLI を dev container イメージへ正式に組み込む作業が別セッションで
   進行し、`main` へ PR #18 としてマージ済み(このブランチとは独立)。
5. 世代 2 で >= 2 verified discovery event を再現する構成が出れば Track B(IEEE-CIS 橋、policy §4)
   へ。皆無なら停止規則 1 が発動し、最良構成のまま Track B へ進む(合成完璧主義を避ける)。
6. Container 隔離、Null の独立再実行検証は Confirmatory 前の必須項目のまま。

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
