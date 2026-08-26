# IEEE-CIS C-lite v0.3.1 measurement and debt-closure verification

**実施日:** 2026-08-26  
**Competition:** IEEE-CIS Fraud Detection  
**用途:** Late Submissionによる事後Hidden/Private Endpoint評価。正式順位・賞の主張には使用しない。

## 結論

v0.3の制御機構は再現可能に動作したが、生成済みLocked CandidateはCanonical BaselineのPrivate AUCを改善しなかった。Full Common First-level Cross-fitでもPredictive Collapseが確認され、Island 01のPayment-process仮説は20回Matched Nullを通過しなかった。したがって次の広域探索やMatched v0.2/v0.3比較にはまだ進まない。

4層Acceptanceは次のとおりである。

| Acceptance | 判定 | 根拠 |
| --- | --- | --- |
| Control-plane | Pass | Cold Replay 3/3 first-attempt valid、Resource Failure 0、全test/OOF Gate合格 |
| Dynamic Structure Mechanism | Pass | DebtをTerminal化し、誤Promotionせず非共有を維持 |
| IEEE-CIS Capability | Fail | 2 Model FamilyとOOFは実行済みだが、Validated Client Proxy、fold-safe UID、validated Known/Newが欠落 |
| Primary Endpoint | Fail | v0.3 adaptive Private 0.893519 < Canonical 0.905709、別Competition未実施 |

Generic Structure成功条件であるValidated High-leverage Structureは0件である。

## 1. Frozen Primary Endpoint

Batch hashは`d212957f5d129b3cebe5c530064d45fbf285ede9229fb0da33d8c47a8a516bce`。4件の候補、順序、Submission内容SHAをスコア照会前に固定した。全Artifactは506,691行、一意TransactionID、非欠損有限確率、固定SHAを通過した。

| Candidate | Local AUC | Public AUC | Private AUC | Public rank相当 | Frozen Private順位 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Canonical Baseline | 0.910093 | 0.934969 | 0.905709 | 4102 | 1 |
| v0.2 Corrected Locked | 0.948746 | 0.922259 | 0.897071 | 4713 | 2 |
| v0.3 Cycle 1 01/02 Blend | 0.873772 | 0.913496 | 0.892904 | 4934 | 4 |
| v0.3 Cycle 4 Island 01 | 0.869652 | 0.909933 | 0.893519 | 4994 | 3 |

Kaggle refsは順に`55790957`、`55790958`、`55790962`、`55790963`。Local→Private Spearmanは0.6だった。ただしLocal AUCは同一First-level protocolではなく、v0.2/v0.3は狭いSecond-level OOF Intersectionである。この値はLocal validation fidelityの公平な比較ではない。

Kaggleのdownload可能なLeaderboardはPublic scoreだけを含むため、Private rank相当は取得不能としてnullを記録した。Public rank相当も当時の正式参加順位ではなく、Late scoreをdownload済みPublic Leaderboard score分布へ挿入した値である。

## 2. Full Common First-level Cross-fit

全590,540 train rowsを使用し、40%地点から始まる3つの非重複Forward Horizon、7日gap、Seed `17/42/20260826`、Fold-local Feature Fitを全4 Representationへ共通適用した。各Foldのvalidationは118,108行、共通OOFは354,324行である。

| Representation | Seed平均OOF AUC |
| --- | ---: |
| Canonical Base | 0.895077 |
| Island 01 Cycle 4 | 0.898652 |
| Island 02 Cycle 2 | **0.902963** |
| Island 03 Cycle 2 | 0.898623 |

Rank Stabilityは平均pairwise Spearman 0.888889、minimum 0.8で、Island 02が全9 seed/fold contextで最良だった。

Predictive Diversity測定結果:

| 指標 | 値 | Pilot Gate |
| --- | ---: | ---: |
| Residual Effective Rank | 1.038561 | < 1.2 |
| Mean Residual Correlation | 0.993091 | > 0.95 |
| Pairwise Residual Correlation範囲 | 0.990831–0.994340 | — |
| Prediction Correlation範囲 | 0.981171–0.988304 | — |
| Nested Ensemble AUC | 0.901061 | — |
| Marginal AUC Gain | −0.001902 | <= 0 |
| Marginal MSE Gain | −0.000174 | <= 0 |

3条件をすべて満たしたため`Predictive Collapse=true`である。以前のEffective Rank 1.107745は狭いOOF Intersectionだけが原因ではなく、共通First-level評価ではさらに1へ近づいた。

探索Cycle 2–4のcumulative best metric、QD occupancy、Validated Structure数、Debt数を入力すると、全4停滞条件がCycle 3と4で連続し、Cycle 4で`Exploration Stagnation=true`となった。これはSemantic Collapseとは別の判定である。

## 3. Island 01 Structure Validation Debt

同一80,000 row sample、3 Forward Horizon、同一LightGBM/Seed条件で、ProductCD、14-day Time bin、log2 Amount magnitude、joint decimal residue分布を保持するMatched Nullを20回実行した。

| 指標 | 値 |
| --- | ---: |
| Real mean AUC | 0.872216 |
| Null mean AUC | 0.871013 |
| Null 95%点 | 0.872296 |
| Null >= Real | 2 / 20 |
| Real > Null 95%点 | **False** |

Sequential Futilityは5回時点の結果を事後的な停止根拠にせず20回を完了した。20回時点の`P(p < 0.05 | data)`は0.084918で、sequential early-stop条件自体はfalseだったが、必須のMatched-null 95% Gateは不合格だった。

