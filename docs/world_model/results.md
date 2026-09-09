# 世界モデル 一次版 — 結果

**作成:** 2026-09-06
**規則:** [coding_rules.md](coding_rules.md)(符号化前に確定・commit 済み)
**符号化:** [corpus_coding.json](corpus_coding.json) — 38 コンペ × 13 状態
**当てはめ:** `scripts/fit_world_model.py` → [world_model.json](world_model.json)

---

## 1. 事前登録した判定の結果

leave-one-domain-out、38 コンペ × 13 状態、対応ありブートストラップ 10,000 回。

| 予測子 | 一致率 |
| --- | ---: |
| **チェックリスト**(context を無視した多数決) | 0.8462 |
| **context 条件付け**(temporal / entity / decomposable) | **0.8745** |
| 差 | **+0.0283**、95% 区間 **[+0.0121, +0.0466]** |

**区間が 0 をまたがない。事前登録した基準で、context 条件付けはチェックリストに優る。**

`research_models.md` §247 の主張 —「Preferred State は固定ベクトルではなく
context 条件付き分布として扱うべき」— は、**保留した domain に対して成立した。**

### domain 別

| domain | n | context | チェックリスト | 差 |
| --- | ---: | ---: | ---: | ---: |
| forecasting | 6 | 0.910 | 0.833 | **+0.077** |
| tabular | 7 | 0.824 | 0.758 | **+0.066** |
| recsys | 3 | 0.897 | 0.846 | **+0.051** |
| cv | 10 | 0.885 | 0.885 | 0.000 |
| nlp | 9 | 0.863 | 0.863 | 0.000 |
| other | 3 | 0.897 | 0.897 | 0.000 |

**利得は時間構造を持つ 3 domain からしか出ていない。**cv / nlp / other では
context モデルの予測がチェックリストと**完全に一致した** —— 3 特徴のうち
`temporal` と `entity` がこれらの domain でほぼ定数になり、条件付けが働かないためである。
**現在の context 特徴量は cv / nlp に対して情報を持たない。**

---

## 2. 制約(過大に読まないために)

### 2.1 一致率は多数派に支配されている

全 494 セルのうち **410 件(83.0%)が 0**(記録なし)。**「どの状態も決定的でない」と
答えるだけで 0.83 が出る。**上の +0.028 はその上での差である。

### 2.2 決定的な状態を当てられているかは、別の話

事前登録外の**事後診断**(判定を覆すためには使わない):

| | 真に「決定的」な 78 セルの再現 |
| --- | --- |
| チェックリスト | **22/78**(28%) |
| context 条件付け | **31/78**(40%) |

**どちらも過半を落としている。**context 条件付けが優ることと、実用的な精度があることは別である。

### 2.3 **反例を 1 件も再現できない**

真に `−1`(反例)のセルは 6 件。**両予測子とも 1 件も `−1` を出さない。**
494 件中 6 件では、縮約後の分布で `−1` が最大になることはない。

これは重大である。**`−1` はチェックリスト化を防ぐために置いた唯一の仕掛けであり
(§341)、当てはめた世界モデルはその仕掛けを再現できない。**
Mercari・DSTL・Bengali.AI・Planet・Quora が corpus に入っていても、
**モデルの出力には「多様性が要らない場合がある」が現れない。**

現時点の世界モデルは、**反例を持つ corpus から作った、反例を出力できないモデル**である。

### 2.4 corpus が観測できない状態が 2 つある

| 状態 | 38 コンペ中の観測 |
| --- | --- |
| **Hypothesis Calibration(HCAL)** | **0 件** |
| **Falsification Coverage(FC)** | **0 件** |

write-up は成功後に書かれ、**失敗した仮説と確信度の履歴は記録されない**(§101 の
survivorship / hindsight bias)。

**この 2 つは、C-lite を B から区別する当の構成要素である。**
つまり **winner corpus は、C-lite が価値を持つとされる部分について事前分布を供給できない。**
C-lite の価値は corpus からは出てこず、**実験でしか決着しない。**

### 2.5 単独符号化

**符号化者は 1 名(Claude)。**引き継ぎ書が要求する独立 2 系統の一致率は**未測定**。
`world_model.json` を Preferred State の既定値としてコードへ組み込まない。

---

## 3. 観測された決定性(参考)

38 コンペ中で「決定的」と符号化された回数。

| 状態 | +1 | −1 |
| --- | ---: | ---: |
| Representation / Model Coverage | 22 | 2 |
| Entity & Temporal Integrity | 15 | — |
| Validation Fidelity | 11 | — |
| Hypothesis Coverage | 6 | — |
| DGP Understanding | 5 | — |
| Data / Label Quality | 5 | — |
| Solution / Error Diversity | 5 | 2 |
| Robustness | 5 | — |
| Distribution Shift Understanding | 3 | — |
| Error Understanding | 1 | — |
| Performance Belief | — | 2 |
| **Hypothesis Calibration** | **0** | — |
| **Falsification Coverage** | **0** | — |

---

## 4. 次にやること

1. **独立符号化を入れて一致率を出す。**定義が曖昧で一致しない状態は定義を直す
2. **cv / nlp に効く context 特徴量を探す。**現行 3 特徴はこの 2 domain で定数に近い。
   ただし n=38 なので特徴を増やすと過学習する —— **増やすなら事前登録し直す**
3. **`−1` を再現できる形にする。**縮約付き argmax では反例が消える。
   反例を別クラスとして扱うか、決定性と必要性を分けて持つか
4. **NEDO へ適用する** —— 提出物がアルゴリズムで、`temporal=0 / entity=1 /
   decomposable=1`。問題クラス外での予測を出し、実測(較正・分解能・
   課題ごと相関・族の調査)と突き合わせる
5. **HCAL と FC は corpus から取らない。**実験で測るしかないことを設計に織り込む
