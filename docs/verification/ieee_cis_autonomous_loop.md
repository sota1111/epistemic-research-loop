# 実機検証: IEEE-CIS Fraud Detection での自動起票研究ループ

実施日: 2026-08-24 / 対象コンペ: `ieee-fraud-detection` / Linear プロジェクト: **ERL IEEE-CIS 自動起票検証**

推測は書かない。以下はすべて実際に実行したコマンドとその出力、イベントログ、Kaggle API の応答から
確認した事実である。到達しなかったものは「到達しなかった」と明記する。

## 検証条件

| 項目 | 値 |
| --- | --- |
| データ | Kaggle 公式配布 CSV (train 590,540 行 / test 506,691 行 / 434 列)、`dataset_fingerprint cc0739cc…` |
| ワーカー | `examples/ieee_cis/run_experiment.py`（LightGBM 4.7.0 / pandas 2.3.3、CPU 24 コア） |
| Epistemic arm | `ieee-epistemic-001`、executor `linear_local_worker`（当時）、`configs/verification/ieee_cis_epistemic.yaml` |
| 追検証 | `ieee-cp-verify-001`、executor `ai_dev_control_plane`（実機・後述） |
| Exploiter arm | `ieee-exploiter-002`、executor `local`、`configs/verification/ieee_cis_exploiter.yaml` |
| 提案スロット | `llm.adapter: file_bridge`。**ANTHROPIC_API_KEY が未設定のため Claude Code が提案 JSON を記述した** |
| Leaderboard | `public_feedback: numeric`, `max_public_queries: 5`、private は研究ループから一度も開封していない |

### 情報汚染の統制 — 断言できる部分とできない部分

**断言できる:** 本セッションで WebSearch / WebFetch を一度も呼んでいない。Kaggle Discussion、公開
ノートブック、Winning Solution を読んでいない。起票した実行契約は全件 `network_policy: disabled`。

**断言できない:** `run_experiment.py` の `_uid()` は `card1` + `addr1` + `P_emaildomain` でクライアント
を同定し、`uid_agg` はその uid 別に `TransactionAmt` の平均・標準偏差・件数を作る。IEEE-CIS には
card1 + addr1 + D1n から UID を構成する広く知られた手法があり、その議論は私の学習データに含まれる。
**この列の選び方が第一原理から出たものだと、誠実には主張できない。** 当初この節は「コンペ固有の解法は
実装していない」と書いていたが、それは言い過ぎであり撤回する。

`strict_historical` ソースポリシーは URL を遮断するが、モデルの記憶は遮断しない。**これはこの設計が
構造的に防げない汚染経路である。**

影響の実測（打ち消しにはならないが、規模は記録しておく）:

| 観点 | 実測 |
| --- | --- |
| Epistemic arm の提出が使った特徴 | `base` のみ（uid 系は不使用、public 0.934969 に寄与ゼロ） |
| Exploiter sweep で `uid_agg` が稼いだ CV | **+0.00034**（0.97128 → 0.97162） |
| 素の 434 列だけの提出スコア | **0.934969**（つまり 0.93 台はデータそのものが出す） |
| entity 構造についてループが出した結論 | 全データで 0.005 の価値しかなく、**補正として falsified** |

つまり uid 能力を実装したうえで、ループはそれを採用に値しないと判定した。既知解法へ寄せたのなら
下手な寄せ方だが、**能力セットの設計に記憶が影響した可能性そのものは残る。**

## 誰が何を決めたか

**提案文（仮説・実験設計・どの予測が一致したかの判定）は Claude Code が書いた。** API キーが無いため
自動 LLM アダプタは起動できず、設計上の `file_bridge` 経路を使った。それ以外――スキーマ検証、ハード
ゲート、効用計算、ポートフォリオ選択、反証処分（survives / weakened / falsified / inconclusive）、
log-odds によるビリーフ更新、フェーズ判定、予算計上、Linear 起票――は**すべて決定論的コードが実行
した**。つまり「提案する人」が人手なだけで、「何が証拠として通るか」を決めたのはコードである。