これによりConfounder-preserving Nullは`failed`、後続のIndependent Implication、Multi-context Replication、Decision Adoptionは`waived_by_failed_prerequisite`となった。Debtは全Requirement処理済みの意味で`resolved`だが、Assessmentは次のままである。

```text
USEFUL_ENCODING_UNVALIDATED_STRUCTURE
structural_validity_passed = false
predictive_improvement_passed = true
confirmed_fact_shareable = false
```

Payment-processの物語は知識へPromotionされず、Feature encodingとしてCandidate Archiveに残すことだけが許可される。

## 4. Cold-start Reliability Replay

3つのAgent branchをそれぞれ新規cloneし、新しいRun RootからCycle 1を逐次Replayした。40,000 train sampleを用いたがtest predictionは全506,691行を必須とした。

| Gate | 結果 |
| --- | ---: |
| First-attempt Valid Artifact Rate | 100% |
| Resource Failure Rate | 0% |
| Final-test Rows | 506,691 / candidate |
| OOF Honesty | 3 / 3 Pass |
| Overall Reliability Gate | **Pass** |

初回Runの4/7 Invalid Artifactは現行Preflight付きCold Replayでは再現しなかった。

## 5. Representation × Learner Transfer Matrix

同じ354,324 OOF行、3 Horizon、3 SeedでLightGBMとCatBoostを全4 Representationへ、Logistic SGDをCanonical Baseへ適用した。

| Representation | LightGBM AUC | CatBoost AUC | CatBoost Gain vs Base |
| --- | ---: | ---: | ---: |
| Canonical Base | 0.895077 | 0.866719 | 0 |
| Island 01 Cycle 4 | 0.898652 | 0.868193 | +0.001473 |
| Island 02 Cycle 2 | **0.902963** | 0.868523 | +0.001803 |
| Island 03 Cycle 2 | 0.898623 | **0.868925** | +0.002206 |

Canonical Logistic SGDは0.790631だった。Learnerを混ぜた全9セルのEffective Rankは1.209649まで上昇したが、best AUC−0.02をQuality Floorとするとeligibleなのは4 LightGBMだけである。全9セルのNested BlendはAUC 0.898001で、best singleに対するGainは−0.004962だった。

| 分解 | Effective Rank |
| --- | ---: |
| Representation diversity within LightGBM | 1.038561 |
| Representation diversity within CatBoost | 1.014900 |
| Learner diversity on Canonical（Logistic含む） | 1.274390 |
| Learner diversity on Island 01（LGBM/CatBoost） | 1.065043 |
| Learner diversity on Island 02（LGBM/CatBoost） | 1.071278 |
| Learner diversity on Island 03（LGBM/CatBoost） | 1.061671 |

H_modelは部分的に支持された。Learner変更は予測差を作るが、今回のCatBoost/Logistic設定ではQuality Floorを満たさずEnsemble Gainへ変換されない。H_representationも支持され、各Learner内では4 RepresentationのResidualがほぼ同一方向である。

Island 01のGainがCatBoostへ正にTransferしたことはPayment-process encodingがLightGBM固有の偶然だけではないことを示すが、Matched Null不合格を覆さず、構造妥当性の証拠には数えない。

この結果に対して`PDD-IEEE-CIS-V031-001`をopenした。次Candidateは具体的なData Sliceと誤差Mechanismを実行前に登録し、AUC 0.882963以上を維持したうえでArchiveの最小Residual Correlation 0.990831を下回るか、Nested Marginal AUC Gainを正にしなければDebtを閉じられない。ControllerはFeatureまたはModel Familyを指定していない。

## 6. 実装Artifact

- Frozen endpoint: `.runs/ieee-cis-v031-primary-endpoint/`
- Common Cross-fit: `.runs/ieee-cis-v031-common-crossfit/`
- Learner Matrix: `.runs/ieee-cis-v031-learner-matrix/`
- Structure Debt: `.runs/ieee-cis-v031-structure-debt/terminal/terminal_report.json`
- Cold Replay: `.runs/ieee-cis-v031-cold-replay/report.json`
- Aggregate report: `.runs/ieee-cis-v031-final-report.json`

Run Artifactはgit管理対象外で、本文書が要約とprovenanceを保持する。実行ScriptとGate実装はリポジトリへ含める。

主要Report SHA-256:

```text
primary_endpoint_results  22a283540786cc5ea110218f2db8b00e796d2a2d1135f18c8f7540507327c1af
common_crossfit_report    1f6c908b718a9a4f2aaaafd475e0f1193f8d0c421b8023162384aa12477613d8
learner_matrix_report     ccd75e1840f20c51151203a51ca3bc614d04cff053c57ebae24a052f78307aad
structure_terminal_report 00bd2e1afc7f53b310163f78b386bf071f88a336028d25a62fedddfbe81a27de
cold_replay_report        59e9d88d8ecc0360090ae6ce54636a531b9c414a67376e839f5e184c8056fda7
aggregate_report          694b9f2206b3030cecbd05a4298c6998a78d6aa16ac288aa815f618c4781d90a
```

## 7. 未完了と次のGate

Matched-budget v0.2/v0.3/改良版比較は、IEEE-CIS Capability Acceptanceと別Competitionが未完了のため未承認である。現在のLate Submission結果を用いてv0.2またはv0.3の一般的優劣を結論してはならない。
