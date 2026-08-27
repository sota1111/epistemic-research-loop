# Epistemic Research Loop 引き継ぎ書

**更新日:** 2026-08-27  
**現在の基準:** C-lite v0.3.7 Agent Reproducibility and Blind-spot Qualification  
**対象リポジトリ:** `epistemic-research-loop`

## 1. 現在地

`main`はPR [#17](https://github.com/sota1111/epistemic-research-loop/pull/17)までマージ済みである。

```text
main / origin/main
879812e8765fc7de810ff832386234f586ed5580
Merge pull request #17 from sota1111/system/c-lite-v0.3.7
```

v0.3.7の結論は**Engineering Qualification FAIL**である。これはInfrastructure failureではなく、評価の過大計上を除去した後、Agent単体のStructure discovery / evidence-based falsificationがPreregistered Gateへ届かなかったという結果である。

一方、正しく発見できた少数のActionable StructureはTransferしやすかった。現在の主Bottleneckは、発見後のCandidate translationではなく、前段の仮説生成、識別Evidence、Matched Negative rejection、Promotion calibrationにある。

## 2. 最重要結果

| 指標 | v0.3.7結果 | Gate | 状態 |
| --- | ---: | ---: | --- |
| Median Agent TSDR | 0.0833 | >= 0.50 | Fail |
| Median Agent TSRR | 0.0208 | >= 0.67 | Fail |
| Worst Agent FSPR | 0.3333 | <= 0.20 | Fail |
| Shared Blind-spot Rate | 0.7917 | <= 0.20 | Fail |
| Minimum Leave-one-agent-out TSRR | 0.0000 | >= 0.67 | Fail |
| Persistent Ladder | 1/4 levels、1/3 agents | 3/4、2/3 | Fail |
| Median Structure Brier | 0.2614 | <= 0.20 | Fail |
| Median Structure ECE | 0.1826 | <= 0.20 | Pass |
| Pooled USTR | 0.7500 | >= 0.50 | Pass |
| Median Structure Gain | +0.09431 | > 0 | Pass |

補足値：

```text
IRD                               0.7083
Population Effective Families   14.3505
Dominant Family Fraction         0.1250
Population Action Types          3
EECR                              0.1510
Deep Lineage Completion          0.5972
Mean Population-union TSDR       0.2083
Mean Population-union TSRR       0.0833
Mean Population-union FSPR       0.3333
```

Semantic Diversityは高いが、Discovery/Rejection Complementarityは各0.0208に留まった。多様な研究名・仮説が存在しても、重要構造を機能的にCoverできるとは限らない。

## 3. Ablation結果

### P0 vs P1 Assumption Challenge

| Arm | Mean TSDR | Mean TSRR | Mean FSPR | Persistent discovery |
| --- | ---: | ---: | ---: | ---: |
| P0 | 0.0694 | 0.0278 | 0.1667 | 0/48 |
| P1 | 0.0972 | 0.0278 | 0.0556 | 1/48 |

P1は具体的なStructure名を教えずにTSDRを小幅改善し、FSPRを低下させた。ただしPersistent discoveryは1件だけで、標準Promptへ確定採用できる再現性はない。

### S0 / S1 / S2 Lineage Policy

| Policy | Mean TSDR | Mean TSRR | Mean FSPR | Persistent discovery |
| --- | ---: | ---: | ---: | ---: |
| S0 deterministic | 0.1042 | 0.0208 | 0.1458 | 0/32 |
| S1 posterior commit | 0.0833 | 0.0417 | 0.1042 | 1/32 |
| S2 two-hit maturation | 0.0625 | 0.0208 | 0.0833 | 0/32 |

S1/S2はFSPRを下げたがTSDRを安定改善しなかった。履歴上のDeep Lineage CompletionもS0とほぼ同じであり、現在のPolicy Contractは意図した「一定期間の深い探索」を十分に強制・監査できていない。

## 4. 実装マップ

### Benchmark / Blind Suite

- `src/epistemic_loop/benchmark/v037_repro_suite.py`
  - 4 locked Suite
  - Persistent-unit L1–L4
  - Matched Negative
  - Observation×Routing、Non-actionable、Encoding-only Control
  - Agent別Opaque ID、列名、Pack/Context/Row permutation
- `scripts/build_v037_reproducibility_suites.py`
  - Prompt/Policy hashを含む一括Suite Lock
- `scripts/audit_v037_blindness.py`
  - Agent-visible path/content leakage audit

### Agent Contract

- `src/epistemic_loop/controller/v037_agent.py`
  - 3-mode Proposal
  - S0/S1/S2 lineage metadata
  - 4分解Confidence
  - Failure trace
  - Sequential full-refit null declaration
  - 2 Translation以上
  - Confirmation/Transfer prediction contract
- `prompts/generic_research_agent/v037_p0.md`
- `prompts/generic_research_agent/v037_p1.md`

### Evaluation

- `src/epistemic_loop/evaluation/v037.py`
  - Agent、Agent×Sampling、Population block集計
  - TSDR / TSRR / FSPR / USTR
  - SBR / DC / RC / MAC / LOAO
  - Controller-derived LOCO
  - Locked Translationだけを使うConfirmation
  - Persistent PositiveとMatched Negativeの対評価
  - Evidence-based rejection
  - DiscoveryとTransferの分離
- `src/epistemic_loop/evaluation/calibration_v037.py`
  - Development-only isotonic calibration
  - Calibration-adjusted evidence escalation
- `scripts/lock_v037_agent_runs.py`
  - 24 outputのArtifact validationとSHA Lock
- `scripts/finalize_v037_reproducibility.py`
  - 開封前のPacket/Submission/Prompt/Encrypted Truth SHA再照合
  - Controller Truth復号後の厳格集計

### Tests

- `tests/unit/test_v037_repro_suite.py`
- `tests/unit/test_v037_agent_contract.py`
- `tests/unit/test_v037_calibration.py`
- `tests/unit/test_v037_evaluation.py`

## 5. 評価実装で修正済みの落とし穴

次を再導入しないこと。

1. Sampling conditionを跨いだ「どこか一回の発見」でShared missを救済しない。
2. Confirmation label上で複数Translationを事後最大化しない。Research中にLockしたTranslationだけを使う。
3. Persistent Positiveを、対応Matched NegativeのEvidence-based rejectionなしでDiscoveryへ数えない。
4. Agentが`FALSIFIED`と書いただけでTSRRへ数えない。
5. Transfer Sealed gainをStructure discovery条件へ含めない。
6. Agent申告のLOCOをそのまま信頼せずController側で再計算する。
7. Agent-reported failure stageとController-observable failure stageを混同しない。

これらの厳格化により見かけの成績は低下したが、Lock済みAgent outputやThresholdは変更していない。

## 6. 既知の制約

### 24評価は24 fresh LLM contextではない

実際は6 LLM Agent trajectoryが各4 Suiteを処理した。Suite間DatasetとOpaque viewは独立だが、同一trajectory内で実装経験を持ち越し得る。ConfirmatoryではSuiteごとにfresh Agent contextを作ること。

### Full-refit Null provenanceはPARTIAL

全288 Packは5–30回のFeature再生成・Model再学習を宣言しているが、Replicate単位の次のArtifactを保存していない。

- permutation hash
- preserved-statistics diagnostics
- feature manifest hash
- fold plan hash
- model-fit manifest hash
- OOF prediction hash

現状を「検証済みFull-refit」と表現しないこと。

### Calibration C1/C2は未測定

実装とUnit Testはあるが、Development Agent runでMapをfitし、新Qualificationへ適用していない。報告済み結果はRaw Confidence C0のみである。

### BlindnessはPath Policy隔離

共有Host上でController TruthをAgent-visible root外へ置いた。Container mount / PID namespace / `/proc` isolationではない。Confirmatory claim前にContainer隔離が必要である。

### 統計区間は記述用

Wilson intervalはPackを独立Bernoulliとして扱い、Suite/Family内相関を無視する。ConfirmatoryではSuite/Family cluster bootstrapまたは階層Modelを使うこと。

### Synthetic Generator一般化は未測定

Communication M0–M4、未使用Real Benchmark、IEEE-CIS Hidden transfer、B/B+/C比較は未測定である。

## 7. 次の推奨作業

順序を維持すること。

1. **新Version/Suite IDを作る。** 開封済み`v037-repro-b01..b04`を再利用しない。
2. **Suiteごとにfresh LLM contextを使う。** 24評価なら24 trajectoryを作る。
3. **Null provenance artifactを必須化する。** 自己申告boolだけでPromotionさせない。
4. **P1を暫定Promptとして再検証する。** 具体的なEntity/Time/Feature語彙は追加しない。
5. **Lineage継続をControllerで強制・監査する。** S1/S2は最低2 Cycleまたは明示Falsificationまで同じLineage IDを追跡させる。
6. **Evidence-based Falsification bundleを改善する。** Matched Null、Independent implication、Confirmation非再現を機械Artifactで結ぶ。
7. **C1/C2をDevelopment Suiteだけでfitする。** Qualification Truthはfitへ使わない。
8. **Container隔離を実装する。** Agent/Controller root、env、process、mountを分ける。
9. **新Generator familyまたは未使用Real Benchmarkへ移る。** 同一Synthetic系統への適合を避ける。
10. **個体Gate通過後にだけCommunication M0–M4を行う。** 現段階で共有を増やすと個体能力不足をPopulation Unionが再び隠す。

## 8. 次回Suite作成時の注意

現在の`V037_SUITE_IDS`と`.runs/v037/primary_suite_set_lock.json`は開封済みPilot用である。現行Builderは同じID/Rootへの上書きを拒否する。

次回は以下のいずれかを行う。

- v0.3.8として新しいconstants、config、prompt hash、Suite IDを追加する。
- BuilderをPreregistered manifest入力型へ一般化し、既存IDを変更不能に保つ。

既存`.runs/`、`.state/`、`.controller_truth/`はGit ignore対象であり、コミットしない。Truthを失った環境では、コミット済み集計Reportだけが正本となる。

## 9. 再現・確認コマンド

コード品質：

```bash
make ci
```

最終確認時は次を通過している。

```text
367 tests passed
coverage 85.16%
ruff / format / mypy PASS
schema diff PASS
secret scan PASS
dependency audit PASS
```

開封済みPilotのローカルArtifactが残っている場合のみ：

```bash
uv run python scripts/audit_v037_blindness.py
uv run python scripts/finalize_v037_reproducibility.py --output-root .runs/v037/final_reports
```

新規Suiteでは、必ず新ID/RootへBuildし、Agent実行後にLock、全Output Lock後にFinalizeする。

## 10. 正本文書

- [研究設計](research_basis_and_design_rationale.md)
- [v0.3.7差分仕様](c_lite_revision_v0.3.7.md)
- [v0.3.7 Preregistration](v037_preregistration.json)
- [詳細検証](verification/v037_agent_reproducibility_and_blind_spots.md)
- [Final Acceptance](v037_final_acceptance.md)
- [Qualification Result](v037_qualification_result.json)
- [Agent Scorecards](v037_agent_reproducibility_scorecards.json)
- [Population Blind Spots](v037_population_blind_spot_report.json)
- [Failure Traces](v037_structure_failure_traces.json)
- [Full-refit Null Audit](v037_full_refit_null_audit.json)
- [進捗ログ](progress.md)

## 11. Git / PR状態

```text
PR #17       MERGED
Feature      d3c7499 feat: qualify v0.3.7 agent reproducibility
Merge        879812e Merge pull request #17
Base         main == origin/main
```

PR #17のGitHub CI `quality`とGitGuardianはPass済みである。

## 12. v0.4待避物

未統合のv0.4 Problem Formulation実装が次に残っている。

```text
stash@{0}: On system/c-lite-v0.4: wip: c-lite v0.4 problem formulation implementation
```

概要：16 files、約582 insertions / 12 deletions。主な対象は`configs/system_c.yaml`、schema、`agents/auto.py`、`proposal_bridge.py`、`config.py`、`multi_island_loop.py`、domain、QD archiveである。

このstashは古い`system/c-lite-v0.4`基点（`f69bdde`）で作られ、現行`main`では特に`evaluation/__init__.py`等が進んでいる。`main`へ直接`git stash pop`しない。

安全な復元例：

```bash
git switch -c system/c-lite-v0.4-rebase main
git stash apply stash@{0}
# 競合を個別解消し、make ciを実行
# 正常にコミットできた後だけstashをdrop
```

v0.3.7の個体GateがFailしているため、v0.4の機能追加をそのままPrimary探索へ有効化する前に、上記のAgent単体Qualification改善を優先する。
