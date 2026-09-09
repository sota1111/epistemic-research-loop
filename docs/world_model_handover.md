# 世界モデル構築 引き継ぎ書

**作成:** 2026-09-06
**状態:** 未着手。素材は 2026-08-24 から repo にある
**正本の素材:** [research_models.md](research_models.md) §44(38 コンペ表)・§245(状態ベクトル定義)・§341(過学習対策)

---

## 0. 何を作るのか

**Preferred Research State** — 「勝てる研究状態」の分布

    p(s_good | competition context)

を、**38 コンペの上位解法 corpus から**作る。[research_models.md](research_models.md) §247 が
明示するとおり、**固定ベクトル `s*` ではなく context 条件付き分布**である。

作るものは**技術のチェックリストではない。**§247 の警告:

> 最も危険なのは、Winner corpus から「winner は adversarial validation をする / pseudo-labeling
> する / ensemble する」のようなチェックリストを作ることです。

Preferred State は**「何を使っているか」ではなく「重要な問いについてどの程度根拠ある理解を
持っているか」**で定義する。

---

## 1. 素材は最初から揃っている

### 1.1 コーパス — 38 コンペ(research_models.md §44)

| 領域 | 件数 | 例 |
| --- | ---: | --- |
| Tabular / Fraud / Relational | 9 | IEEE-CIS、Santander CTP、Home Credit、Amex、Elo、TalkingData |
| Forecasting / Time-series | 7 | Rossmann、Favorita、M5、Web Traffic、Recruit、ASHRAE |
| CV(segmentation / detection / metric) | 10 | TGS Salt、Airbus、Severstal、RSNA、SIIM、Humpback、Bengali、Planet、Carvana、DSTL |
| NLP | 8 | Quora Insincere / Pairs、Jigsaw ×2、Tweet Sentiment、QUEST、CommonLit、Feedback ELL |
| Recommendation / Online | 3 | H&M、Santander Product、Riiid |
| Retrieval / Scientific / Multimodal | 3 | Google Landmark、NOMAD、Avito |

各行に**「モデルそのものより重要だった研究上の発見」**が一次情報の引用付きで入っている。
1 位だけでなく Top 3〜10 を含む。

### 1.2 反例も既に特定されている(これが重要)

チェックリスト化を防ぐ対照が corpus に入っている。

| コンペ | 反証する仮説 |
| --- | --- |
| **Mercari 1st** | 「多数 family 探索・複雑 ensemble は必須」— single sparse-input MLP へ集中 |
| **DSTL 3rd** | 同上 — 複雑 ensemble なしで上位と競合 |
| **Bengali.AI 5th** | 「異なる model family が必ず必要」— 同一 SEResNeXt の seed diversity のみ |
| **Planet Amazon / Quora Insincere** | 「Public LB は使える」— 大きな shake-up |

**失敗例・失速例を Control として含めること**は §18 の要求でもある。

### 1.3 状態ベクトルの定義(§245)

13 状態が、**定義 / 観測・定量化 / uncertainty と更新 / Private LB との想定関係**の
4 列付きで定義済み。観測方法まで書いてあるので、実装の設計余地はほとんど無い。

---

## 2. 現状 — 世界モデルは存在しない

`src/epistemic_loop/controller/research_state.py`:

```python
DEFAULT_PREFERRED_TARGETS = {
    "validation_fidelity": 0.80,
    "hypothesis_resolution": 0.70,
    "falsification_coverage": 0.60,
    "representation_coverage": 0.35,
    "error_diversity": 0.50,
    "robustness": 0.80,
    "dgp_understanding": 0.50,
}
```

**コンペ由来ではない。私が置いた手書きの定数である。**corpus から学習した箇所は
コードベースのどこにも無い。

| 仕様(§245 の 13 状態) | 実装 |
| --- | --- |
| Validation Fidelity | 定数 0.80 |
| DGP Understanding | 定数 0.50 |
| Falsification Coverage | 定数 0.60 |
| Representation / Model Coverage | 定数 0.35 |
| Solution / Error Diversity | 定数 0.50 |
| Robustness | 定数 0.80 |
| **Distribution Shift Understanding** | **無し** |
| **Entity & Temporal Integrity** | **無し** |
| **Data / Label Quality Understanding** | **無し** |
| **Error Understanding** | **無し** |
| **Hypothesis Coverage** | **無し** |
| **Hypothesis Calibration** | **無し** |
| **Performance Belief** | **無し** |

