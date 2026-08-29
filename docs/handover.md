# Epistemic Research Loop 引き継ぎ書

**更新日:** 2026-08-29
**現在の基準:** v0.4.0 Track A 世代 1 + 4 つの side-probe 全て完了(78 run)。**opus×P1(cycle=4)が
3 study・14 replicate を通じて false promotion ゼロのまま P1 達成基準を満たしたと判定。**
[v0.4.1 方針](c_lite_v041_policy.md)を策定し、Track B(IEEE-CIS)を起動。**Matched Negative
構築法の根本的な設計欠陥(decile-stratified permutation)を特定・修正した後、IEEE-CIS
(`v041-trackb-03`)・Santander(`v042-mc-b02`)の 2 コンペ独立に blind bridge の成立を
確認した(2026-08-29)。** IEEE-CIS:opus×P3・sol×P3×xhigh の 2/3 構成が P2 達成。
Santander:**3/3 構成全てが達成**、Matched Negative は 48 パック中 1 件のみ昇格
(agent 申告 AUC 中央値 0.503、ほぼ完全な chance)。2 コンペでの独立達成により、
単一コンペの偶然という懸念は解消された。opus×P1(合成側 P1 達成構成)は IEEE-CIS では
1/4 のみだが Santander では 4/4——同一構成の実データ transfer 成功率がコンペ依存で
大きく異なるという知見も得た。詳細:
[Track B qualification](verification/v041_track_b_qualification.md) /
[Santander qualification](verification/v042_santander_qualification.md)。

**v0.4.2 進行中(2026-08-29)。** 目標を「Kaggle 金メダル」から「複数コンペでの best-of-population
近傍到達 + 未知構造発見の検証」に修正([v0.4.2 方針](c_lite_v042_policy.md)、改訂メモ参照)。
Rossmann・Santander は同日中にユーザーが Kaggle コンペ規約に同意しデータ取得済み(旧
ブロッカー解消)。builder を `v042_multi_competition_suite.py` としてコンペ非依存に一般化済み。

**Matched Negative 構築法に 2 段階の欠陥修正を実施(2026-08-29、2 段目で成功)。**
1 段目(baseline model を線形→`HistGradientBoostingClassifier`)は**効果なし**と判明
(`v041-trackb-02`:P2 再現要件 3 構成とも 0/4、negative パック AUC 0.48〜0.73 で初回から
不変)。根本原因を数学的・実験的に特定——**`decile-stratified permutation` は decile 間の
陽性率相関を完全に温存する設計欠陥**(baseline の表現力とは無関係、合成データでの再現実験で
`AUC(risk, decile-permuted target)=0.988` を確認)。`_destroy_target_structure`
(完全ランダム permutation、stratification 廃止)へ 2 段目の修正を実施した `v041-trackb-03`
で **P2 再現要件を opus×P3(3/4)・sol×P3×xhigh(4/4)の 2 構成が達成、Matched Negative は
48 パック中 0 件昇格**——修正が機能したことを確認した。詳細:
[Track B qualification](verification/v041_track_b_qualification.md)。

**Santander(`v042-mc-b02`、修正版)も P2 再現要件を達成——IEEE-CIS より強い結果
(2026-08-29)。** 3構成全て(MC-opus-P1:4/4、MC-opus-P3:4/4、MC-sol-P3:3/4)が
成立、Matched Negative は 48 パック中 1 件のみ昇格(AUC中央値0.503、ほぼ完全な
chance)。**2 つのコンペで独立に P2 が達成されたことで、v0.4.2 の 2 claim(best-of-
population 近傍到達・未知構造発見)が単一コンペの偶然でないことを実証した。** 構造面では
promoted パックの claim が構成・seedを問わず「context 間で共有される単一の線形方向」という
一貫した discovery を示し、Santander technique taxonomy の技術クラス#2(特徴独立性前提の
モデリング)と初めて部分一致した(IEEE-CIS 側は 0/6 一致だった)。**opus×P1(合成側 P1
達成構成)は IEEE-CIS では 1/4 だったが Santander では 4/4——同一構成の成功率がコンペ
依存で大きく異なるという新知見。** 詳細:
[Santander qualification](verification/v042_santander_qualification.md)。
旧 permutation 版(`v042-mc-b01`)は参考記録のみ:
[記録](verification/v042_santander_v1_informal_note.md)。Rossmann は回帰対応が未実装の
ため引き続き見送り([v0.4.2 方針§3](c_lite_v042_policy.md))。

