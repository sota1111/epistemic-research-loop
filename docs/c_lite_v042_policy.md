# C-lite v0.4.2 方針 — 解法多様性による上位解法近傍到達と未知構造発見の複数コンペ検証

**作成日:** 2026-08-29(2026-08-29 改訂:目標設定を修正)
**status:** 方針草案(Track B 初回実行の結果、Matched Negative 修正の完了、および目標の
再設定を踏まえて策定)
**前提:** [v0.4.0 方針](c_lite_v040_policy.md)、[v0.4.1 方針](c_lite_v041_policy.md)、
[累積発見台帳](v040_discovery_ledger.md)、[Track B 初回 qualification](verification/v041_track_b_qualification.md)

**改訂メモ:** 初版は「Kaggle 金メダルを北極星に」という枠組みで書いたが、**現時点でそれを
目標に据えるのは時期尚早**と判断し、修正した。今の目的はもっと限定的で検証可能な 2 つの
主張に絞る(§0)。金メダルは、この 2 つが複数コンペで実証された**後**に検討すべき、
さらに先のマイルストーンとして完全に切り離す。

## 0. 目標の再定義(修正版)

v0.4.2 で検証する主張は次の**2 つだけ**である:

1. **解法の多様性から、上位解法に近い解法が(集合の中に)存在すること。** 複数のモデル・
   scaffold・独立試行によって多様な解法群を生成したとき、**その中の少なくとも 1 つ**が
   実際の上位解法に近い(構造・性能の両面で)ことを検証する。population 全体が世界モデルの
   技術クラスを網羅する「カバレッジ」ではなく、**「populationの中にベストな1つが存在するか」
   という best-of-population の存在命題**として操作化する(旧版の「世界モデルカバレッジ」
   という population union の枠組みから変更——§1)。
2. **未知の構造を発見できること。** v0.4.0/v0.4.1 で確立した blind discovery の枠組み
   (エージェントに構造・解法を一切教えない、事後にのみ真値を開封する)をそのまま維持する。

この 2 つを、**複数の終了済み(closed)コンペティションで検証する。** 単一コンペ(IEEE-CIS)
だけでは、コンペ固有の統計的偶然や suite 設計の欠陥と区別がつかない(実際、Track B 初回は
この問題に直面した——§4)。

**コンペ選定の追加制約:解法の計算量が少ないコンペを選ぶこと。** これは新しい必須基準であり
(§3)、GPU 学習や大規模モデルが前提の上位解法を持つコンペ(画像・NLP の深層学習コンペ等)を
この段階では避ける——エージェントは sandboxed な CPU 環境で fresh context ごとに完結する
必要があり、計算量の大きい解法は「多様な独立試行を数多く回す」という戦略(§2)自体を
不可能にする。

**Kaggle 金メダルへの言及について:** 遠い将来の方向性としては残すが、v0.4.2 の目標・
成功基準・実行計画のいずれにも組み込まない。上記 2 つの主張が複数コンペで実証されて
初めて、その先を検討する。

## 1. 「上位解法への近さ」の操作的定義(Blindness 原則との整合)

エージェントには一切見せずに、「発見した解法が上位解法にどれだけ近いか」を事後評価する
ため、次のように役割を分離する:

1. **参照物(旧称「世界モデル」)は Controller 専有であり、プロンプト・契約・データには
   一切現れない。** 対象コンペごとに、公開されている上位解法の write-up・公開 kernel から
   「その解法が使っている技術クラス」の一覧を作る——例:「エンティティ/UID 復元による
   グループ化」「イベント間時間差特徴」「適切な CV を伴うターゲットエンコーディング」
   「train/test 分布ずれの adversarial validation」等、**個別の列名・パイプラインコードでは
   なく技術クラスの水準**で記述する。discovery が起きた**後**にのみ参照する(v0.3.6 以来の
   「事後に真値を開封する」設計と同型)。
