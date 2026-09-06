# 反例 `−1` の再現 — 結果

**作成:** 2026-09-06
**規則:** [coding_rules_v2_counterexample.md](coding_rules_v2_counterexample.md)(**当てはめ前に確定・commit 済み**)
**当てはめ:** `scripts/fit_world_model_counterexample.py` → [world_model_counterexample.json](world_model_counterexample.json)
**一次版:** [results.md](results.md) は変更していない。corpus のラベルも 1 件も触っていない

---

## 1. 事前登録した判定の結果 — **点予測としては不採用**

leave-one-domain-out、38 コンペ × 13 状態 = 494 セル、対応ありブートストラップ 10,000 回、seed 20260906。

| 予測子 | 一致率 | 平均対数損失 | `−1` 再現 | `+1` 再現 |
| --- | ---: | ---: | ---: | ---: |
| チェックリスト | 0.8462 | 0.4652 | 0/6 | 22/78 |
| **context 条件付け(一次版)** | **0.8745** | **0.4318** | **0/6** | **31/78** |
| 2 部モデル(決定性 × 向き) | 0.8664 | 0.4420 | **0/6** | 24/78 |

差(2 部モデル − 一次版):

| | 差 | 95% 区間 |
| --- | ---: | --- |
| 一致率 | **−0.0081** | [−0.0223, +0.0061] |
| 平均対数損失(小さいほど良い) | **+0.0103** | **[+0.0027, +0.0174]** |

| 事前登録した基準(§4) | 結果 |
| --- | --- |
| (a) 反例を 1 件以上再現する | **満たさない**(`−1` と予測したのは 2 セル、いずれも外れ) |
| (b) 一致率の差の区間下限 ≥ −0.01 | **満たさない**(下限 −0.0223) |

**したがって、事前登録した規則どおり 2 部モデルを点予測形式としては採用しない。**

**さらに強い結果が出ている。**対数損失の差の 95% 区間は **0 をまたがない** ——
2 部モデルは分布の当てはまりでも**一次版より悪い。**
「反例の再現と一致率のトレードオフ」ではなく、**この再パラメータ化自体が負けている。**

## 2. なぜ再現できなかったか

`−1` の 6 セルは 4 コンペに集中している。

| コンペ | domain | 状態 |
| --- | --- | --- |
| Mercari Price Suggestion | nlp | RMC, SED |
| Bengali.AI Handwritten Grapheme | cv | RMC |
| Planet Amazon | cv | PB |
| DSTL Satellite Imagery | cv | SED |
| Quora Insincere Questions | nlp | PB |

**6 件すべてが cv / nlp にある。**そして [results.md](results.md) §1 が既に測っていたとおり、
**context 特徴 3 つ(temporal / entity / decomposable)は cv / nlp でほぼ定数**である。
反例が存在する当の領域で、条件付けに使える情報が無い。

これは cv 保留 fold の `τ` に露骨に出た。`τ` は学習側だけで決めるが、cv を保留すると
学習側の `P(−1)` 上位が **0.087 の同点の塊**になり、事前登録した「同点の塊ごと落とす」
処理で `τ = ∞`(= `−1` を出さない)になった。**セルが反例を分離していない。**

> **反例が再現できないのは corpus のせいでも縮約のせいでもなく、
> [results.md](results.md) §1 で既に見えていた穴 —— cv / nlp に効く context 特徴が無い ——
> と同じ 1 つの穴である。**§3 の作業 7 を通らない限り、作業 6 は点予測としては通らない。

## 3. 採った形 — 分布に `P(−1)` を持たせる

事前登録した §4 のとおり、点予測が `−1` を出せなくても
**world model の出力は反例の確率質量を明示的に持つ。**
`world_model_counterexample.json` は状態 × context セルごとに
`p_mentioned` / `p_minus` / `p_counterexample` を持つ。

corpus 全体での向き(`p_minus` = 決定的だったとき、それが反証である確率):

| 状態 | 観測 `+1` | 観測 `−1` | `p_mentioned` | **`p_minus`** |
| --- | ---: | ---: | ---: | ---: |
| **Performance Belief** | 0 | 2 | 0.075 | **0.75** |
| **Solution / Error Diversity** | 5 | 2 | 0.200 | **0.33** |
| **Representation / Model Coverage** | 22 | 2 | 0.625 | **0.12** |
| Validation Fidelity | 11 | 0 | 0.300 | 0.08 |
| Entity & Temporal Integrity | 15 | 0 | 0.400 | 0.06 |

**これがチェックリスト化を防ぐ仕掛けの実体である。**
「Representation Coverage は 38 コンペ中 22 回決定的」だけを渡せばチェックリストになる。
**「決定的だったとき、8 回に 1 回は逆向きだった」を同じ数値として渡せば、ならない。**
Performance Belief に至っては **決定的だった 2 回とも反証**であり、
「Public LB を性能推定と同一視できない」という向きでしか corpus に現れない。

**点予測の argmax は、この情報を必ず捨てる。**だから世界モデルを使う側は
**分布を読むこと。**`world_model.json` / `world_model_counterexample.json` のどちらも、
点ラベルへ潰した時点で反例は消える。

## 4. 観測 0 の状態に、縮約は数値を返す(読み違え防止)

`HCAL` と `FC` は 38 コンペ中の観測が **0** である([results.md](results.md) §2.4)。
それでも縮約は `p_mentioned = 0.025`、`p_minus = 0.5` を返す。**これは証拠ではなく事前分布である。**
読み違えを防ぐため、`world_model_counterexample.json` は状態ごとに
`observed: {decisive, counterexample, competitions}` を並べ、
`unobserved_states: ["HCAL", "FC"]` を明示する。

**この 2 つは C-lite を B から区別する当の構成要素であり、corpus からは決して埋まらない。**
実験(§3 の作業 12)だけが埋める。

## 5. 制約

- **符号化者は依然 1 名。**独立符号化の一致率は未測定(§3 の作業 5)。
  本追補の産物も **Preferred State の既定値としてコードへ組み込まない**
  ([coding_rules.md](coding_rules.md) §7)。実装側では
  `DEFAULT_PREFERRED_TARGETS` を撤去し、目標値は**欠測**として扱うようにした(§3 の作業 8)
- 一次版の判定(context 条件付け > チェックリスト)は**変わらない。**本追補は
  一次版を置き換える提案として立てられ、**その提案が自分の事前登録基準で落ちた**
- 次に効くのは作業 7(cv / nlp に効く context 特徴)である。**ただし n=38 で特徴を増やすと
  過学習するので、増やすなら事前登録し直すこと**
