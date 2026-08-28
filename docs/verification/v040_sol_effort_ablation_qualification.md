# v0.4.0 Track A Side-probe — Codex Sol Reasoning-Effort Ablation

## 結論

codex sol(gpt-5.6-sol)に対し、CLI・model・prompt arm(P1)・cycle 予算を固定し
**reasoning effort(low/medium/high/xhigh)のみを変えた** 24 run(4 水準 × 6 replicate)の結果:

- **発見イベント数は effort に対して単調増加した:** low 2 件 → medium 3 件 → high 4 件 →
  xhigh **7 件**。事前登録した「単調増加を仮定しない」という前提に反し、実際には明確な
  単調増加が観測された。**「narrowing 仮説」(高 effort ほど収束が早まり多様性が下がる)は
  棄却され、「capacity 仮説」(高 effort ほど held-out 証拠を積み上げる能力が上がる)が
  支持された。**
- **多様性指標(diversity_metrics)も同じ方向に単調増加した。** semantic_family_count:
  1.00 → 1.17 → 1.17 → **1.67**、effective_family_count:1.00 → 1.05 → 1.05 → **1.33**、
  eecr:0.00 → 0.50 → 0.25 → 0.39。narrowing 仮説の副次予測(低 effort の方が仮説多様性が
  高い)も支持されなかった——**発見と多様性がトレードオフになる証拠は見つからなかった。**
- **`persistent_clear` が history 上初めて真に発見された。** gen1(24 run)・scaffold-ladder
  screen(進行中)を含め、このセッションを通じて persistent ラダー L1–L3 の発見は皆無だったが、
  本 ablation の **high(b06)と xhigh(b03)でそれぞれ 1 件ずつ、計 2 件の真の発見**が生じた。
  low・medium では一度も発見されていない。**これは「persistent ラダーの壁は evidentiary
  capacity(held-out 証拠を 0.95 閾値まで積む能力)の問題であり、reasoning effort を上げる
  ことで動く」という v0.4.0 policy 側の仮説を直接支持する、初めての肯定的証拠である。**
- **`high` の false promotion 5 件は全て `v040-solE-b05` の 1 replicate に集中**しており、
  他の 5 replicate は健全だった。gen1 の terra/g03 と同型の「単発の暴走」であり、`high`
  という effort 水準そのものが系統的に過剰確信しやすいという結論は時期尚早。

## 実行記録

- 4 構成(S-low・S-medium・S-high・S-xhigh、いずれも codex/gpt-5.6-sol/P1)× 6 replicate = 24 run。
  `-s danger-full-access` + `-c model_reasoning_effort` 明示指定(世代 1 の sandbox 修正を
  最初から継承)。
- **replicate 数は当初 4 だったが、統計的根拠なく評価器のハードコード制約を避けるための
  数字だったとユーザー指摘を受け、6(policy §3.2 の下限)へ修正**(`evaluate_v037_runs`/
  `evaluate_v038_runs` に `expected_suite_count` 引数を追加、既存呼び出しは無変更)。
  既に実行済みだった最初の 4 suite(16 run)はそのまま活かし、2 suite(8 run)を追加実行。
- 盲検監査:view 24・transcript 37 とも findings 0。24 run 中 24 run が Lock → SHA 再照合 →
  開封。評価器は v0.3.7 系列 verbatim 再利用。

## Effort 水準別結果

| Effort | 発見イベント | 発見 family | False promotion | mean semantic family | mean effective family | mean eecr |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| low | 2 | grammar_a, grammar_b | 0 | 1.00 | 1.00 | 0.00 |
| medium | 3 | grammar_a, grammar_b | 1 | 1.17 | 1.05 | 0.50 |
| high | 4 | grammar_a, grammar_b, **persistent_clear** | 5(1 replicate に集中) | 1.17 | 1.05 | 0.25 |
| **xhigh** | **7** | grammar_a, grammar_b, **persistent_clear** | 1 | **1.67** | **1.33** | 0.39 |

## persistent_clear の発見詳細(6 suite × 4 effort = 24 セルの内訳)

| Suite | low | medium | high | xhigh |
| --- | --- | --- | --- | --- |
| b01 | inconclusive | useful_encoding_unvalidated | validated_non_actionable | falsified |
| b02 | inconclusive | useful_encoding_unvalidated | falsified | useful_encoding_unvalidated |
| b03 | inconclusive | inconclusive | useful_encoding_unvalidated | **validated_actionable_transferred(発見)** |
| b04 | falsified | falsified | falsified | validated_actionable_transferred(発見に至らず) |
| b05 | useful_encoding_unvalidated | falsified | inconclusive | falsified |
| b06 | inconclusive | useful_encoding_unvalidated | **validated_actionable_transferred(発見)** | useful_encoding_unvalidated |

xhigh/b04 は `validated_actionable_transferred` と申告したが Controller 側の behavioral
discovery 判定は通らなかった(過大申告だが matched-negative ではないため false promotion
にはならない)。それでも **6 suite 中 4 つ(b01・b03・b04・b06)で high か xhigh が唯一
`falsified` から離れた resolution を出している**——低 effort では一貫して inconclusive /
falsified / useful_encoding に留まり、真剣に検証しようとした形跡すら少ない。

## 判定と含意

- **事前登録した 3 通りの予測のうち「capacity 仮説」が支持された。** narrowing 仮説(発見と
  多様性のトレードオフ)は本データでは確認されなかった。
- **scaffold-ladder screen の「二問題フレーミング」(仮説生成多様性 vs 証拠能力)に対する
  最初の実証データが得られた。** persistent_clear の発見が high/xhigh に限られたことは、
  「evidentiary capacity(cycle・effort による held-out 証拠の積み上げ)」レバーが
  persistent ラダーの壁を動かす、という仮説を支持する一次データである。
- **次の作業:**
  1. 世代 2 の codex sol 構成には **xhigh を採用**する(発見・多様性・false promotion
     いずれの指標でも最良)。
  2. scaffold-ladder screen(Stage 1、進行中)の sol 側は xhigh 固定であり、本結果と
     整合的に読める設計になっている。Stage 2(cycle 予算 4→8)は persistent ラダー突破の
     再現性を検証する最優先候補になった。
  3. `high` の b05 異常値は、世代 2 以降で再現するか要観察(1 replicate のみでは判断不能)。

## 正本

- [Preregistration](../v040_sol_effort_ablation_preregistration.json)(replicate 数修正の
  事前登録記録を含む)
- [Selection Table](../v040_sol_ablation_selection.json) /
  [Diagnostics](../v040_sol_ablation_diagnostics.json)
- [v0.4.0 方針](../c_lite_v040_policy.md)