**suite_id 命名の教訓:** `v042-mc-santander-01` のように suite_id にコンペ名を含めると
`agent_packet.json` へそのまま書き込まれエージェントへ漏洩する(盲検監査が検出・修正済み)。
以後の suite_id はコンペ名を含まない opaque 命名(`v042-mc-a01`・`b01`・`b02`...)を使うこと。

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
- **cycle-budget ablation(4→8 cycle)完了。** opus×P1×cycle8・sol×P1×xhigh×cycle8、各 6
  replicate = 12 run(cycle=4 baseline は既存 study 再利用)。**事前登録した capacity 仮説は
  支持されなかった。** 発見イベント数はほぼ横ばい(opus 2.0→1.83/replicate、sol 1.17→1.33/
  replicate)。**多様性指標は両モデルとも明確に低下**(opus 3.75→2.67、sol 1.67→1.17)——
  reasoning effort とは逆方向の効果。**cycle を増やすと「広く探索」ではなく「同じ仮説を
  深く詰める」方向に働く**——evidentiary capacity を単一概念で扱うのは不正確だったと判明。
  sol の false promotion 1→4(単一 suite 集中、単発の暴走型)。`persistent_delayed_history`
  は opus×P1×cycle8 でも 1/6 発見(cycle=4 の Stage2 と同水準、底上げなし)。
  運用面:suite build 実行忘れ・`_CONFIG_REGISTRY` 登録漏れ(Stage2 に続き 2 度目、回帰テスト
  追加済み)、バッチ親プロセスが原因不明で異常終了(子プロセスは孤立生存で完走、実害なし)。
  詳細: [verification/v040_cycle_budget_ablation_qualification.md](verification/v040_cycle_budget_ablation_qualification.md)
- **[v0.4.1 方針](c_lite_v041_policy.md)を策定。** 累積発見台帳を精査した結果、**opus×P1
  (claude-opus-5・P1・cycle=4)が gen1・Stage1・Stage2 の 3 study・14 replicate を通じて
  false promotion ゼロのまま 3 つの異なる persistent family(compositional・clear・
  delayed_history)を発見しており、v0.4.0 方針の P1 達成基準(同一構成の独立 2 run 以上での
  persistent 系発見+汚染なき Matched Negative 棄却)を満たしていると判定した。** v0.4.0 の
  停止規則 2(「P1 達成構成が出た時点で Track B へ即時移行」)に従い、v0.4.1 は Track A の
  さらなる世代を追わず **Track B(IEEE-CIS blind bridge)の起動を主目的**とする。投入構成は
  opus×P1(実績)・opus×P3(Stage2 で同点最高)・sol×P3×xhigh(codex 系で唯一複数 persistent
  family 発見)の 3 構成。**Track B の Suite build は実データを扱うためユーザー確認を取ってから
  実行する**(本方針書に明記済み)。
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

0. **Kaggle コンペ規約への同意——2026-08-29 ユーザーが Rossmann・Santander 両方で完了、
   データ取得済み。** (以前このブロッカーで停止していたが解消。)Santander は
   `v042-mc-b01` として Suite 構築済み(§1b 参照)。**重要な事故と修正:** 初回ビルドで
   `--suite-id v042-mc-santander-01` を使ったところ、盲検監査(`audit_v042_blindness.py`)が
   全 12 view で `santander` 文字列の混入を検出——**suite_id は `agent_packet.json` に
   そのまま書き込まれる**ため、コンペ名を suite_id に含めるとエージェントへ直接データセット
   識別情報が漏れる。該当 Suite は削除・再構築し、以後の suite_id はコンペ名を含まない
   opaque な命名(`v042-mc-a01`・`v042-mc-b01`)に統一した
   (`v042_multi_competition_suite.py` の `V042_MC_SUITE_IDS` にコメントで明記)。
   Rossmann は回帰対応が未実装のため見送りのまま(`[v0.4.2 方針§3](c_lite_v042_policy.md)`)。
