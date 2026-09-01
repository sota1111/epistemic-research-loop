# v0.3.8 Fresh-context Qualification with Machine-audited Provenance

## 結論

v0.3.8 Engineering Qualification は **FAIL**（9 Gate 群のうち 4 Pass / 5 Fail）。ただし v0.3.7 比で
全主要指標が改善し、3 つの Gate 群（Persistent Ladder、Calibration、Transfer）が Fail から Pass へ
転じた。残る Bottleneck は (1) Persistent 系 family の個体発見率、(2) 反証バンドルの内部不整合
（`falsified` 申告と >0.05 の implication strength の共存）による Evidence-based rejection の不成立、
(3) 依然高い Shared Blind-spot である。

| 指標 | v0.3.7 | v0.3.8 | Gate | 判定 |
| --- | ---: | ---: | ---: | --- |
| Median Agent TSDR | 0.0833 | **0.1875** | >= 0.50 | Fail |
| Median Agent TSRR | 0.0208 | **0.1875** | >= 0.67 | Fail |
| Worst Agent FSPR | 0.3333 | **0.2083** | <= 0.20 | Fail（僅差） |
| Shared Blind-spot Rate | 0.7917 | **0.7083** | <= 0.20 | Fail |
| Minimum LOAO TSRR | 0.0000 | 0.0000 | >= 0.67 | Fail |
| Pooled USTR | 0.7500 | **1.0000** | >= 0.50 | Pass |
| Median Structure Gain | +0.0943 | **+0.2209** | > 0 | Pass |
| Median Structure Brier | 0.2614 | **0.1813** | <= 0.20 | **Pass（新規）** |
| Median Structure ECE | 0.1826 | **0.1055** | <= 0.20 | Pass |
| Persistent Ladder levels | 1/4 | **4/4** | >= 3/4 | **Pass（新規）** |
| Persistent discovering agents | 1/3 | **2/3** | >= 2/3 | **Pass（新規）** |

補足値：

```text
Mean Population-union TSDR   0.2083 -> 0.2917
Mean Population-union TSRR   0.0833 -> 0.4583
Discovery Complementarity    0.0208 -> 0.0417
Rejection Complementarity    0.0208 -> 0.1250
C1-calibrated Median Brier            0.1728
C1-calibrated Median ECE              0.0551
TSDR cluster bootstrap 95%            [0.160, 0.236] (8 blocks)
TSRR cluster bootstrap 95%            [0.111, 0.257]
```

### Family 別の個体発見（24 反復中）

```text
observation_routing_composition  23/24   ほぼ完全（v0.3.7: 7/24）
persistent_clear                  2/24   ただし matched_negative 段階の失敗が 12
persistent_noisy_proxy            1/24
persistent_delayed_history        1/24
persistent_compositional          1/24
stable_structure_nonactionable    1/24
```

### Failure Funnel（未発見 Positive 116 件、Controller 判定）

```text
evidence          67  (v0.3.7: 77)
matched_negative  27  (v0.3.7: 10)
promotion         21  (v0.3.7: 45)
```

Controller-adjudicated Stage A–C（proposal artifact から判定）は全 pack で完了しており、
自己申告との乖離はなかった。

### 反証バンドルの内部不整合（v0.3.9 の主対象）

Negative 144 件中、Agent は 122 件を `falsified` と申告したが、Evidence-based rejection に
数えられたのは 27 件だった。棄却が阻止された 95 件の Controller 側理由は：

```text
implication_support を含む     73  （うち単独 40）
research_support を含む        36
confirmation_support を含む    36
```

つまり主因は「`falsified` と主張しながら、同じ提出物の independent_implication_strength が
2 Context 以上で 0.05 を超えている」自己矛盾である。これは Truth を使わずに Lock 前へ
契約検証（自己整合性）として前倒しできる。persistent_clear の matched_negative 失敗 12 件も
この不整合による対 Negative 棄却不成立が主経路であり、修正の期待効果が最も大きい。

False promotion 15 件のうち 8 件は `useful_encoding_without_structure`（予測利得はあるが構造の
ない Family）への Validated 昇格で、「予測利得 ≠ 構造」の罠が残っている。

## 実行設計

```text
4 locked qualification suites (v038-qual-c01..c04)
× 3 generic agent identities
× 2 sampling conditions
= 24 suite-level agent evaluations, each a fresh `claude -p` process
```

v0.3.7 との違いは介入セットのみ：fresh context per run、Null provenance artifact の契約必須化、
P1 単独 Prompt、Lineage 継続の Controller 強制、C1/C2 の Development-only fit、Suite×Seed cluster
bootstrap。Generator families・Pack 設計・Gate 閾値は v0.3.7 と同一。

