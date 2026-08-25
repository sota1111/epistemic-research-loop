# Capability matrix

This is the single place to check what this repository claims to do and where each claim is
enforced. Each row names the requirement, the code that implements it, and the test that would fail
if it stopped being true. **Progress and status live here and in [progress](progress.md), not in the
Linear issue** — Linear carries the pointer, this repository carries the evidence.

Status values: **enforced** (deterministic code refuses the violation), **derived** (computed from
the event log without a human or a model asserting it), **measured** (reported by the benchmark),
**documented** (a policy the code assumes but cannot itself check).

## 1. Hypothesis-centric experimentation

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 1 | 仮説中心で実験を管理している — experiments hang off hypotheses, not the other way round | enforced | `domain/models.py` `ExperimentProposal.hypothesis_ids` (`min_length=1`); `domain/hypothesis_graph.py` | `tests/unit/test_models.py`, `tests/unit/test_hypothesis_graph.py` |
| 2 | 各実験に「何を検証するか」が明確に紐づいている | enforced | `research_question`, `hypothesis_ids`, and `predicted_outcomes.discriminates_from`; unknown hypothesis ids fail `hard_gate` | `tests/unit/test_hard_gate.py` |
| 3 | 実験前に予測・成功条件・反証条件を固定している | enforced | `predictions_if_true` / `predictions_if_false` / `decision_rule` / `controls` required by schema and `validate_preregistration`; the state machine refuses `parsing → planning` reordering | `tests/integration/test_research_loop.py`, `tests/unit/test_state_budget.py` |
| 12 | Validation 方法そのものを研究対象にできる | enforced | `HypothesisType.VALIDATION`; the phase policy will not leave discovery until a validation hypothesis is settled | `tests/unit/test_phase_evidence.py` |
| 13 | 時系列シフト・Group shift・train/test shift・leakage を探索できる | enforced | `HypothesisType.{TEMPORAL_STRUCTURE, ENTITY_STRUCTURE, DISTRIBUTION_SHIFT, LEAKAGE}`; `CompetitionObserver` seeds all four as unresolved questions | `tests/unit/test_models.py` |

## 2. Epistemic value in selection

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 4 | スコア改善だけでなく情報価値の高い実験を選べる | enforced | `scoring/selector.py`: `U = wp·P + wi·I + wr·R + wd·D − λ·C` | `tests/unit/test_scoring.py` |
| 5 | Epistemic Value が実際の実験選択に影響している | enforced | Discovery weights epistemic at 0.45 against pragmatic 0.20 (`config.SelectionConfig`) | `tests/unit/test_scoring.py` |
| 31 | 事前登録した結果尤度と現在beliefからInformation Gainを機械計算できる | enforced | `HypothesisOutcomeForecast` validates both likelihood vectors; `scoring.epistemic.binary_hypothesis_information_gain` computes mutual information; `selection/v2` records the method used | `tests/unit/test_models.py`, `tests/unit/test_scoring.py`, `tests/integration/test_research_loop.py` |
| 17 | 同系統のモデル調整だけに偏らず多様性を保っている | enforced | greedy similarity-penalised portfolio (`select_portfolio`) plus the gate that refuses a fourth consecutive optimization run | `tests/unit/test_scoring.py`, `tests/unit/test_hard_gate.py` |
| 18 | CPU・GPU・時間・LLM コストを考慮している | enforced | `scoring/cost.py`, `controller/budget_manager.py`, and six budget checks inside `hard_gate` | `tests/unit/test_state_budget.py`, `tests/unit/test_hard_gate.py` |

See [experiment selection](experiment_selection.md).