`docs/verification/sot-3053/` の前回検証では同じ理由で `erlctl run loop`（完全無人）が未実行のまま
だった。今回もそこは変わらない。**完全無人ループは依然として未検証である。**

## 実測 1: 1 日あたりのループ回数と Kaggle 提出回数

| 指標 | 実測 |
| --- | --- |
| Epistemic arm のラウンド数 | **16**（要件は 10 回以上） |
| Epistemic arm の実験数 | 提案 21 / **完了 20**（E-HPO-01 は一度も選ばれなかった） |
| 自動起票された Linear イシュー | **20 件**（SOT-3058 〜 SOT-3077、実行された実験ごとに 1 件） |
| Kaggle 提出 | **1 回**（上限 5 回 / 日） |
| Leaderboard 読み取り | 1 回（予算 5 のうち 1 消費） |
| 計上 CPU 時間 / 実ワーカー時間 | 12.85 h（見積り計上） / **0.49 h**（実測、24 コア） |

ローカル採点のみで完結したループが 15 ラウンド、Leaderboard を使ったループが 1 ラウンド。提出を伴わ
ない実験は Kaggle の日次上限を消費しないため、ループの回転数は計算資源だけで決まる。

## 実測 2: 前の結果によって次の Issue が変わったか

これが検証の主眼である。実行された 20 実験の系列を、**なぜその実験になったか**とともに示す。

| # | 実験 | 種別 | 主要指標 | 直前の結果からどう決まったか |
| --- | --- | --- | ---: | --- |
| 1 | E-SPLIT-01 | diagnostic | `validation_gap` 0.0270 | 初期仮説群から効用最大。HPO 候補(0.292)を退けて選択(0.725) |
| 2 | E-ENT-02 | falsification | `validation_gap` 0.0479 | **R1 の反証記録が「entity 重複が交絡」と書いたため**、それを殺す実験を新規起票 |
| 3 | E-COMBO-03 | falsification | `validation_gap` −0.0289 | R2 が H-VAL-TIME を contested に落としたため、加法性を問う実験へ |
| 4 | E-TIME-04 | falsification | `validation_gap` −0.0140 | **R3 が自分の設計欠陥で inconclusive になったため**、評価集合を固定した修正版を起票 |
| 5 | E-ADV-01 / E-DUP-01 | diagnostic | `adversarial_auc` 0.9178 | validation が一段落し、shift 系の効用が相対的に上昇 |
| 6 | E-SHIFT-06 | falsification | `adversarial_auc` 0.8537 | **R5 の反証記録が「時間代理列かもしれない」と書いたため**、D/C ブロックを外した対照を起票 |
| 7 | E-LEAK-05 / E-BASE-07 / E-DUP-01 | diagnostic ほか | `max_univariate_auc` 0.7552 | leakage が唯一の critical 未解決として残ったため |
| 8 | E-ABL-08 | ablation | `roc_auc` 0.9148 | **R7 の subgroup 出力が ProductCD 差(0.16)を露出させ、新仮説 H-PRODUCT-W を生成** |
| 9 | E-SUB-09 | diagnostic | `public_score` 0.9350 | ローカル論証が 8 ラウンド自己参照だったため、**1 提出で外部測定** |
| 10 | E-VAL3-10 | falsification | `validation_gap` 0.0049 | **LB との乖離から新仮説 H-TEST-SHARES-ENTITIES を生成**し、提出ゼロで検証 |
| 11 | E-ABL-11 | ablation | `roc_auc` 0.8999 | V ブロックが無価値と分かり、探索空間が変わったため C/D へ |
| 12 | E-ABL-12 | ablation | `roc_auc` 0.8507 | **R11 が閾値の隙間に落ちたため**、冗長性を直接問う設計に作り直し |
| 13 | E-REP-13A/B | replication | `roc_auc` 0.9245 / 0.8683 | 未再現の所見の上に構築しないため |
| 14 | E-REP-14 | replication | `validation_gap` 0.0046 | entity 効果の訓練量依存を第 3 点で確認 |
| 15 | E-CAT-15 | falsification | counts | **H-PRODUCT-W が 7 ラウンド前に自分で要求した対照**を初めて実施 |
| 16 | E-REP-16 | replication | `validation_gap` −0.0052 | 唯一残った validation 補正が 1 seed 対にしか依っていなかったため |

