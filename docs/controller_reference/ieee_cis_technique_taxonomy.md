# IEEE-CIS Fraud Detection — 技術クラス参照物(Controller専有)

**分類:** Controller専有・エージェント非開示。[c_lite_v042_policy.md](../c_lite_v042_policy.md) §1 の
「技術クラス参照物」。discovery 後の post-hoc スコアリングにのみ使う。プロンプト・契約・
データ・エージェント可視のいかなるファイルにも複製しないこと。Track B(v041-trackb-01/02)は
本ドキュメント作成前に実行されているため、既存の discovery ログとの照合はこれから行う。

**出典:** Kaggle 公開 1st place write-up ("FraudSquad 1st Place Solution") および複数の
public solution 記事の要約。個別の列名・具体的コード・正確なハイパーパラメータは記録しない。

## 技術クラス

1. **エンティティ/UID 復元によるグループ化。** 明示的な顧客 ID が無い中で、カード情報・
   住所・時間調整済み特徴など複数の弱い識別子を組み合わせて「同一の顧客/カードによる
   取引」を再構成する(1st place を含む多くの上位解法が採用)——匿名化された部分特徴からの
   エンティティ解決という技術クラス。
2. **時間的因果性を守ったクライアント単位の集約特徴。** 復元した UID ごとに、過去の取引の
   みを使う集約統計量(頻度・金額分布等)を構築する——未来情報の漏洩を避ける設計が
   1st place で強調されている。
3. **同一エンティティの取引間の時間差特徴。** 同一 UID の連続取引間の時間間隔。
4. **適切な CV を伴うカテゴリ変数のターゲット/頻度エンコーディング。**
5. **train/test 分布ずれの adversarial validation。**
6. **複数の勾配ブースティング系統(CatBoost/LightGBM/XGBoost)のアンサンブル。** 1st
   place は 3 種の GBM 単体モデルを組み合わせている。

## 本プロジェクトでの位置づけ

Track B は列名を意図的に匿名化・汎用ラベル化しているため(`_visible_column_map` による
ハッシュ化)、#1(UID 復元)や #4(カテゴリ変数エンコーディング)はエージェントに提示される
数値列だけでは再現しにくい技術クラスである可能性が高い——一方 #2〜#3(集約統計・時間差)・
#5(adversarial validation 的な分布比較)・#6(アンサンブル設計)は、Track B のプロトコル
(仮説列挙・証拠手続き)が到達しうる技術クラスとして、discovery ログとの事後照合対象とする。

**次のアクション:** v041-trackb-01/02 の完了済み・完了予定の discovery ログを本taxonomyに
照合し、best-of-population 近似度([c_lite_v042_policy.md](../c_lite_v042_policy.md) §1)を
算出する。

## 層2(データ形式非依存メタ技術)との照合

v041-trackb-03(修正済み Suite)の discovery ログは、上記層1の6クラスとは0/6一致だったが、
[層2 taxonomy](meta_technique_taxonomy_layer2.md) の2クラス双方と一致した——promoted 27件中
17件(63%)が層2クラス#1(context プーリング)、複数 run が独立に層2クラス#2
(occurrence/sparsity 集約)に到達している。詳細は
[クロスコンペ統合分析](../verification/v042_cross_competition_synthesis.md)を参照。
