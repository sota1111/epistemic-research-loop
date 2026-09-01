# Santander Customer Transaction Prediction — 技術クラス参照物(Controller専有)

**分類:** Controller専有・エージェント非開示。[c_lite_v042_policy.md](../c_lite_v042_policy.md) §1 の
「技術クラス参照物」。discovery 後の post-hoc スコアリングにのみ使う。プロンプト・契約・
データ・エージェント可視のいかなるファイルにも複製しないこと。

**出典:** Kaggle 公開 1st place write-up ("#1 Solution" discussion, 2019) および複数の
public solution 記事の要約。個別の列名・具体的コード・正確なハイパーパラメータは記録しない
(技術クラスの水準に留める、というブラインドネス原則——policy §1.1)。

## コンペの性質

200 個の匿名化数値特徴(`var_0`〜`var_199`)、二値 target。特徴間の意味的関連は非公開。
train は 200,000 行、test も 200,000 行。Track B の他コンペと異なり **時間的順序を持たない**
——本コンペを Suite 化する際は `time_column=None`(iid_random split)を用いる
([v042_multi_competition_suite.py](../../src/epistemic_loop/benchmark/v042_multi_competition_suite.py))。

## 技術クラス

1. **行レベルの「本物 / 合成」判定(uniqueness/frequency ベース)。** test セットの約半数が
   合成的に生成された行であり、各特徴内の値の出現回数(unique かどうか)を手がかりに本物の
   行だけを抽出できることが 1st place 含む上位解法の中核的発見だった。データ完全性・
   adversarial validation に隣接する技術クラス。
2. **特徴間独立性を前提としたモデリング。** 200 特徴がほぼ独立という前提のもとで、
   典型的な木モデルの交互作用探索とは異なる「特徴ごとに寄与を計算し合成する」設計
   (per-feature モデル、"sum of logs" 的な合成)を採用する解法が上位に複数存在した。
3. **頻度/出現回数エンコーディング。** 各特徴の値の出現回数そのものを追加特徴として使う
   (#1 と直結する技術クラス)。
4. **データ拡張・オーバーサンプリング。** クラス不均衡に対し、拡張・オーバーサンプリングで
   CV とリーダーボード双方のスコアを大きく改善したと複数解法が報告している。
5. **特徴独立性構造に特化したニューラルネット設計と GBM とのブレンド。** 1st place は
   600 特徴の LightGBM と、特徴独立性を意識したカスタム NN 構造をブレンドして最終スコアを
   得た。

## 本プロジェクトでの位置づけ

上記 5 クラスのうち、#1(行の真贋判定)は本コンペ固有の「test セット合成行」構造に強く
紐づき、Track B のような時間分離ではなく **iid 前提の transfer 評価**(policy §0 の
best-of-population claim の対象)でどう現れるかが未知——エージェントが見るのは transfer
区間の特徴のみで test/train 境界そのものは見せないため、#1 の技術クラスが直接発見される
可能性は低いと予想されるが、事前には確定しない。#2〜#5(特徴独立性・頻度エンコーディング・
データ拡張・アンサンブル設計)はエージェントの protocol でも到達可能性がある技術クラスとして
discovery 後の照合対象とする。

**ステータス(2026-08-29 時点):** データ取得・Suite 構築・12-run batch(`v042-mc-b02`)完了
済み。結果は [Santander qualification](../verification/v042_santander_qualification.md) と
[クロスコンペ統合分析](../verification/v042_cross_competition_synthesis.md) を参照。

## 層2(データ形式非依存メタ技術)との照合

discovery ログは上記層1の技術クラス#2(特徴独立性前提のモデリング)と部分一致した
(「単一の共有線形方向が context を跨いで汎化する」という発見)。[層2 taxonomy](meta_technique_taxonomy_layer2.md)
との照合では、**promoted 38件全て(100%)が層2クラス#1(context プーリング)**に一致——
Santander の実際の構造(200特徴のほぼ独立性・線形分離可能性)が単純であることの反映と
考えられる。詳細は[クロスコンペ統合分析](../verification/v042_cross_competition_synthesis.md)
を参照。