固定計画の順次実行ではない。**R2・R4・R6・R10・R12・R15 は、直前の実験結果または反証記録が存在しな
ければ書きようがない実験である。**

## 実測 3: KPI 改善以外の実験が選ばれたか

ラウンド 1 の選択ログ（`erlctl experiments select` の出力そのもの）:

```
SELECTED: ['E-SPLIT-01']
  E-SPLIT-01   total=+0.7248  prag=-0.0085 epis=0.950 robu=0.800 dive=0.95 cost=0.023
  E-ADV-01     total=+0.6489  prag=-0.0040 epis=0.850 robu=0.680 dive=0.90 cost=0.025
  E-DUP-01     total=+0.5513  prag=-0.0010 epis=0.750 robu=0.480 dive=0.80 cost=0.014
  E-UNIV-01    total=+0.4958  prag=-0.0010 epis=0.750 robu=0.240 dive=0.75 cost=0.014
  E-HPO-01     total=+0.2916  prag=-0.0110 epis=0.350 robu=0.560 dive=0.20 cost=0.038
```

**期待スコア利得が正なのは E-HPO-01 だけである**（`mean_gain=0.006`）。それが最下位で落ち、期待利得
ゼロの validation 診断が選ばれた。E-HPO-01 は 16 ラウンド通じて一度も選ばれなかった。

完了 20 実験の種別内訳: diagnostic 6 / falsification 6 / replication 5 / ablation 3 / **optimization 0**。
lineage は validation, entity, shift, leakage, gbdt, representation, sampling の 7 系統。同種 HPO の
反復にはなっていない。

## 実測 4: 反証と方針転換

支持だけでなく反証が起きたか。ビリーフ更新の実測（`prior -> posterior`）:

| 仮説 | 経過 | 最終 |
| --- | --- | --- |
| H-VAL-TIME | 0.700 → 0.794 (supported) → **0.700 (contested)** → 0.794 → **0.700 (contested)** | contested |
| H-ENTITY-LEAK | 0.650 → 0.754 → 0.835 → 0.754 (contested) → **0.530 (falsified)** | falsified |
| H-LEAK-FEATURE | 0.400 → **0.197 (falsified)** → 0.083 | falsified |
| H-FEATURE-V | 0.550 → 0.611 (contested) → **0.366 (falsified)** | falsified |
| H-PRODUCT-W | 0.600 → 0.658 → 0.761 → 0.658 → **0.415 (falsified)** | falsified |
| H-TEST-SHARES-ENTITIES | 0.600 → **0.356 (falsified)** | falsified |
| H-SHIFT-COVARIATE | 0.600 → 0.712 → 0.803 | supported |
| H-REPR-HISTORY | 0.650 → 0.650 (inconclusive) → 0.754 → 0.835 | supported |
| H-VAL-TRANSFER | 0.750 → 0.750 | retired（測定器が問いに答えられないと判明したため） |

9 仮説中 **5 が反証、2 が contested、1 が retired**。研究方針が結果で変わった具体例:

- **R2**: H-VAL-TIME が supported から contested へ落ち、`validation_locked` が自動で false に戻った。
  一度「解決済み」とした問いをループが自分で再開している。
- **R8**: V ブロック 339 列の除去コストが 0.0013（seed ばらつき 0.0034 未満）。「V に信号がある」という
  想定が反証され、探索空間から 78% の列が外れた。
- **R10**: LB との乖離から生成した仮説が自分で反証され、さらに**比較手法そのものの欠陥**（訓練データ量
  の交絡）を露出させた。R9 の解釈も同時に無効化されている。