## 3. Explorer / Exploiter separation

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 6 | Explorer と Exploiter の役割が明確に分かれている | enforced | `RunMode.{EPISTEMIC, EXPLOITER_ONLY}`; exploitation cannot begin until `handoff_to_exploiter` records a `ResearchBriefCreated` event | `tests/integration/test_exploiter_handoff.py` |
| 7 | 序盤は探索、終盤は最適化へ自動的に移行できる | derived | `controller/phase_evidence.py` folds the log into `PhaseEvidence`; `phase_policy.decide_phase` consumes it; the autoloop calls both every round | `tests/unit/test_phase_evidence.py`, `tests/e2e/test_local_scoring_loop.py` |
| 21 | Researcher から Exploiter へ検証済みの知見を明示的に引き渡している | enforced | `agents/research_synthesizer.derive_brief` builds the brief from the event log only, and refuses when no completed experiment established a validation scheme | `tests/integration/test_exploiter_handoff.py` |
| 22 | Exploiter の異常結果から Researcher に戻れる | derived | `phase_evidence.anomaly_detected` (contested-after-support, model-class failure, seed/fold spread) returns exploitation to consolidation and retires the brief | `tests/unit/test_phase_evidence.py`, `tests/integration/test_exploiter_handoff.py` |

See [exploiter handoff](exploiter_handoff.md).

## 4. Falsification and belief

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 8 | Falsifier が代替仮説や反証実験を生成している | enforced | `FalsificationRecord.{strongest_alternative_explanation, alternative_claims, recommended_next_test}` are recorded as events and replayed into the next round's hypothesis and experiment prompts | `tests/e2e/test_local_scoring_loop.py` |
| 9 | 失敗した実験や反証された仮説も知識として蓄積している | enforced | `ExperimentFailed` events; falsified hypotheses are kept, never deleted; `RunState.failed_experiments()` and `falsification_digest()` feed the proposal context | `tests/e2e/test_local_scoring_loop.py`, `tests/integration/test_event_projection.py` |
| 10 | 実験結果に基づいて Belief を更新している | enforced | `belief/updater.py` log-odds update clipped to `[0.05, 0.95]`, weight fixed by `EVIDENCE_WEIGHTS` | `tests/unit/test_belief.py` |
| 11 | LLM が研究状態やスコアを恣意的に直接変更できない | enforced | the model returns only `HypothesisBatch`, `ExperimentBatch`, `FalsificationAssessment`; disposition, evidence weight, posterior, gates, budgets, state transitions, and hashes are computed | `tests/e2e/test_autonomous_loop.py` |
| 20 | 仮説・実験・判断・Belief Update の履歴を追跡できる | enforced | append-only JSONL with sequence numbers and a SHA-256 hash chain; SQLite is a rebuildable projection | `tests/property/test_event_replay.py` |

## 5. Holdout, leakage of information, contamination

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 14 | 同じ Validation への適応的過学習を防止している | enforced | `holdout/adaptivity.py` + the `hard_gate` adaptivity check; `loop.max_validation_reuse` (default 8) bounds selecting queries per split | `tests/unit/test_validation_adaptivity.py` |
| 15 | Sealed Holdout / Public / Private を研究ループから隔離している | enforced | `HoldoutGate` (strict_blind refuses every query), `LeaderboardGate` (budgeted, threshold-only by default), `redact_private`, AES-GCM `SealedScoreStore` | `tests/property/test_holdout.py`, `tests/unit/test_leaderboard.py`, `tests/unit/test_holdout_edges.py` |
| 16 | 過去コンペの Winning Solution / Discussion による情報汚染を防止している | enforced | `contamination/source_policy.py` blocks Kaggle discussions, code, competition-specific GitHub, and post-competition material; queries carrying the slug are refused; workers run with networking disabled | `tests/unit/test_contamination.py` |
| 19 | 再現に必要なコード・データ・seed・設定・artifact を保存している | enforced | `base_commit_sha`, `dataset_fingerprint`, `config_hash`, `environment_hash`, unique `seeds`, and `ArtifactRef` (SHA-256, size, MIME, timestamps) on every observation | `tests/integration/test_local_executor.py` |

See [validation adaptivity](validation_adaptivity.md), [holdout policy](holdout_policy.md),
[leaderboard policy](leaderboard_policy.md), [contamination policy](contamination_policy.md).

