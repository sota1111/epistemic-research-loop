# 世界モデル 符号化規則(事前登録)

**確定:** 2026-09-06、**符号化を開始する前**
**この文書を確定した後、規則・特徴量・判定基準を変更しない。**変更する場合は
変更理由と変更時刻を追記し、変更前の当てはめ結果も残す。

**素材:** [research_models.md](../research_models.md) §44(38 コンペ表)・§87〜116・§245・§341
**入口:** [世界モデルとは何か](README.md)

---

## 1. 何を符号化するか

write-up から「勝者の validation_fidelity は 0.82 だった」は**復元できない。**
復元できるのは「**このコンペで、どの研究状態が勝敗を決めたか**」である。よって
符号化するのは状態の**値**ではなく**決定性**である。

各コンペ × 13 状態に、次の 3 値のいずれかを与える。

| 値 | 意味 | 付与条件 |
| ---: | --- | --- |
| **+1** | **決定的だった** | §44 の当該行、または §87〜116 の本文が、上位到達の主要因としてその状態の理解を明示的に挙げている |
| **0** | **記録なし** | 言及がない。**「重要でなかった」ではない**(write-up の欠落と区別できないため) |
| **−1** | **反例** | そのコンペが「その状態が高くなければ勝てない」を**反証する**証拠として本文に挙げられている |

**−1 を必ず使うこと。**これがチェックリスト化を防ぐ唯一の仕掛けである(§341)。
本文が明示している反例:

- **Mercari 1st**(single sparse-input MLP)→ Solution/Error Diversity に −1
- **DSTL 3rd**(複雑 ensemble なしで競合)→ Solution/Error Diversity に −1
- **Bengali.AI 5th**(同一 architecture の seed diversity のみ)→ Representation/Model Coverage に −1
- **Planet Amazon / Quora Insincere**(大きな shake-up)→ Performance Belief に −1
  (Public LB を性能推定と同一視できない)

## 2. 13 状態(§245 の定義に従う。短縮名は本符号化限り)

| 短縮名 | 状態 | +1 を付ける根拠の例 |
| --- | --- | --- |
| `VF` | Validation Fidelity | holdout 設計・time split・「LB より CV を信じる」が主要洞察 |
| `DGP` | DGP Understanding | 行/ラベルの生成過程の推定が勝ち筋(fake row、UID、candidate 生成) |
| `DSU` | Distribution Shift Understanding | adversarial validation、train/test 差の把握が主要因 |
| `ETI` | Entity & Temporal Integrity | 同一 entity・時間因果・重複/overlap の扱い |
| `DLQ` | Data / Label Quality Understanding | label noise、leakage、synthetic row、外部 leak |
| `EU` | Error Understanding | subgroup / slice / 分解による誤りの説明 |
| `HC` | Hypothesis Coverage | 代替説明の探索、問題分解の複数案が並立 |
| `HCAL` | Hypothesis Calibration | 確信度と結果の整合(**write-up にはほぼ現れない想定**) |
| `FC` | Falsification Coverage | 有力仮説を否定しにいく実験 |
| `RMC` | Representation / Model Coverage | representation / family が本質的に異なる解が上位に並ぶ |
| `SED` | Solution / Error Diversity | 誤差が独立な解の保持、ensemble 寄与 |
| `ROB` | Robustness | seed/split 安定性、shake-up 耐性 |
| `PB` | Performance Belief | hidden 性能の推定そのものが論点 |

## 3. context 特徴量

**domain は特徴量に使わない。**leave-one-domain-out で保留する軸だからである
(保留した domain は学習時に未知水準になる)。§247 が禁じているのは
「tabular fraud winners の習慣を CV コンペへ押しつける」ことなので、
**domain ではなく構造属性で条件付ける。**

38 件 = n が小さいので**3 特徴に固定する**(多くすると過学習する)。

| 特徴 | 定義 |
| --- | --- |
| `temporal` | 時間順序が予測対象の一部、または train/test が時間で分かれる |
| `entity` | 同一 entity(顧客・店舗・画像・ユーザ)が複数行に跨って現れる |
| `decomposable_metric` | 評価指標が subgroup / class / 階層へ分解でき、その分解が上位差になりうる |

`submission_type`(予測値 / **アルゴリズム**)は 38 件すべて「予測値」なので
**学習には使わない。**NEDO を問題クラス外テストへ掛けるときに使う。

> **追記(2026-09-06、規則の変更ではなく被覆の記録):** 3 特徴 = 8 セルのうち、
> 38 コンペが観測したのは **6 セル**である。`(0,1,1)` と `(1,0,1)` は空。
> NEDO は `(0,1,1)` に落ちるため、**条件付けが働かない**
> ([prediction_nedo.md](prediction_nedo.md) §2)。

## 4. domain の割り当て(leave-one-domain-out 用)

`tabular` / `forecasting` / `cv` / `nlp` / `recsys` / `other`(retrieval・scientific・multimodal)

## 5. 当てはめる対象

    p(状態 k が決定的 | temporal, entity, decomposable_metric)

**prior strength は low に固定する**(§18)。実装上は、条件付き頻度を
全体頻度へ向けて縮約する(shrinkage 係数を事前に `k0 = 5` と固定する)。

## 6. 判定基準(事前登録)

**帰無仮説 H0:** context で条件付けても、**context を無視したチェックリスト**より
当たらない。

| | 予測子 |
| --- | --- |
| **base rate(チェックリスト)** | 状態ごとに、学習側 38−m 件の多数決ラベルを、保留コンペ全件へ一律に予測する |
| **context モデル** | 上記 §5 の条件付き頻度(shrinkage 込み)を 0.5 で二値化して予測する |

- **評価:** leave-one-domain-out。保留 domain の各コンペについて 13 状態の
  Hamming 一致率を出し、38 件で平均する
- **検定:** 38 件を単位とした対応ありブートストラップ(10,000 回)で差の 95% 区間を出す
- **判定:** 区間が 0 をまたぐ場合、**「context 条件付けの優位は検出できなかった」と記録する。**
  順位を付けない。これは失敗ではなく結果である
- **`−1` の扱い:** 一致率の計算では 3 値をそのまま比較する(+1/0/−1 の完全一致のみ正解)

**検出力についての事前の注意:** n=38、domain 6 区分。**小さな差は検出できない。**
事前に「差が 0 と区別できなかった」で終わる可能性が高いことを認める。

## 7. 符号化者

**今回は 1 名(Claude)による単独符号化である。**§引き継ぎ書が要求する
独立 2 系統の一致率は**未測定**であり、その旨を成果物に明記する。
独立符号化が入るまで、この世界モデルを Preferred State の既定値として
コードへ組み込まない。

## 8. 汚染への対処

- corpus の write-up は LLM の事前学習に含まれる。**世界モデルは Controller 専有とし、
  エージェント可視のいかなるファイルにも複製しない**(層2 taxonomy と同じ規則)
- 符号化は §44 の表と §87〜116 の本文**のみ**を根拠にする。
  記憶や外部知識で行を補わない。根拠が本文に無ければ `0`
