# C-lite Revision v0.3.8 — Fresh-context Reproducibility with Machine-audited Provenance

**基準:** v0.3.7 Engineering Qualification FAIL（[検証](verification/v037_agent_reproducibility_and_blind_spots.md)）からの是正回。
生成系・Pack設計・評価Gateは v0.3.7 と同一に保ち、介入セットだけを差分にする。

## v0.3.7 からの差分

1. **Suiteごとに fresh LLM context。** 24評価 = 24個の独立 `claude -p` プロセス。各 run は隔離
   作業ディレクトリで実行し、stream transcript を保存して Blindness audit に使う。実行は CLI 認証
   （`claude -p`）であり、Provider API key は環境に渡さない。
2. **Null provenance artifact の必須化。** 実行済み Null replicate ごとに permutation hash /
   preserved statistics / feature manifest hash / fold plan hash / model fit manifest hash /
   OOF prediction hash / gain を提出に含める。自己申告 boolean だけの Null は Lock 前に契約違反として
   拒否する。Controller は件数整合・gain 整合・hash 一意性を機械監査する（Artifact自体は Agent 計算で
   あり、独立再実行は未実施 — 過大表現をしない）。
3. **P1 を単独 Prompt として固定。** v0.3.7 P1 の科学的本文は不変で、構造固有語彙は追加していない。
   追加節は Lineage 拘束と Provenance 手続きの記述のみ。
4. **Lineage 継続の Controller 強制。** `posterior_commit` / `two_hit_maturation` では、明示 Close /
   Falsification / 成熟なしに open lineage を放棄した提出を `selected_lineage_id` 系列から検出して
   Lock 前に拒否する。Agent 申告 boolean には依存しない。
5. **Failure stage A–C の Controller 判定。** Proposal artifact から hypothesis / experiment design /
   implementation 段階を判定し、自己申告 trace と併記する。
6. **C1/C2 を Development Suite だけで fit。** 2つの Development Suite（6 fresh run）を先に実行・Lock・
   開封して isotonic map と ECE 連動 Evidence gate を決め、Qualification には適用のみ行う。
   Primary gate は比較可能性のため v0.3.7 と同一の Raw C0 gate。
7. **Suite×Seed cluster bootstrap 区間。** Wilson 区間（独立性仮定）に加えて、Suite×Sampling condition
   Block を単位にした bootstrap 区間を報告する。

## 変更しないもの

- Generator families、4-level Persistent Ladder、Matched Negative、12 Pack 構成、3 Context、900 rows。
- Behavioral discovery / Evidence-based rejection / Matched-negative gate / Controller LOCO の評価規則
  （`evaluation/v037.py` を検証済みのままre-use）。
- Engineering Gate 閾値。

## 実行順序

```bash
uv run python scripts/build_v038_suites.py            # 4 qual + 2 dev を一括生成・Lock
# Development 6 runs（fresh `claude -p`）
uv run python scripts/run_v038_agent.py --suite-id v038-dev-d01 --run-id agent-01-s17
# ... 全 development run 完了後
uv run python scripts/lock_v038_agent_runs.py --group development
uv run python scripts/fit_v038_calibration.py         # dev truth のみ開封し C1/C2 を Lock
# Qualification 24 runs（fresh `claude -p`）
uv run python scripts/run_v038_agent.py --suite-id v038-qual-c01 --run-id agent-01-s17
# ... 全 qualification run 完了後
uv run python scripts/audit_v038_blindness.py
uv run python scripts/lock_v038_agent_runs.py --group qualification
uv run python scripts/finalize_v038.py                # qual truth 開封・厳格集計・docs 出力
```

## 隔離水準（正直なラベル）

- 作業ディレクトリ隔離（リポジトリ外）+ CLI deny rule（リポジトリ / Controller path / ネットワーク）
- Truth は保存時暗号化、鍵は 0600
- 事後 transcript audit（禁止 path / 禁止 token）
- **Container / mount / namespace 隔離ではない。** Confirmatory claim には引き続き Container 隔離が必要。

## 正本

- [Preregistration](v038_preregistration.json)
- Prompt: `prompts/generic_research_agent/v038_p1.md`（sha256 `d2c60932…c34fda`）