## 6. Does the research actually pay for itself

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 23 | Exploiter-only と同一条件・同一予算で A/B 比較できる | enforced | `BenchmarkPlan` fixes seeds, budgets, source policy, holdout policy, and `max_final_submissions` across both arms | `tests/e2e/test_synthetic_benchmark.py` |
| 24 | 単発ではなく複数回の paired run で比較できる | enforced | `BenchmarkPlan.replicates` has `ge=3`; `finalize_benchmark` refuses an unpaired or incomplete plan | `tests/e2e/test_synthetic_benchmark.py`, `tests/integration/test_cli_benchmark.py` |
| 25 | Private score だけでなく CV–Private gap・計算効率・発見能力も評価している | measured | `benchmark/evaluator.py` reports sealed regret, `*_cv_private_gap`, `compute_overhead`, `regret_removed_per_extra_cpu_hour`, and `*_discovery_rate` | `tests/e2e/test_synthetic_benchmark.py` |
| 26 | Researcher が不要な簡単な問題を Negative Control として評価している | measured | the `iid_easy` scenario has no gold findings and charges the epistemic arm 20% extra compute; the report surfaces `negative_control_win_rate` and `negative_control_overhead` | `tests/e2e/test_synthetic_benchmark.py` |
| 27 | Synthetic benchmark で時系列シフト・偽特徴・探索空間の壁を再現できる | enforced | `benchmark/synthetic/scenarios.py`: `temporal_shift`, `spurious_leakage`, `candidate_generation_bottleneck` | `tests/e2e/test_synthetic_benchmark.py` |
| 28 | 「スコアを上げる能力」ではなく「未知の重要構造を発見する能力」を確認できる | measured | `GoldFinding` + `concept_match` score each arm on the structure it named; both arms are credited symmetrically, so the discovery gap reflects what each system chose to run | `tests/e2e/test_synthetic_benchmark.py` |

See [benchmark protocol](benchmark_protocol.md).

## 7. Operating within Kaggle's limits

| # | Requirement | Status | Where | Proof |
| --- | --- | --- | --- | --- |
| 29 | Kaggle 提出は 1 日 5 回まで。ローカル採点でループは 10 回以上回せる | enforced | `Budget.max_daily_submissions = 5` and `erlctl kaggle submit --daily-cap` (default 5) refuse an exhausted day; the loop reads only worker-written `metrics.json`, so its cadence is bounded by compute, not by Kaggle | `tests/e2e/test_local_scoring_loop.py` (12 rounds, 0 submissions), `tests/unit/test_kaggle_submission.py` |
| 30 | 進捗はリポジトリのドキュメントから確認でき、Linear には詳細を書かない | documented | this file and [progress](progress.md); the Linear issue carries only a pointer | — |

## Live verification

The rows above are proved by tests. [IEEE-CIS verification](verification/ieee_cis_autonomous_loop.md)
is the separate question of whether they hold on a real competition: 16 adaptive rounds, 21 auto-filed
Linear tickets, one Kaggle submission, and an exploiter-only control arm at matched budget. It records
five defects that only appeared under real data, and three claims it did **not** establish -- the
unattended loop, the control plane's worker fleet, and the Research-to-Exploitation transition.

## What is *not* claimed

- **Confidence is not calibrated.** It is an operational prioritisation number in `[0.05, 0.95]`.
  `belief/calibration.py` can score a run's Brier loss after the fact; nothing calibrates during it.
- **Selection v2 is partial.** Likelihood-based EIG is enforced when a proposal supplies an
  `outcome_forecast`, but old proposals use the explicitly recorded `rubric_v1` fallback. There is
  not yet a validation-world posterior, preferred-state gap, forecast calibration loop, or
  role-scoped multi-agent proposer.
- **The synthetic benchmark is a harness test, not evidence about Kaggle.** Its actions and regrets
  are stipulated. It shows the selection policy prefers informative actions and that the negative
  control costs more without paying — not that the loop beats an exploiter on a real competition.
  Real-competition profiles exist in `configs/benchmarks/` but have not been run in this repository.
- **`normalized_cost` scales are stipulated defaults**, not measured from a real worker fleet.
- **The local executor is a development sandbox.** Production isolation (read-only mounts, network
  policy, resource caps) belongs to `ai-dev-control-plane`; see [security](security.md).