- **R14**: entity 補正の効果が 200k 行で 0.0479、300k 行で 0.0046、590k 行で 0.0049。R2 の測定は
  「entity 分割」と「時系列順序の放棄」を同時に変えていたと判明し、**10 ラウンド分の帰属が訂正された**。
- **R15**: H-PRODUCT-W が R8 で自分に課した対照（カテゴリ別件数）を初めて実施したところ、C=732 行、
  H=642 行、R=1298 行、W=6268 行。「0.16 のカテゴリ差」は小標本ノイズだった。**自分の過剰主張を
  自分で撤回している。**

## 実測 5: Leaderboard とローカル評価の乖離

1 提出のみで得た外部測定を、最適化対象ではなく Observation として扱った。

| 推定 | 値 | public score との差 |
| --- | ---: | ---: |
| random k-fold（全データ） | 0.9509 | 0.0159 |
| time-ordered holdout（全データ） | 0.9150 | 0.0200 |
| time+entity separated（全データ） | 0.9101 | 0.0249 |
| **Kaggle public score** | **0.934969** | — |

乖離の向きが重要で、**最も楽観的なスキームが最も近い**。R10 はこれを「分割の忠実さ」ではなく
「各スキームが訓練から取り除くデータ量」の単調な反映と読み、比較手法自体を無効と判定した
（提出モデルは 100%、random 3-fold は 67%、holdout 系は約 80% で訓練している）。
この判定によって H-VAL-TRANSFER は答えの出ない問いとして retired になった。

private score は研究ループから一度も開封していない。`erlctl kaggle feedback` は `redact_private` を
通すため、numeric モードでも private は返らない。

### 記録すべき汚染事象

`kaggle competitions submissions` を診断目的で直接叩いた際、**その出力に private score が表示された**。
ループの経路（submit → seal → feedback）は private を遮断するが、生の Kaggle CLI は遮断しない。
この値は以降のいかなる提案・仮説・実験設計にも使用していないが、「オペレータが素の CLI を叩けば
private が見える」ことは設計上の穴として記録する。

## 実測 6: フェーズ遷移 — 到達しなかった

**Research から Exploitation への遷移は、この run では起きなかった。** 機構は実装され単体テスト済み
（`tests/unit/test_phase_evidence.py`, `tests/integration/test_exploiter_handoff.py`）だが、この run は
discovery に留まった。理由は推測ではなく算術である。最終ラウンド時点の派生証拠:

```
ablations_complete: true      critical_leakage_resolved: true
search_space_defined: true    stable_lineages: 6
validation_locked: true       anomaly_detected: false
mean uncertainty 0.379  (閾値 0.35)
```

6 条件のうち 5 が真で、残るのは平均不確実性のみ。active 仮説は H-VAL-TIME (0.700 → 不確実性 0.600)、
H-SHIFT-COVARIATE (0.803 → 0.394)、H-REPR-HISTORY (0.835 → 0.331)。閾値 0.35 は「active 仮説が平均で
信頼度 0.825 以上」を要求する。**この run はそこに届かなかった。届かなかった理由は、2 つの validation
補正が両方とも再現試験で縮んだからである**（entity 0.0479→0.0046、temporal 0.0140→0.0052）。

これは機構の失敗ではなく、機構が意図どおり働いた結果と読むべきである。再現していない所見の上で
exploitation を始めないのがフェーズポリシーの目的だからだ。ただし**遷移そのものは実運用で未確認**で
あり、そう記録する。

なお `uncertainty_threshold=0.35` は `decide_phase` の引数既定値であり、設定ファイルから変更できない。
これは設定可能にすべき箇所である（未修正）。

## 実測 7: Exploiter-only との対比 — **Leaderboard では Exploiter が勝った**

同一データ・同一ワーカー・同一予算設定・各 1 提出。詳細は
[ieee_cis_arm_comparison.md](ieee_cis_arm_comparison.md)。