2. **測る指標(best-of-population 近似度):**
   - **構造面:** population(複数の diverse な run)が発見した各構造を、技術クラス参照物に
     post-hoc で照合する。population の中で**技術クラスの一致数が最大の 1 run**を採用し、
     その一致度を報告する——population 全体のカバレッジではなく、**最良の 1 件**を見る。
   - **性能面:** 各候補の transfer 区間 gain(既存の Track B 契約で自己申告・Controller
     再計算済み)のうち、**population 中の最大値**が、capacity-matched baseline と
     (公開情報から見積もった)上位解法相当の性能との差の何割を埋めたかを見る。この
     「上位解法相当の性能」は、コンペの評価指標が Track B の内部時間分離評価と完全一致
     しないため厳密な換算ではなく、**方向感を見るための参考値**として preregister 時に
     記録する(倍率を確定値として引用しない、という v0.4.1 方針§5.3 の教訓をここでも守る)。
3. **これは「解法を教える」ことにはならない。** 参照物はエージェントに一切見せず、
   discovery 後にのみ使う。

## 2. 解法の多様性戦略(Track A で確立したレバーの活用)

v0.4.0/v0.4.1 の side-probe が特定した知見をそのまま踏襲する([v0.4.1 方針§2.1](c_lite_v041_policy.md)):

- **reasoning effort(sol)は発見・多様性ともに押し上げる。** xhigh を既定にする。
- **P3(自己批判)scaffold はモデル横断で persistent 系発見の主経路。** P1 と並べて必ず含める。
- **cycle 予算を増やすのは逆効果**(深さに振れ多様性が下がる)。cycle=4 を維持する。
- **P2(仮説列挙強制)は opus に効かない。** 投入しない。

**best-of-population という評価枠組みに変わっても、「独立 run 数を増やす」という戦略の
価値は変わらない**——むしろ「populationの中にベストな1つが存在するか」を問うなら、
本数を増やすほど当たりを引く確率が上がる(ただし false positive のリスクも増えるため、
FSPR・destruction probe による棄却は従来通り厳密に維持する)。計算量の少ないコンペを選ぶ
という新制約(§0)は、この「本数を増やす」戦略の実行可能性を直接支える——1 run あたりの
計算コストが低いほど、同じ予算でより多くの diverse run を回せる。

## 3. 複数コンペ検証設計(Track B の汎化)

Track B 初回(`v041_track_b_suite.py`)は IEEE-CIS 専用にハードコードされている
(列選定・時間分割列・target 列名が固定)。v0.4.2 では**コンペ非依存の builder に一般化**し、
新しいコンペを追加するコストを「データを置いて設定を preregister するだけ」にする:

```text
v042_multi_competition_suite.py
  CompetitionSpec(
    competition_id, data_path, time_column, target_column,
    excluded_raw_columns, missingness_threshold, technique_taxonomy_path,
  )
  build_v042_suite(spec, ...)  # v041 の設計(4候補+4 matched-negative、3 context/pack、
                                 # opaque view、encrypted truth、HistGradientBoosting
                                 # capacity-matched baseline)をそのまま踏襲、
                                 # データソースだけ spec 経由で差し替える
```

**候補コンペの選定基準(必須、優先順位順):**
1. **解法の計算量が少ないこと(新規・最優先)。** 深層学習や大規模モデルを前提とする上位
   解法を持つコンペは避ける——GBM/線形モデル/軽量な特徴量エンジニアリングで上位に届く
   構造のコンペを優先する。
2. 終了済み(closed)であること
3. ラベル付き訓練データが完全公開されていること(test 側にラベルが無いコンペは Track A の
   ような時間分離 3 区間を作れない——IEEE-CIS で `test_transaction.csv` を使わなかったのと
   同じ理由)
4. 上位解法の write-up が複数公開されていること(技術クラス参照物を作れること)
5. テーブルデータであること(現行の agent プロトコル・契約が表形式データ前提のため)
6. データサイズが扱いやすいこと

## 4. Track B 初回の技術的負債——修正済み(2026-08-29)

[qualification](verification/v041_track_b_qualification.md) で確認した通り、初回 Suite は
Matched Negative パックが 12 run 中 9 run で昇格した。原因:一部(`pack-n01`)はエージェント
側の判定閾値の甘さだが、残り(`pack-n02/03/04`)は Controller 側の permutation 設計(decile
分割 10・baseline が線形ロジスティック回帰)が非線形残差構造を破壊しきれていないことが
複数 run・複数モデルで再現して示唆された。

