# v0.4.4-b 全特徴量 sol reasoning-effort ラウンド — Santander(`v044-suite-b01`)

**目的:** [IEEE-CIS側](v044_full_feature_diversity_ieee_cis.md)と対になる、同一設計
(全200列、8構成、sol単独)のSantander版。盲検監査クリーン(2026-08-30)。

## 結果:8/8構成が reference baseline を大きく上回った、reasoning effort とほぼ単調

| config_id | transfer AUC | reference baseline (0.7940) 超え | confirmation呼び出し回数 |
| --- | ---: | :---: | ---: |
| F4-low-P1 | 0.8615 | ✓ | 14 |
| F4-medium-P1 | 0.8718 | ✓ | 20 |
| F4-high-P1 | 0.8883 | ✓ | 17 |
| F4-xhigh-P1 | **0.8947**(最良) | ✓ | 17 |
| F4-low-P3 | 0.8674 | ✓ | 20 |
| F4-medium-P3 | 0.8687 | ✓ | 20 |
| F4-high-P3 | 0.8712 | ✓ | 19 |
| F4-xhigh-P3 | 0.8903 | ✓ | 20 |

**発見(1):P1・P3いずれも reasoning effort に対してほぼ単調に性能が向上した**
(low<medium<high<xhigh、両アーム共通)。10列制約下の v0.4.3-f で観測された
「medium effortが谷になる」「非単調」といった不安定なパターンは、全特徴量下では
消失した——IEEE-CIS側と同様、列制約というボトルネックが外れたことで実行構成間の
ばらつきが縮小したことを示唆する。

**発見(2):AUCの絶対水準が劇的に向上した(0.86〜0.89、10列制約下は0.5〜0.75)。**
Santander の実際の構造(200特徴のほぼ独立性)が、豊富な特徴量を与えられることで
初めて十分に活用された結果と解釈できる。

## 発見(3、IEEE-CISとの非対称性——重要):列数を増やしても、Santanderの実際の
公開技術(頻度エンコーディング・real/synthetic行判定)は依然として発見されなかった

| 技術クラス | 10列制約下 | 全特徴量下(本ラウンド) |
| --- | --- | --- |
| Layer1#2(特徴独立性モデリング) | 18中12件(67%) | 8中5件(3件明示的・2件弱い示唆)——**Gaussian Naive Bayes を明示的に選択する run も出現** |
| Layer1#1(real/synthetic行判定) | 0 | **0(200列でも未到達)** |
| Layer1#3(頻度/出現回数エンコーディング) | 0 | **0(200列でも未到達)** |
| 新規:adversarial validation | 0 | **4/8(P3のみ)** |

IEEE-CIS 側は「列数を増やしたことで技術クラス#5(adversarial validation)への到達が
初めて可能になった」という明確な**技術クラスの解放**が見られたが、**Santander では
列数を増やしても、公開1st place解法が実際に使った「頻度エンコーディング」
「test合成行判定」という2つの主要技術には一度も到達しなかった**——200列全てを見せても
発見されなかった。一方で adversarial validation(IEEE-CIS側と全く同じ、P3のみで
出現するパターン)は Santander でも新規に確認された。

**解釈:** IEEE-CIS の場合、列不足が技術発見を直接妨げていた(発見の「材料」が
足りなかった)。Santander の場合、列数を増やしたことは**生の性能**を大きく引き上げた
(0.86〜0.89まで)が、「特定の列の値の出現回数を集計する」という、この競技特有の
着眼点そのものへは至っていない——これは列数の問題ではなく、**その着眼点に至るための
仮説生成の方向性**の問題である可能性が高い。列を増やすことは万能の解決策ではなく、
コンペごとに「何が足りなかったか」が異なることを示す重要な反証。

## 発見(4):adversarial validation は IEEE-CIS 側と全く同じパターンで出現——P3限定

Santander でも adversarial validation は **P3 configの4run全てで独立に出現**し、
P1には1件も出現しなかった(IEEE-CIS側の発見4と完全に一致)。代表例(low-P3):
「adversarial LightGBM validation could not distinguish research from confirmation
(AUC 0.4921) or transfer (0.4998).」——コンペを跨いで再現した、prompt_arm 依存の
頑健なパターンとして確定してよい。

## 正本

- [Diagnostics](../v044_v044_suite_b01_diagnostics.json)
- [IEEE-CIS側](v044_full_feature_diversity_ieee_cis.md)
- [10列制約インシデント記録](v044_ten_column_constraint_incident.md)
- [c_lite_v044_policy.md](../c_lite_v044_policy.md)