**13 のうち 6 が定数、7 が欠落。**そして §247 が「最も危険」と名指しした
**固定ベクトル + 数値チェックリスト**の形になっている。

---

## 3. なぜ research_models.md から作らなかったのか

6 つある。順に、後のものほど大きい。

**3.1 この文書を「設計の根拠」として読み、「データ」として読まなかった。**
正本文書一覧では「研究設計」に分類してある。推奨されている**機構**(仮説レジストリ、
EIG、falsifier、QD)は実装したが、**中身**(13 状態と観測方法)は実装していない。
機構はコードだが、中身は当てはめが要る。**コンパイルが通るほうだけ作った。**

**3.2 定数を置いて先へ進み、置き換えなかった。**`derive_research_state` が
何かを返さないとループが回らないので `DEFAULT_PREFERRED_TARGETS` を置いた。
仮置きだと分かる TODO も、由来のコメントも書いていない。**決定として読める形で残った。**

**3.3 corpus は散文であって、データセットではない。**
p(s_good | context) を leave-one-domain-out で当てはめるには、38 コンペを 13 状態へ
**符号化する作業**が要る。誰もやっていないし、私は工数として見積もったこともない。
**これが実際に欠けている作業のすべてである。**

**3.4 「Winner 由来 Prior は初期実装では使用しない」を無期限の延期に使った。**
[research_basis_and_design_rationale.md](research_basis_and_design_rationale.md) §17 の
汚染対策(survivorship bias、meta-overfitting、LLM contamination)は正当な規則である。
**私はその安全規則を、難所を飛ばす許可として使った。**規則が言っているのは
「prior strength を low に固定せよ」であって「作るな」ではない。

**3.5 NEDO で「問題クラスが違う」を過大に適用した。**
引き継ぎ書に自分でこう書いた —「継承したのは population × 設計軸 → 機械的選定 →
実スコアで親選定というループ構造だけ」。**ループを継承して蓄積を捨てた。**
ループは作り直しがいちばん安い部分である。

**3.6 そして 13 状態のうち少なくとも 8 は問題クラスに依存しない。**
表形式に寄っているのは DGP / Distribution Shift / Entity・Temporal / Label Quality の
4 つだけで、残りは予測でも組合せ最適化でも同じ意味を持つ。**捨て方が広すぎた。**

---

## 4. NEDO は、この世界モデルが転移する証拠を出している

§3.6 が机上の議論でないことは、NEDO の実測が示している。**私は 4 つの状態を、
仕様にあると知らないまま、別の名前で再発明した。**

| §245 の状態 | NEDO で私が作ったもの | 実測値 |
| --- | --- | --- |
| **Validation Fidelity**「local が generalization regime をどれほど再現するか。model ranking の順位相関」 | ローカル → 実 public の較正 | 傾き **0.589**、上位圏 ρ **+0.700** |
| **Robustness**「score SD、worst-case split、rank stability」 | 分解能の法則 | 半幅 = **32/√問数** |
| **Solution / Error Diversity**「OOF residual correlation、prediction disagreement」 | 課題ごとスコア相関 | 中央値 **0.368** |
| **Representation / Model Coverage**「MAP-Elites occupancy、family descriptors」 | 解法族の調査 | **上位 16 体すべて同一族** |

**予測問題ですらない出題で、13 状態のうち 4 つが独立に再発見された。**
これは「世界モデルは表形式に縛られている」という私の言い訳への反証である。
同時に、**世界モデルがあれば最初から測っていたはずのものを、4 ラウンドかけて
その場しのぎで作り直した**ことの記録でもある。

---

## 5. 作業手順

### 5.1 形を先に直す — 目標値ではなく「決定性」の事前分布にする

**write-up から「勝者の validation_fidelity は 0.82 だった」は復元できない。**
復元できるのは**「このコンペではどの状態が勝敗を決めたか」**である。よって作るのは

    p(状態 k がこのコンペで決定的だった | competition context)