1. **Track B(IEEE-CIS blind bridge)——起動・実行済み、Matched Negative 設計の修正が必要
   (2026-08-29)。** 1 Suite(`v041-trackb-01`)・12 run(opus×P1/P3・sol×P3×xhigh 各 4 replicate)
   を実行、契約エラー 0・盲検監査クリーンだったが、**P2 再現要件は 3 構成とも不成立**——
   主因は候補構造の未発見ではなく、**Matched Negative パックが 12 run 中 9 run で最低 1 件
   昇格した**こと。提出済み transfer AUC を精査すると、一部(`pack-n01`)は chance 付近
   (~0.5)なのに昇格されておりエージェント側の閾値判定の甘さ、残り(`pack-n02/03/04`)は
   複数 run・複数モデルで再現する 0.55〜0.71 の AUC が見られ、**Controller 側の Matched
   Negative 構築法(decile-stratified permutation、baseline が線形ロジスティック回帰)が
   非線形残差構造を破壊しきれていない疑いが強い**——suite 設計側の技術的負債。
   詳細:[Track B qualification](verification/v041_track_b_qualification.md)。
   **次のステップ:** baseline モデルをより表現力の高いものに変える等で Matched Negative
   構築を強化し、新 Suite で再試行する。実データを再び扱う判断のため、**実行前にユーザー
   確認を取ること**。
   **2026-08-29 追記1:** ユーザー承認を得て baseline を `HistGradientBoostingClassifier` に
   変更した新 Suite(`v041-trackb-02`)を construct・12-run 再検証を実行・開封。**結果:
   P2 再現要件は 3 構成とも 0/4 で不成立——初回よりむしろ悪化。** negative パックの agent
   申告 transfer AUC は 0.48〜0.73(中央値 0.602)と初回(0.55〜0.71)からほぼ不変——
   baseline 強化は効かなかった。
   並行して builder を `v042_multi_competition_suite.py` としてコンペ非依存に一般化し、
   v041-trackb-01 の FSPR-clean な 2 run(Matched Negative 汚染の影響を受けていない)に
   対して修正後の best-of-population 指標を遡及適用した——構造面は taxonomy 6 クラスと
   0/6 一致(匿名化データでは列意味論依存の技術クラスに到達しにくい可能性)、性能面は
   population 最大 +0.21 AUC(baseline比)。詳細:
   [遡及分析](verification/v042_best_of_population_ieee_cis_retrospective.md)。
   **2026-08-29 追記2(根本原因特定・本修正):** baseline 強化が効かなかった理由を数学的に
   特定した——`_decile_stratified_permutation` は risk decile **内**でのみラベルを
   シャッフルするため、decile **間**の陽性率相関(target と risk の粗い相関)を完全に
   温存してしまう設計欠陥だった(bucket 内シャッフルは bucket の陽性件数を不変に保つため、
   これは permutation の数学的性質として必然)。AUC は順位統計量であり、この粗い相関だけで
   chance を大きく超えるスコアが出る。合成データでの再現実験で
   `AUC(risk, decile-permuted target)=0.988`、`AUC(held-out独立モデル, 同target)=0.700`
   (実測レンジ 0.55〜0.73 と整合)を確認、baseline の表現力とは無関係と証明した。
   **修正:** `_decile_stratified_permutation` → `_destroy_target_structure`(完全ランダム
   permutation、stratification 廃止)。**suite_id 命名の教訓も同時に発見:**
   `v042-mc-santander-01` は suite_id が `agent_packet.json` に書き込まれるためコンペ名の
   漏洩になる(盲検監査が検出)——以後 opaque 命名(`v042-mc-a01`/`b01`/`b02`)に統一。
   **2026-08-29 追記3(修正の成功を確認):** `v041-trackb-03`(修正版)12 run 完了・盲検
   監査クリーン・開封。**Matched Negative は 48 パック中 0 件昇格(v1:11/48、v2:12/48から
   ゼロへ)、agent 申告 AUC 中央値 0.522(chance 水準へ復帰)。P2 再現要件を TB-opus-P3
   (3/4)・TB-sol-P3(4/4)の 2 構成が達成——Track B が実データで初めて成立した。**
   TB-opus-P1(合成側 P1 達成構成そのもの)は 1/4 のみで非達成——P3(自己批判 scaffold)の
   追加が実データ transfer に重要という新知見。詳細:
   [Track B qualification](verification/v041_track_b_qualification.md)。