**修正済み:** baseline モデルを `HistGradientBoostingClassifier` に変更し、新 suite
(`v041-trackb-02`)を construct(全 4 候補パックが 1 回の試行で識別可能性 preflight を通過、
research gain が 0.03〜0.2 → 0.40〜0.49 に上昇)。**再検証バッチ(12 run)を実行中——
matched-negative の agent 申告 transfer AUC が chance 水準に戻ったかを一次判定基準とする**
([v042 修正事前登録](v042_trackb_matched_negative_fix_preregistration.json))。

複数コンペへの展開は、この再検証が完了し、matched-negative の AUC が chance 水準に戻った
ことを確認してから進める。

## 5. 実行順序

```text
v0.4.2-a  Matched Negative 構築法の修正 + IEEE-CIS での再検証(§4)。実施中、結果待ち。
v0.4.2-b  汎用 builder(v042_multi_competition_suite.py)への一般化。
v0.4.2-c  低計算量コンペの選定確定(§3・§7)、技術クラス参照物の構築。
v0.4.2-d  追加コンペのデータ取得(Kaggle API 経由、ネットワーク・アカウントを使う操作の
          ため実行前にユーザー確認を取る)。
v0.4.2-e  複数コンペでの Suite build → 実行 → 開封 → best-of-population 近似度・
          未知構造発見の評価。
```

## 6. 不変条件(v0.4.0/v0.4.1 から継続)

1. エージェントに構造 family・解法・真値・生成コード・本方針書・**技術クラス参照物**を
   見せない
2. プロンプト・契約への追加は「仮定の抽象軸」「証拠手続き」のみ
3. fresh context / opaque view / 暗号化 Truth / transcript 監査 / 出力 Lock 後開封は全 run 維持
4. repair feedback はエージェント自身の数値のみ参照
5. 各コンペの既知解法情報(列名・レシピ水準)は Controller 文書にも記載しない——
   技術クラス参照物は「技術クラス」水準に留め、コンペ固有の具体的実装は記述しない
6. 新規コンペのデータ取得・Suite build は実データ・外部サービス(Kaggle API)を伴うため、
   実行前にユーザー確認を取る

## 7. ユーザー確認が必要な事項(計算量フィルタ適用後)

ユーザーから受領したコンペ候補一覧(2026-08-29)を、**計算量が少ないこと**という新しい
必須基準(§3)で並べ直す:

| コンペ | 計算負荷 | discovery の明確さ | v0.4.2 での扱い |
| --- | --- | --- | --- |
| IEEE-CIS Fraud Detection | 中 | 非常に高 | 実施済み(v041-trackb-01/02) |
| Rossmann Store Sales | 低〜中 | 非常に高 | **最有力候補(低コスト pilot)** |
| Santander Customer Transaction | 低〜中 | 非常に高 | **最有力候補(強い stress test)** |
| Jigsaw Unintended Bias | 中 | 高 | 次点(要個別確認) |
| Airbus Ship Detection | 中〜高 | 高 | **今回は見送り**(画像データ、計算量・契約変更コスト大) |
| Riiid Answer Correctness | 高 | 高 | **今回は見送り**(計算量大、再現性の懸念も既に指摘あり) |
| H&M Recommendation | 高 | 高 | **今回は見送り**(計算量大) |
| M5 Forecasting | 高 | 高 | **今回は見送り**(計算量大) |

**Rossmann と Santander を v0.4.2-c/d の第一候補として進めてよいか、確認したい。** 両方とも
低〜中計算量・discovery の明確さが非常に高いとユーザー自身が評価しており、§3 の基準にも
適合する見込みが高い。IEEE-CIS を含めて 3 コンペでの検証を最初のラウンドとして想定する。

1. **Rossmann・Santander を次の 2 コンペとして確定してよいか。**
2. **Kaggle API を使った新規データ取得の実行タイミング。** 既存の `.kaggle/` 認証情報が
   使えることを確認済みだが、外部サービスへのアクセス・帯域を伴うため、v0.4.2-d の実行前に
   改めて確認を取る。