であって、目標値ベクトルではない。**`DEFAULT_PREFERRED_TARGETS` は形からして誤っている。**

### 5.2 38 × 13 の符号化

§44 の各行の「重要だった発見」を 13 状態へ割り当てる。1 コンペが複数状態を持ってよい。

- 符号化規則を**先に文書化し、事前登録する**(事後に規則を変えない)
- **2 名以上(またはモデル 2 系統)で独立に符号化し、一致率を出す。**一致しない
  状態は定義が曖昧なので、定義を直してから再符号化する
- 出典 URL を各セルに残す。§44 の引用をそのまま持つ

成果物: `docs/world_model/corpus_coding.json`(38 行 × 13 列 + 出典 + 符号化者)

### 5.3 competition context の特徴量を決める

条件付けに使う変数。**NEDO のような出題も表現できること**が要件である。

問題タイプ / 提出物の種類(予測値 か **アルゴリズム**)/ 評価指標の形 /
時間構造の有無 / train-test 分割の性質 / データ規模 / 公開-非公開分割の方式 /
外部データの可否 / 実行時間制約の有無

### 5.4 当てはめと、**leave-one-domain-out での検証**

- prior strength は **low に固定**(§17 の要求)
- **leave-one-competition-out だけでなく leave-one-domain-out**(§247)。
  「tabular fraud winners の習慣」を CV コンペへ押しつけない
- **判定基準を先に決める。**保留した domain で「どの状態が決定的か」の予測が
  base rate を上回らなければ、**世界モデルは転移しないと結論して記録する。**
  これは失敗ではなく結果である

### 5.5 Controller 専有にする

層2 taxonomy と同じ規則を適用する。**プロンプト・メモリ・エージェント可視の
いかなるファイルにも複製しない。**エージェントが世界モデル無しでどの状態へ
向かうかを測れなくなるため。

### 5.6 最初の適用先

**NEDO を最初の問題クラス外の適用先にする。**予測問題ですらないので、
context 特徴量と leave-one-domain-out の実効性が最も厳しく試される。

---

## 6. 落とし穴(すべて素材側に明記済み)

| 落とし穴 | 対策 | 出典 |
| --- | --- | --- |
| **Survivorship bias** | Top 3〜10 を含める。失速例・失敗例を Control に | §18 |
| **Meta-overfitting** | leave-one-domain-out。prior strength low | §247 / §18 |
| **LLM contamination** | corpus の write-up は事前学習に入っている。**エージェントへ見せない**ことで、再発見か暗記かを分離する | §17 / §1784 |
| **Information Gain の Goodhart 化** | 「belief entropy は減ったが間違っている」を主要失敗要因として扱う | 結論表 |
| **チェックリスト化** | 状態は「何を使ったか」でなく「どれだけ根拠ある理解を持つか」。反例 4 件を必ず通す | §247 |

---

## 7. 完了条件

**ファイルが存在することは完了条件ではない。**

1. `corpus_coding.json` が 38 × 13 で埋まり、独立符号化の一致率が報告されている
2. leave-one-domain-out の予測性能が、事前登録した base rate と比較して報告されている
   (**上回らなくてもよい。報告されていることが条件**)
3. `DEFAULT_PREFERRED_TARGETS` が撤去され、context 条件付きの事前分布に置き換わっている。
   置き換えられない状態は**定数のままにせず、欠測として扱う**
4. 世界モデルが Controller 専有であることがテストで担保されている
5. NEDO(問題クラス外)への適用結果が、成功・失敗のどちらであっても記録されている

---

## 8. この作業の位置づけ

[research_basis_and_design_rationale.md](research_basis_and_design_rationale.md) §1917 は
**「System B が弱い状態で System C を比較してはならない」**と定める。
世界モデルは C の入力であって、B の構成要素ではない。したがって順序は

1. **強い B を作る**(効用に novelty / QDContribution を入れる)
2. **世界モデルを作る**(この文書)
3. **C と B を比較する**

**2 を 3 の前に置くこと。**世界モデル無しの C は C ではない。
