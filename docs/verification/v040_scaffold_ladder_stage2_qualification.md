# v0.4.0 Track A Side-probe — Opus + Sol Scaffold-ladder Stage 2 (Confirmatory)

## 結論

Stage 1(n=4)の 3 つの未確認結果を policy §3.2 推奨の 6 replicate で再現確認した結果:

- **`persistent_delayed_history`(88 run を通じて 0 件だった唯一の family)が、opus×P1 と
  opus×P3 の両方で真に発見された。** これでこのセッションを通じて **persistent ラダーの全 4
  段階が、少なくとも一度は真に発見された。** 発見は各構成 1/6 replicate(opus×P1: `d02`、
  opus×P3: `d06`)で、依然として低頻度だが、もはや「一度も破られていない壁」ではない。
  **さらに opus×P3 は同じ 6 replicate 中で `persistent_clear` も発見しており**、1 構成が
  2 つの異なる persistent family を発見した初めての事例になった。
- **sol×P3 の false promotion は Stage 1 の 7 件(1 suite 集中)→ Stage 2 で 0/36 に消失。**
  単発の暴走だったという仮説が確認された。P3 が sol の calibration を系統的に悪化させる
  という懸念は解消してよい。
- **opus×P3 の多様性ブーストは、方向は再現したが効果量は大幅に縮小した。**
  mean semantic_family_count:Stage 1 8.75 → **Stage 2 4.33**(6 replicate 全て 3–6 の
  狭いレンジ、Stage 1 の 6–12 という広いレンジより大幅に低い)。opus×P1(3.67)との差は
  依然としてプラスだが、「3 倍」ではなく「+18%程度」——**n=4 のスクリーニング推定値は
  効果量を過大評価していた。** これは正しく確認世代を挟んだからこそ検出できた誤り。

## 実行記録

- 3 構成(opus×P1・opus×P3・sol×P3×xhigh)× 6 replicate = 18 run。新 Suite
  (`v040-scaf2-d01..d06`、master seed 20260929)。
- 盲検監査:view 18・transcript 28 とも findings 0。全 18 run 一発で Lock 通過(契約 repair
  不要)。
- **開封時に評価器の潜在バグを発見・修正:** `evaluate_v037_runs` の `agent_seed_aggregates` が
  `agent_id × sampling_seed` の**全直積**を仮定しており、Stage 2 のような非対称スロット構成
  (`agent-02-s17` が存在しない)でゼロ除算を起こした。実際に提出された `(agent_id, seed)`
  組み合わせのみを走査するよう修正。**既存の全 3 study(gen1・Stage 1・sol ablation、いずれも
  対称な full-grid 設計)で再実行し、出力が bit-for-bit 完全一致することを確認**したうえで
  適用(後方互換性を主張ではなく実測で保証)。

## 構成別結果(Stage 1 → Stage 2 比較)

| 構成 | 発見イベント(S1→S2) | mean semantic family(S1→S2) | False promotion(S1→S2) | persistent_delayed_history |
| --- | --- | --- | --- | --- |
| T2-opus-P1 | 9(n=4)→ **13**(n=6) | 3.00 → 3.67 | 0 → 0 | **discovered=true**(1/6) |
| T2-opus-P3 | 9(n=4)→ **14**(n=6) | **8.75 → 4.33**(縮小) | 0 → 0 | **discovered=true**(1/6) |
| T2-sol-P3 | 5(n=4)→ 10(n=6) | 1.25 → 1.50 | **7 → 0**(消失) | discovered=false |

発見イベント数はいずれも replicate 数の増加(1.5 倍)にほぼ比例して増加しており、Stage 1 の
順位(opus-P1≈opus-P3 > sol-P3)は安定して再現した。

## persistent 系発見の詳細

| 構成 | family | suite | resolution |
| --- | --- | --- | --- |
| T2-opus-P1 | persistent_delayed_history | d02 | `validated_actionable_transferred`(discovered) |
| T2-opus-P3 | persistent_delayed_history | d06 | `validated_actionable_not_transferred`(discovered) |
| T2-opus-P3 | persistent_clear | d05 | `validated_non_actionable`(discovered) |
| T2-sol-P3 | persistent_compositional | d02 | `validated_actionable_transferred`(discovered) |
| T2-sol-P3 | persistent_noisy_proxy | d01 | `validated_actionable_transferred`(discovered) |

他の replicate は falsified / inconclusive / useful_encoding_unvalidated に留まる。6 replicate
中 1〜2 という発見率は他の study の既知の発見率と同程度で、**「壁」ではなく「低確率で起きる」
性質**であることが裏付けられた。**opus×P3 は 1 構成で 2 つの異なる persistent family を
同時に発見した初めての事例**であり、sol×P3 も persistent_compositional・persistent_noisy_proxy
という sol 系では初めての 2 family を発見している——P3(自己批判)scaffold が、モデルを
問わず persistent 系発見の主要な経路になりつつある。

## 判定

- **cycle-budget ablation(この直後に起動)の意義が一段と高まった。** persistent_delayed_history
  が opus(P1・P3 とも、cycle=4)で発見できることが分かった以上、「evidentiary capacity は
  cycle 数を増やせばさらに底上げできるか」という問いに直接答えられる。
- **opus×P3 を無条件で「多様性 3 倍」として世代 2 に持ち込むのは誤り。** 実際の効果量
  (+18%程度)を前提に、世代 2 の設計判断を修正する必要がある。
- **世代 2 の暫定候補は変わらず opus×P1・opus×P3・sol×P3×xhigh(またはより単純な sol×P1×xhigh)。**
  ただし opus×P3 の優位性は「発見イベント数では同点、多様性ではわずかに上回る」という
  正確な言葉遣いに改める。

## 正本

- [Preregistration](../v040_scaffold_ladder_stage2_preregistration.json)
- [Selection Table](../v040_scaffold_stage2_selection.json) /
  [Diagnostics](../v040_scaffold_stage2_diagnostics.json)
- [発見台帳](../v040_discovery_ledger.md)(要更新)