| 指標 | Epistemic | Exploiter-only |
| --- | ---: | ---: |
| **Public leaderboard score** | 0.934969 | **0.938967** |
| 自分が判断に使っていた推定値 | 0.9101 | 0.9721 |
| **較正誤差（推定 − 実測）** | **−0.0249** | **+0.0331** |
| 完了実験数 | 20 | 20 |
| うちスコアを上げられない実験 | 20 (100%) | 0 (0%) |
| 探索した lineage 数 | 7 | 2 |
| ワーカー実時間 | 0.49 h | 2.81 h |
| 見積もりに対する実消費比 | 0.63x | 3.12x |

**結論を曲げずに書く: 最終 Leaderboard スコアでは Exploiter が 0.0040 上回った。** 20 ラウンドの
チューニングが未チューニングのベースラインに勝ったのであって、これはチューニングの目的そのもので
ある。Epistemic arm は最後までモデルを調整していない。discovery に留まり、研究が支持する
未チューニングの全データ・ベースラインを提出した。**したがってこれはチューニング済みモデルと
未チューニングモデルの比較である。**

差が出たのは較正の側である。Exploiter は自分が 0.9721 だと信じていて実際は 0.9390、
つまり **0.033 過大評価**していた。Epistemic は 0.9101 だと信じていて実際は 0.9350、
**0.025 過小評価**していた。誤差の大きさは同程度だが向きが逆で、過大評価は隠れ split が
現れたときに順位を失う側の誤りである。

もう一点、**予算の等価性は名目上しか成立していなかった**。両アームとも全てのバジェットゲートを
通過したが、実消費は 0.49 h 対 2.81 h（5.7 倍）だった。ゲートは提案が申告した見積もりを課金し、
`BudgetManager.reconcile` は no-op のままである。貪欲 HPO は「木を 400 本足す」が毎回安く見えて
累積するため、系統的に過少申告する。

## 実測 8: 発見された構造

スコアを上げる能力ではなく、未知の構造を発見する能力の実測。

1. **V ブロック(339 列)は C/D 履歴ブロックと冗長。** 単独除去コスト 0.0013、C/D 単独除去 0.0162、
   3 ブロック同時除去 **0.0654**（個別和 0.0175 の 3.7 倍）。seed 37/53・300k 行で 0.0562 として再現。
   超加法性は冗長性の署名であり、どちらか一方があれば信号は保たれる。**表の 78% を無料で捨てられる。**
2. **train/test は時刻を除いても 0.8537 で分離可能。** D/C ブロックを外しても残るため、単なる時刻の
   言い換えではない。ただし残差は真の covariate shift の上界であって測定値ではない。
3. **entity 重複率 83%、完全重複行 0%。** ただし entity 分離の価値は訓練量に依存し、全データでは
   0.005（seed ばらつき以下）。R2 の 0.048 は別の対比を測っていた。
4. **単一列 leakage は存在しない**（最強列 0.7552 < 0.80）。2 回の独立実行で完全一致。

これらはいずれも「スコアを上げる」実験からは出てこない。1 と 3 は探索空間と検証設計を変えた。

## 実測 9: control plane 実機での往復 — 当初は 1 件も実行されていなかった

**当初の 20 件は control plane が 1 件も実行していない。** 使った executor は `linear_local_worker`
（今回書いた検証用ハーネス）で、Issue の起票は実物、実行はローカルプロセスの代行だった。

さらに悪いことに、**起票した 20 件は control plane 側で無限リトライを起こしていた。**

```
[RUNNER] issue=SOT-3059 no repo mapping for project="ERL IEEE-CIS 自動起票検証" (fail-closed)
[RUN]    issue=SOT-3059 stderr: REPO_RESOLUTION_UNAVAILABLE: ...
```

`auto_runner.log` 内の同エラーは **2,252 行**に達していた。原因は私のプロジェクト命名である。control
plane は Linear プロジェクト名を slugify して `/workspaces/<slug>` を checkout として導出する
（`src/lib/projectRepo.ts`）。`ERL IEEE-CIS 自動起票検証` は `erl-ieee-cis` に落ち、そのパスは存在しない。
`TARGET_REPO=` 行は本文に**入っていた**が、ルーティングには使われない。