2. **codex 系(sol/terra)限定の false promotion 現象——機序を部分的に特定済み(2026-08-29、
   read-only 調査完了)。** 4 件の暴走 replicate(gen1 terra/g03・sol ablation high/b05・
   Stage1 sol×P3/c04・cycle8 sol/e05)が実際に書いた `run_protocol.py` を直接読んだ結果、
   **4 件全てが null 分布を `N_NULL=5` replicate で推定していた**(promotion 判定
   `position>=0.95` が理論上 ~16.7% の確率でノイズでも棄却域に入る粗い検定になる)。
   対照 opus は一貫して 200〜500 replicate。ただし N_NULL=5 は codex の固定習慣ではなく
   run ごとにばらつき、false promotion 0 件の N_NULL=5 run も多数あるため、**必要条件に
   近いが十分条件ではない**——「codex 系は自己記述する統計プロトコルの厳密さが run 間で
   ばらつく」という限定的な主張までが現時点の到達点(詳細:
   [累積発見台帳§7](v040_discovery_ledger.md)、[v0.4.1 方針§4.1](c_lite_v041_policy.md))。
   これ以上の深掘り(null replicate 数の下限をプロンプトで指定する介入の是非など)は
   Track B より優先度低。
3. **GLM(zai)の正式な study はまだ実施していない。** runner 統合・smoke test 済み。
   Track B 完了後、または並行する余力があれば独立 side-probe として投入する
   (v0.4.1 方針§4.2)。なお `Dockerfile`/`scripts/glm-cli` として GLM/codex/claude CLI を
   dev container イメージへ正式に組み込む作業が別セッションで進行し、`main` へ PR #18 として
   マージ済み(このブランチとは独立)。
4. Container 隔離、Null の独立再実行検証は Confirmatory 前の必須項目のまま。

## 7. 再現・確認コマンド

```bash
make ci          # ruff / mypy / schema / secret / audit 全 Pass(tests は都度件数変動)

# 各 side-probe は build → batch → audit → lock → finalize の共通パターン
# (例:cycle-budget ablation。他の study も scripts/*_v040_*.py の対応スクリプトで同型)
uv run python scripts/build_v040_cycle8_suites.py    # 一度だけ、以後は resumable(新 suite id 追加時のみ再実行)
uv run python scripts/run_v040_cycle8_batch.py --parallel 4   # 再開可能
uv run python scripts/audit_v040_cycle8_blindness.py
uv run python scripts/lock_v040_cycle8_runs.py
uv run python scripts/finalize_v040_cycle8.py        # 全 run が Lock 済みの場合のみ

# 新しい study を追加する際の必須チェックリスト(このセッションで 2 回登録漏れを起こした):
# 1. v040_grammar_suite.py に SUITE_IDS/MASTER_SEED/CONFIGS/RUN_IDS を追加
# 2. scripts/run_v040_agent.py の _CONFIG_REGISTRY に追加 ← 忘れやすい
# 3. build/batch/audit/lock/finalize の 5 スクリプトを既存 study からコピーして書き換え
# 4. uv run pytest tests/unit/test_v040_grammar_and_contract.py -k registers_every_study
#    (registry 完全性の回帰テスト、新 study を検知して自動でチェックする)
```

