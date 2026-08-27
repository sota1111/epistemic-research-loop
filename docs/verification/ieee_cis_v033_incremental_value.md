# IEEE-CIS v0.3.3 実装・検証結果

## 結論

v0.3.3の評価契約、36-run設計、cgroup v2実測、Hard Budget、Mechanism Calibration、Structure Promotion Gate v2、Private Embargoを実装した。既存v0.3.2の結果は、W02単体のHidden転送FAILとLocked Ensemble転送PASSへ正しく分解できた。

一方、B/B+/CのLive 36-runと新しいPrivate評価は完了扱いにしていない。現在の実行環境はcgroup v2を読めるが、Processは共有root cgroup `/` に所属し、cgroup filesystemもread-onlyである。Arm別の専用cgroupを作れないため、実測Process-tree CPUを1%以内で比較するPrimary RunのAdmission Gateが拒否した。Sequential実行にしても他Process混入を排除できず、仕様上の同一Resource比較にはならない。

したがって、今回の検証範囲は次のとおりである。

```text
Implementation / Unit / Policy Preflight: PASS
Live B/B+/C 36-run: NOT RUN (resource-isolation gate)
PrivateAUC_C - PrivateAUC_B+: UNMEASURED
PrivateAUC_C - PrivateAUC_B: UNMEASURED
```

## v0.3.2 Frozen Evidenceの再分類

| 項目 | 結果 |
| --- | ---: |
| Archive Best Private AUC | 0.909654 |
| W02 Single Private AUC | 0.899993 |
| Locked Ensemble Private AUC | 0.914784 |
| W02 Standalone Gain | -0.009661 |
| Ensemble Gain | +0.005130 |
| Local→Private Spearman | 0.4 |

Acceptanceは以下になった。

| Acceptance | 状態 |
| --- | --- |
| Locked portfolio gain vs previous Archive | PASS |
| W02 standalone Hidden transfer | FAIL |
| Ensemble Hidden transfer | PASS |
| Local candidate-ranking fidelity | PARTIAL PASS |
| Quality-conditioned predictive diversity | PASS |
| Archive-wide predictive breadth | PARTIAL、non-blocking |
| Mechanism attribution | PARTIAL |
| Structural falsification | PASS |
| True structure discovery | PARTIAL PASS |
| System C vs B/B+ | UNMEASURED |

`Effective Rank = 1.116561`はPilot閾値1.2未満だが、Private Ensemble Gainが正だったため、Diagnostic-onlyかつnon-blockingと判定した。

## Mechanism Calibration

W02について、Missingness Topologyを主要因、Category Hashを第二要因とする予測に対し、実測は逆だった。

| 評価 | 結果 |
| --- | ---: |
| Component sign accuracy | 1.0 |
| Effect range accuracy | 0.5 |
| Dominant rank accuracy | 0.0 |
| Slice accuracy | 1.0 |
| Learner transfer accuracy | 1.0 |
| 総合 | PARTIAL |

Topologyの正方向・Slice・Learner Transferは支持されたが、Category Hashの効果範囲と主要因順位を外した。よってW02は`USEFUL_REPRESENTATION_WITH_PREREGISTERED_SLICE_SUPPORT`のままであり、構造へ昇格しない。

## Structure Promotion Gate v2

3 SeedすべてがSupporting Evidenceで、Held-out Positive/Negative Controlが正しく分類されたケースはPromotionした。各Seedを1つずつ除外した3ケースも全てPassした。

1 Seed supporting、2 Seed contradictingの混合集約は、以下の理由でPromotionを拒否した。

```text
full_seed_aggregate_failed
leave_one_seed_out_unstable
```

Seed単位のTerminal Promotion APIは設けていない。Threshold調整用とHeld-out評価用に同一Control Familyを使った場合、およびHeld-out Negativeを誤Promotionした場合もGateが拒否する。

## 36-run Sealed Design

設定からB/B+/C各12 Seed、合計36 Runを構成できた。Seed集合は全Arm共通で、順序はSeedごとのB→B+→Cである。

```text
planned runs: 36
runs per arm: 12
common seeds: 12
private visible during run: false
plan sha256: d2794f1cb6ef75d1db762784528b5e56cadb04269c25491a3832f1ce7d7e1d51
```

Sealed Batchは36件のCandidate commit、Manifest、Fold、Selection Rule、Prediction、Submission Hashが全て揃うまで生成できない。Private Score APIは36件を一括で渡す場合だけ受理し、部分照会を拒否する。テストではB/B+/Cの12 Seed完全BatchだけをLockでき、1件欠落・Seed不一致・重複Output IDを拒否した。

## Resource検証

実環境で以下を確認した。

| 項目 | 結果 |
| --- | --- |
| cgroup filesystem | cgroup2fs |
| `cpu.stat` | Readable |
| `memory.current` | Readable |
| `memory.peak` | Readable |
| current cgroup | `/` |
| cgroup write | 不可 |
| dedicated Arm cgroup | なし |
| Live Primary Admission | Reject |

MeterのCounter差分、Memory Peak、固定4 Thread環境変数、Finalization Reserve、Observed CPU/Token/Wall-clock一致判定はUnit Testで検証した。共有root cgroupを許可する明示的なPreflight Modeでも、Private-ready Batchは作らない。

## Private Embargo

v0.3.2 Private結果の利用目的は`research_conclusion`に限定した。Feature tuning、Model tuning、Ensemble weight tuningはAPIが拒否する。新しいB/B+/C比較はPolicy、Prompt、Budget、Acceptance、36 Outputをすべて固定してから一括評価する。

IEEE-CISは以後Development Benchmarkであり、Confirmatory Claimには未使用Competitionを要求する。

## 未完了項目

以下は実装不足ではなく、実測に必要な外部条件が満たされていないため未完了である。

1. Armごとの書込可能な専用cgroup v2 node
2. 同一LLM・Token上限でのB/B+/C 36 Candidate生成
3. 全Artifactを通した36 Output Lock
4. 全Armの実測CPU・Token・Wall-clock一致
5. 一括Private評価

条件が揃った時点で、`PrivateAUC_C - PrivateAUC_B+`と`PrivateAUC_C - PrivateAUC_B`を初めて判定する。それまではFull C、B+、Strong Bの優劣を主張しない。

機械可読なPreflight結果は`docs/verification/v033_preflight_result.json`に保存した。