正本は [Preregistration](../v038_preregistration.json) と [差分仕様](../c_lite_revision_v0.3.8.md)。

## 実行記録

### Development phase（C1/C2 用、Qualification Truth 不使用）

- 6 fresh runs（2 suites × 3 runs、agent×seed バランス割当）を実行。
- 全 6 run が契約検証 Pass。2 run は契約 repair retry 1 回（validation error feedback のみ、Truth 情報なし）。
- 実行時間は 1 attempt あたり約 23–35 分。
- Development lock 後に Development Truth のみ開封し、C1 isotonic map（72 samples）と per-agent
  development ECE を Lock。全 agent の dev ECE ≤ 0.20 のため C2 evidence gate は標準水準
  （2 supporting contexts / 5 null replicates / LOCO 必須）。

### Blindness / Isolation

- Agent view 36 件の禁止 token 監査：0 findings。
- 全 transcript の禁止 path / token 監査：**実質 0**。初回監査で 2 件の hit があったが、内容は
  numpy RuntimeWarning が interpreter（project venv）の site-packages パスを stderr に含めたもの
  で、リポジトリ内ファイルへの読み取りアクセスではない。レビューの上、
  `<interpreter-site-packages>` として allow-list 化した（実 path 言及は引き続き Fail する）。
- 既知の制約：Agent の `python3` は project venv interpreter を解決した（`uv run` 経由の PATH
  継承）。データ・Truth への情報流はないが、interpreter レベルの隔離は Container 隔離と併せて
  今後の課題として残る。Truth は保存時暗号化（鍵 0600）で、transcript にアクセス痕跡はない。
- Container / mount / namespace 隔離ではない（Preregistration どおり）。

### Qualification phase

- 24 fresh run を並列 4 で実行。初回バッチで 12 run 完了後にアカウントのセッション使用上限
  （HTTP 429、resets 17:10 UTC）へ到達し、12 run が失敗。リセット後に同一 workdir で再開し、
  24/24 が契約 Pass（再開分の一部は中断時の部分成果物を含む workdir 上で新規 fresh context が
  完走した。文脈自体の持ち越しはない）。
- 全 transcript（59 件）の Blindness 監査：禁止 path / 禁止 token アクセス 0。
- 24 run Lock → Suite-set / Prompt / Encrypted Truth SHA 再照合 → 開封・集計。

## 結果

上記「結論」の表のとおり。詳細は
[Qualification Result](../v038_qualification_result.json)、
[Scorecards](../v038_agent_reproducibility_scorecards.json)、
[Blind Spots](../v038_population_blind_spot_report.json)、
[Failure Traces](../v038_structure_failure_traces.json)、
[Null Audit](../v038_full_refit_null_audit.json)。

Agent 別（8 反復 pooled）：

| Agent | TSDR | TSRR | FSPR | USTR | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 | 0.2292 | 0.1875 | 0.0625 | 1.0 | 0.1886 | 0.1365 |
| 02 | 0.1875 | 0.2083 | 0.2083 | 1.0 | 0.1813 | 0.1023 |
| 03 | 0.1875 | 0.1667 | 0.0417 | 1.0 | 0.1701 | 0.1055 |

v0.3.7 で見られた「agent-01 だけが限界寄与を持つ」偏りは解消し、3 Agent の成績が均質化した。
Rejection Complementarity は 0.0208 → 0.125 に上がり、population union TSRR は 0.083 → 0.458。

## 帰結（v0.3.9 への引き渡し）

1. **反証バンドルの自己整合性を契約強制する。** `falsified` 申告と >0.05 implication の共存、
   `validated_*` 昇格と <=0.05 implication の共存を Lock 前の契約違反として repair feedback で
   差し戻す（Truth 不使用・構造情報のリークなし）。
2. Persistent 系 family の evidence 段階（46 件）は残る本質的能力課題。介入は Prompt へ構造語彙を
   足さずに行う必要がある。
3. Fresh context 化・Provenance 必須化・Lineage 強制は維持する（本回の改善に寄与した介入セット）。

## 制約

1. Null provenance artifact は Agent 計算値の構造監査（件数・gain 整合・hash 一意性）であり、
   独立再実行による検証ではない。
2. Container 隔離は未実装。
3. Wilson 区間に加えて Suite×Seed cluster bootstrap を報告するが、これも Engineering 用の記述値。
4. 同一 Synthetic Generator 系統内の評価であり、Real Benchmark 一般化は別途。