`.runs/` `.state/` `.controller_truth/` は Git ignore 対象。開封済み Suite ID の prefix
(`v037-repro-*`, `v038-qual-*`, `v038-dev-*`, `v039-qual-*`, `v040-genA-*`, `v040-solE-*`,
`v040-scaf-*`, `v040-scaf2-*`, `v040-cyc8-*`)は再利用禁止。新しい study は新規 suite id・
新規 master seed で preregister すること。`evaluate_v037_runs`/`evaluate_v038_runs` は
`excluded_pairs`(インフラ障害等の preregistered 除外)と `expected_suite_count`
(既定 4、非対称スロット構成では明示指定)の 2 引数を持つ(いずれもデフォルトで v0.3.7/8/9・
世代 1 は無変更)。`agent_seed_aggregates` は実際に提出された `(agent_id, sampling_seed)`
組のみを走査する(全直積ではない、非対称構成でのゼロ除算を 2026-08-29 に修正)。

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
- [sol reasoning-effort ablation Preregistration](v040_sol_effort_ablation_preregistration.json) /
  [検証](verification/v040_sol_effort_ablation_qualification.md) /
  [Selection Table](v040_sol_ablation_selection.json) / [Diagnostics](v040_sol_ablation_diagnostics.json)
- [scaffold-ladder Stage1 Preregistration](v040_scaffold_ladder_preregistration.json) /
  [検証](verification/v040_scaffold_ladder_qualification.md) /
  [Selection Table](v040_scaffold_ladder_selection.json) / [Diagnostics](v040_scaffold_ladder_diagnostics.json)
- [scaffold-ladder Stage2 Preregistration](v040_scaffold_ladder_stage2_preregistration.json) /
  [検証](verification/v040_scaffold_ladder_stage2_qualification.md) /
  [Selection Table](v040_scaffold_stage2_selection.json) / [Diagnostics](v040_scaffold_stage2_diagnostics.json)
- [cycle-budget ablation Preregistration](v040_cycle_budget_ablation_preregistration.json) /
  [検証](verification/v040_cycle_budget_ablation_qualification.md) /
  [Selection Table](v040_cycle8_selection.json) / [Diagnostics](v040_cycle8_diagnostics.json)
- [累積発見台帳](v040_discovery_ledger.md)(102 run、study 完了ごとに更新)
- [v0.4.1 方針](c_lite_v041_policy.md) — P1 達成の宣言、Track B 起動計画
- [Track B 初回 qualification](verification/v041_track_b_qualification.md) /
  [Matched Negative 修正 Preregistration](v042_trackb_matched_negative_fix_preregistration.json)
- [v0.4.2 方針](c_lite_v042_policy.md) — best-of-population + 未知構造発見の複数コンペ検証、
  計算量フィルタ
- **[v0.4.3 方針(案)](c_lite_v043_policy.md)** — 現行の正本(ユーザー確認前の草案)。
  context プーリング発見の由来検証・taxonomy 2層化・Rossmann 回帰対応・実行構成既定の
  P3 系化
- **[クロスコンペ統合分析(IEEE-CIS×Santander)](verification/v042_cross_competition_synthesis.md)**
  — 現行の正本。両 claim の 2 コンペ独立確認、context プーリング等のメタ技術パターン新発見
- [best-of-population 遡及分析(IEEE-CIS、v041-trackb-01 の限定データ、superseded)](verification/v042_best_of_population_ieee_cis_retrospective.md)
- [Santander qualification(P2 3/3 構成達成)](verification/v042_santander_qualification.md) /
  [参考記録(v042-mc-b01)](verification/v042_santander_v1_informal_note.md)
- Controller専有 technique taxonomy:
  [IEEE-CIS](controller_reference/ieee_cis_technique_taxonomy.md) /
  [Rossmann](controller_reference/rossmann_technique_taxonomy.md) /
  [Santander](controller_reference/santander_technique_taxonomy.md)
- [進捗ログ](progress.md)

## 9. Git 状態

```text
ブランチ  system/c-lite-v0.3.8(main 未マージ、PR 未作成)
main      879812e(= PR #17、v0.3.7)
v0.4      stash はユーザー指示で破棄済み(2026-08-27)
```