### 是正と実機での往復（実測）

1. 起票していた 21 件（SOT-3058〜3078）を Linear API で削除。削除後 45 秒でエラー増加は 0 になった
2. プロジェクトを `Epistemic Research Loop` に改名（slug `epistemic-research-loop`、実在する checkout）
3. executor を `ai_dev_control_plane` に変更
4. 1 件起票 → **webhook が契約を拒否**: `request_id must be a non-empty string`

4 は私が今回入れた「結果テンプレート」が原因だった。control plane は本文の**最初の** ```json ブロック
を実行契約として読む（`src/lib/experimentRequest.ts` の `/```json\s*([\s\S]*?)```/`）。テンプレートを
契約の前に置いたため、契約が読めなくなっていた。**起票は成功し、実行だけが静かに落ちる**種類の不具合
である。契約を先頭に戻し、回帰テストで固定した。

再起票（SOT-3080）後の実測ログ:

```
[RUNNER] issue=SOT-3080 resolved target repo: project="Epistemic Research Loop" -> /workspaces/epistemic-research-loop
[RUNNER] issue=SOT-3080 auto-linked project="Epistemic Research Loop" -> sota1111/epistemic-research-loop (persisted)
[RUN]    issue=SOT-3080 == Auto Runner: script-driven role pipeline ==
[WORKER_ROLES] issue=SOT-3080 per-issue override: solo=claude:opus | handoff=off
```

worker（`claude:opus`）がコマンドを実行し、`ExperimentResult` を書き戻した:

```json
{"experiment_id":"E-CP-01","attempt":2,"status":"completed","exit_code":0,
 "metrics":{"entity_overlap_rate_across_split":0.8282,"row_duplicate_rate_across_split":0.0},
 "runtime":{"wall_seconds":3.75},"external_ref":"SOT-3080"}
