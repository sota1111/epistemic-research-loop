# C-lite v0.3 Structure Maturation 実装検証

**検証日:** 2026-08-26

**対象Branch:** `system/c-lite-v0.3`
**対象仕様:** [C-lite修正仕様書 v0.3](../c_lite_revision_v0.3.md)

## 結論

v0.3の機械的な受入条件は実装・テスト済みである。Agentは固定Client/Temporal Roleを持たずGeneric Stateから開始し、自発的に登録した高レバレッジ構造仮説についてだけ、一時的なImplementation、Null/Skeptic、Verificationの3 Childを生成する。

構造仮説を使うCandidateはArchiveへ登録できる一方、Validation Debtが自動起票される。Debtが解消するまではValidated Structure、DGP Understanding改善、Confirmed Fact配信へ昇格できない。したがってAgent 05のv0.2 UID結果は、予測改善があっても`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`のままである。

## 仕様対応

| 受入項目 | 結果 | 検証点 |
|---|---|---|
| Generic Agent / 固定Structure Roleなし | Pass | v0.3既定ConfigはNiche空、Generic State開始 |
| Structural Hypothesis Contract | Pass | 2 Decision Dimension以上と予測・反証・識別・DecisionをSchemaで必須化 |
| Lifecycle | Pass | 許可された状態遷移以外を拒否 |
| Dynamic Maturation Fork | Pass | 高Leverageかつ代替仮説登録後だけ3 Childを生成 |
| Validation Debt | Pass | Structure由来Candidate昇格時に自動生成 |
| 未解消Debtの知識昇格防止 | Pass | Validated昇格・Confirmed Evidence Promotionを拒否 |
| Stateless Critic | Pass | 論理識別、交絡、重複、Leakage、Power、Decisionの7条件を検査 |
| Structure-aware Utility | Pass | Leverage、Prior摂動に対する最悪Discrimination、Debt Reductionを加算 |
| UID競合仮説 | Pass | Client/Frequency/Time/Components/Linkage/Leakage/Sparse Overfitを登録可能 |
| Nested Ablation | Pass | M0〜M5の共通Model、Hyperparameter、Fold、3 Seed契約を検証 |
| Frequency-matched Null | Pass | UID頻度、Time、Missingness、Known/New Stratum内の割当分布を保持 |
| Linkage Shuffle | Pass | Frequency/Time Stratumを保ったまま時系列Linkを破壊 |
| Fold-safe History | Pass | Transform側Labelを読まずTrain側履歴のみを使用 |
| G1〜G9 | Pass | Fold safetyからDecision adoptionまで全条件を独立判定 |
| 二軸分類 | Pass | 構造妥当性と予測改善の4分類を強制 |
| Synthetic Controls | Pass | Positiveを昇格、Frequency/Time-matched Negativeを棄却 |
| IEEE受入名 | Pass | `validated_behavioral_client_proxies`へ変更、旧名は読取互換のみ |

## 実行結果

```text
ruff format --check: 236 files formatted
ruff check:           passed
mypy:                 134 source files, no issues
pytest:               282 passed
coverage:             86.20% (required 85%)
secret scan:          0 findings
pip-audit:            no known vulnerabilities
schema export:        completed
git diff --check:     passed
```

Positive/Negative Controlの期待結果も決定的テストで確認した。

```text
stable latent behavioral client: VALIDATED_ACTIONABLE_STRUCTURE
frequency/time-matched no-link:   REJECTED_STRUCTURE
false structure promotion rate:  0.0 (test control set)
```

## 解釈上の制約

この検証はValidatorの制御ロジックとSynthetic Controlに対する識別能力を示すものであり、IEEE-CISにGround-truth Client IDが存在することや、Agent 05がそれを発見済みであることを示さない。

実IEEE-CIS上で`Validated Behavioral Client Proxy`と呼ぶには、同一評価FrameでM0〜M5、20個以上のMatched Null、3 Horizon × 3 Seed、Known/New Interaction、Construct ValidityまたはTemporal Persistence、Decision Adoptionを実行し、G1〜G9をすべて通過する必要がある。それまでは高性能CandidateをArchive/Ensembleへ保持できるが、Critical Discovery完全再発見やT1完全点には数えない。
