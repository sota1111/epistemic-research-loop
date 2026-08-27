# v0.3.6 Blind Real-Agent Qualification Verification

## 実装

以下を追加した。

- Development/Qualification Suiteの分離
- 4 Positive/4 Negative × 3 Contextの匿名Pack生成
- Agent別Opaque ID、列名、Pack/Context順、Row順のPermutation
- Fernet暗号化Controller TruthとAgent-visible tree分離
- Identifiability PreflightとPath/Content Blindness Audit
- 3-mode/最大4 CycleのReal-Agent Submission Contract
- Aggregate-only Promotion、Behavioral Discovery、Explicit Falsification、SRR
- Agent/Population TSDR、TSRR、FSPR、USTR、IRD、EECR、Calibration、Regret
- Output Hash Lock後のTruth復号とPost-hoc評価
- M0–M4 Communication Packet境界とAblation Report

## 試行錯誤

### Trial 0 — Agent Artifact Contract不足

最初の`v036-qualification-01`はPrompt Freeze後に生成したが、Agent-visible JSON ContractがTop-level fieldしか示していなかった。これはAgentの研究能力ではなく、既知でないNested Schemaを推測させるInfra Failureになる。

Agent実行前に検出したためSuiteを上書きせず破棄し、Nested Pack/Cycle/Proposal/Context Contractを固定して`v036-qualification-02`を新規生成した。Qualification-01のData/Truth/ScoreはAgentへ渡していない。

### Trial 1 — Development/Qualification Identifiability

Development-01とQualification-02はいずれもController Oracleで4 PositiveすべてResearch識別可能、4 NegativeすべてOracle Gain 0としてReject可能だった。Qualification-02のAgent-visible treeにTruth token、`.enc`、`.key`は0件だった。

### Trial 2 — 3 Real Agents

3 Agentを同時実行し、各Agentは割当ViewとOutputだけを使用した。

- Agent 01: 6つの自作Representation候補を全Packで比較。TemporalとBinary GateをValidated。Observation candidateは大きなResearch GainがあったがIndependent Implication不足として未昇格。
- Agent 02: operator tournament、capacity refinement、matched null、LOCOの4 Cycle。最初の実行はNumPy 2.xの`row_stack`削除で停止したが、Agent自身が`vstack`へ修正し同一Preregistrationを再実行した。
- Agent 03: broad scanからMissingness、Routing、Time、Categoryへ分岐。Cycle 3で既存key名の取り違えにより実行前停止し、自律修正後に同一Bundleを再実行。Cycle 4は`confounders`欠落をArtifact Validatorが拒否し、研究判断や予測を変えずMetadataを補完した。

これらはGeneric Runtime/Artifact修正であり、HumanによるHypothesis、Feature、Operator、Code修正ではない。Human Assistanceは0として扱った。

### Trial 3 — USTR循環定義の修正

初回Post-hoc評価で`behaviorally_validated`にSealed Gain条件を含めていたため、USTR分母がすでにTransfer成功を選び、USTRが循環的に1.0になることを検出した。

全Agent Submission Hashを維持したまま、DiscoveryをResearch Gain、Matched Null、Independent Implication、Cross-context Stabilityで判定し、Sealed GainをTransferだけに使用するよう評価器を修正した。退行Testとして、Research上ValidatedだがSealed Gainが負のCandidateでもDiscoveryに残り、USTRを低下させるTestを追加した。再集計値はUSTR 0.875である。

## 最終結果

```text
IRD                         1.000
Effective Family Count      9.642
Dominant Family Fraction    0.219
Action Types                4
EECR                        0.375
Population Union TSDR       0.750
Population Union TSRR       1.000
Population Union FSPR       0.000
Resolution Rate             0.792
USTR                        0.875
Median Structure Gain      +0.01960
Brier                       0.1789
ECE                         0.1515
Shadow Recovery             0.625
```

Phase 1 Engineering AcceptanceはPASS。

## 重要な失敗・限界

1. Persistent-unit Positiveは全Agentが未発見/未昇格だった。
2. Negativeの明示的RejectionはAgent 03へ集中した。Population Unionの成功だけではAgent単体の安定性を示さない。
3. Agent 02の個別CalibrationはBrier 0.340、ECE 0.341で不合格だった。
4. Agent 01のValidated Temporal CandidateはSealedへ転送せず、Median Gainは-0.01446だった。
5. Agent 03自身が報告した通り、一部Matched Nullは固定OOF predictionへの層別Permutationで、毎回の完全再学習ではない。
6. 同一Synthetic Generator由来のPilotであり、Confidence Intervalが広い。
7. 共有HostのPath Policy隔離であり、Container mount隔離ではない。
8. IEEE-CIS、未使用Real Benchmark、Communication Mode M1–M4は未測定。

## 再現コマンド

```bash
uv run python scripts/build_v036_qualification_suite.py \
  --suite-id <new-suite-id> --suite-kind qualification

uv run python scripts/audit_v036_blindness.py \
  --suite-root .runs/v036/<new-suite-id>

uv run python scripts/run_v036_real_agent_qualification.py \
  --suite-root .runs/v036/v036-qualification-02 \
  --submission-root .runs/v036/v036-qualification-02/agent_outputs \
  --lock-file .runs/v036/v036-qualification-02/phase1_lock.json

uv run python scripts/finalize_v036_independent_agents.py \
  --truth-manifest .controller_truth/v036-qualification-02.manifest.enc \
  --key-file .state/v036/controller.key \
  --lock-file .runs/v036/v036-qualification-02/phase1_lock.json \
  --submission-root .runs/v036/v036-qualification-02/agent_outputs \
  --blindness-report .runs/v036/v036-qualification-02/blindness_report.json
```

Qualification Suiteは再利用せず、再試験は必ず新Suite IDで生成する。