```

値は私がローカルで測った 0.8282 / 0.0 と完全一致し、ループは `OB-703c5f8eeef4` として取り込んだ。
**ループ → Linear 起票 → control plane → worker 実行 → 結果書き戻し → Observation の往復が実機で成立
したのは、この 1 件だけである。**当初の 20 実験はローカル代行のままであり、そこは作り直していない。

## 実測 10: 追跡可能性

全 321 イベントがハッシュ連鎖付き JSONL に記録されている。

```bash
uv run erlctl run status  --run-id ieee-epistemic-001   # フェーズ・派生証拠・validation reuse・予算
uv run erlctl run replay  --run-id ieee-epistemic-001   # イベント再生
uv run erlctl hypotheses graph --run-id ieee-epistemic-001
uv run erlctl experiments history --run-id ieee-epistemic-001
uv run erlctl report run  --run-id ieee-epistemic-001
uv run erlctl holdout status --run-id ieee-epistemic-001
```

各実験は Linear イシュー番号（`external_ref`）を Observation に持つため、
イベント → 起票された Issue → 実行契約 → 成果物 → 反証記録 → ビリーフ更新が一本で辿れる。

## この検証で見つかり修正した欠陥

研究そのものとは別に、ループ側の実欠陥を 5 件検出した。いずれも修正しテストを追加した。

1. **`dispatch` が状態遷移を検証する前に attempt を記録していた。** 拒否された dispatch が実験を
   `running` にしてしまい、以後 attempt 番号を消費しないと再試行できなくなる。
   → 先に遷移、後に記録。`tests/integration/test_controller.py`
2. **`kaggle submit` が採点待ちの後にしか台帳へ書いていなかった。** タイムアウトで**提出は消費された
   のに記録が残らず**、日次上限の計上が狂う。実際にこの検証で 1 件失われた。
   → 受理直後に記録。`erlctl kaggle reconcile` で復旧可能に。
3. **Kaggle CLI の出力から submission reference を誤検出していた。** アップロード進捗の数字を ID と
   誤読し、存在しない ID を待ち続けて 600 秒使い切る。→ 6 桁以上のみ採用、外れたら最新行にフォール
   バック。`tests/unit/test_kaggle_cli_adapter.py`
4. **`max_consecutive_optimization_experiments` が設定に存在するのにゲートが読んでいなかった**（3 を
   ハードコード）。このため **exploiter-only アームがラウンド 4 で構造的に停止し、A/B 比較が成立
   しなかった**。→ 設定を貫通、0 で無効化。`tests/unit/test_hard_gate.py`
5. **`beliefs update` が 1 ラウンド 1 仮説しか扱えなかった。** 1 つの結果が複数仮説に効く場合に
   `parsing → falsifying → updating` を二度通ろうとして失敗する。→ 2 パス化（autoloop と同じ順序）。
6. **`FINALIZING` に到達する経路が存在しなかった。** 最終提出は実験ではない――情報を買わず、最も高価
   な学習であり、Exploiter の実用重視の重みでは効用 **−0.0328** となって**セレクタが自分自身の最終
   提出を拒否した**。成果物をループの記録の外で作るしかない状態だった。→ `run finalize` を追加。
7. **予算ゲートが実消費を見ていない。** `BudgetManager.reconcile` が no-op のため、見積もりが楽観的
   な run は名目予算の数倍を消費できる（実測 3.12 倍）。→ `run status` に観測実時間と比率を表示。
   ゲート側の課金修正は未実施。

## 検証していないこと

- **完全無人ループ (`erlctl run loop`)。** API キーが無く未実行。提案は人手（Claude Code）である。
- **ai-dev-control-plane による 20 実験の再実行。** 実機往復は `ieee-cp-verify-001` の 1 件のみ確認
  した。本文の実測 1〜8 が依拠する 20 実験は `linear_local_worker`（ローカル代行）のままである。
- **private score による最終評価。** 研究ループからは開封していない。
- **Research → Exploitation 遷移**（上記のとおり到達せず）。
- **複数回の paired run**。今回は N=1（1 コンペ・各アーム 1 提出）であり、対照実験ではあっても
  ベンチマークではない。手法の優劣を主張できる設計ではない。

---

# 追検証: ai-dev-control-plane による 10 往復（`ieee-cp-verify-001`）

実施日: 2026-08-24〜25 / executor: **`ai_dev_control_plane`**（ローカル代行なし）

本編 20 実験は `linear_local_worker`（ローカル代行）だった。ここでは **実装を完全に
ai-dev-control-plane に委ね**、ループ → 起票 → control plane → worker → 結果 → Observation を
**10 往復**実測した記録である。

## 10 往復の実測

| # | 実験 | Linear | 問い | 結果 |
| --- | --- | --- | --- | --- |
| 1 | E-CP-01 | SOT-3080 | 時系列分割をまたぐ entity 重複率 | 0.8282 / 行重複 0.0 |
| 2 | E-TIME-R1 | SOT-3082 | 評価ブロックを広げれば temporal 効果は分解できるか | **0.02238**（seed 間レンジ 0.0118） |
| 3 | E-MODEL-R2 | SOT-3085 | V 冗長性は線形モデルでも成り立つか | V 除去コスト 0.0350 |
| 4 | E-SHIFT-R3 | SOT-3086 | shift は少数列が担うか | 0.8499（上位8列除去で 0.0038 のみ低下） |
| 5 | E-CTRL-R4 | SOT-3087 | 同サイズのランダム列除去はいくら掛かるか | **0.0535**（V より高い） |
| 6-10 | E-ORD-A〜E | SOT-3088〜3092 | 5 候補のローカル値と隠れスコア | 下表 |

起票→実行→書き戻しはすべて control plane の `claude:opus` worker が行った。ループ側は
`status: queued` を受け取って result store をポーリングしただけである。

## 発見 1: 前回の temporal 結論は「効果が無い」ではなく「測れていなかった」

本編 R16 は temporal 効果が 0.0140 → 0.0052 に縮み、片方の seed が 0.0008 だったことから
H-VAL-TIME を weakened にした。しかし両測定とも評価ブロックが数千行しかなかった。
全データで holdout を 40% に広げ 4 seed で測ると **0.02238（seed 間レンジ 0.0118）**、
4 seed すべてが 0.0156〜0.0274 で閾値超え。**縮小は分解能不足であって不在ではなかった。**
本編の「validation 補正は両方とも再現に失敗した」という結論は半分誤りである。

## 発見 2: V ブロック冗長性は木モデルの性質（ただし相対的には冗長）

線形モデルで V を除くと 0.0350 掛かる（木では 0.0013）。R2 はこれを「冗長性は木の性質」と
判定したが、その反証記録自身が対照を要求していた。R4 で **同サイズのランダム 339 列**を除くと
**0.0535** — V より高い。つまり V は「平均的な列より情報が少ない」が「無料ではない」。

正直な位置は、これまでのどの主張よりも狭い: **V は両モデル族で相対的に冗長、絶対的に冗長なのは
木だけ。** 本編の「78% を無料で捨てられる」はデータの事実として述べられていたが、そうではない。

## 発見 3: ローカル CV は候補を順位付けできない（rank correlation 0.000）

5 候補を採択済み split で測り、**ローカル順位をイベントログに確定させてから** public を開封した。

| 候補 | 内容 | local | public |
| --- | --- | ---: | ---: |
| A | base | **0.893392** (1位) | 0.934969 (4位) |
| D | base / 1000木 lr0.03 | 0.889952 (2位) | **0.937832** (1位) |
| E | freq_enc | 0.887245 (3位) | 0.935898 (3位) |
| C | no_v | 0.883226 (4位) | 0.932155 (5位) |
| B | uid_agg | 0.878035 (5位) | 0.936254 (2位) |

**Spearman rank correlation = 0.000。** ローカル最下位の B が public 2位、ローカル1位の A が 4位。

前回 run は「水準の比較」を訓練量交絡で答えの出ない問いとして retired にした。今回「順位の比較」は
答えが出て、**否定**だった。実務上の帰結は、この run のローカル推定は隠れスコアの水準も予測できず、
近接した候補の選択にも使えない、ということである。

**限界を明記する。** 5 候補のローカル幅は 0.0154、public 幅は 0.0057 で、この run で測った
single-seed ノイズ 0.003〜0.012 と同程度である。**示せたのは「これほど近接した候補を順位付けできない」
ことであって、大きく異なる候補を順位付けできないことではない。** 各候補 1 seed という設計上の
トレードオフ（幅を優先）も効いている。

## この追検証で見つかり修正した欠陥（本編の 7 件に追加）

8. **`FINALIZING` に到達する経路が無かった**（本編に記載済み、ここで実装）
9. **遅れて届いた結果を取り込めなかった。** timeout → replan 後に result.json が現れると、実験は
   `running` のまま孤児になり計算が捨てられる。非同期 worker では日常的に起きる。
10. **standing な候補プールを再スコアリングできなかった。** `scoring` に入るには新規提案が必須で、
    事前登録した候補集合を 1 件ずつ消化できない。ループが「欲しくない実験」を発明する羽目になる。
11. **選択済みで dispatch されなかった実験が宙に浮いた。** `selected` なので再選択されず、
    `selecting` を過ぎているので dispatch もできない。決定を守るのではなく捨てていた。
12. **結果テンプレートが `external_ref` を欠いていた。** worker が自発的に書いた 6 件しか
    Observation → チケットの追跡が成立せず、10 往復中 4 件が追跡不能だった。
13. **チケットが「スキーマは閉じている」と言っていなかった。** worker が `notes` を足し、
    `extra=forbid` で結果全体が拒否された（実験は実行済みだったので計算が無駄になった）。
14. **実行契約が最初の ```json ブロックでなければならないことを、私が壊した。** 結果テンプレートを
    契約の上に置いた結果 `request_id must be a non-empty string` で webhook に拒否され、
    「起票成功・実行されず」になった。

## 予算

計上 1.905 wall-hours に対し実測 1.035（比 0.54）。Kaggle 提出 5/5（UTC リセット後の満枠）。
