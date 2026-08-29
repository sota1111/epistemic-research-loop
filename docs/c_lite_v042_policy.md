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

## 4. Track B 初回の技術的負債——2 段階の修正を経て解決(2026-08-29)

[qualification](verification/v041_track_b_qualification.md) で確認した通り、初回 Suite は
Matched Negative パックが 12 run 中 9 run で昇格した。

**1 段目の修正(baseline model 強化)は効果なしと判明。** baseline を
`HistGradientBoostingClassifier` に変更した `v041-trackb-02` を再検証したところ、**P2 再現
要件は 3 構成とも 0/4 で初回より悪化**、negative パックの agent 申告 AUC も 0.48〜0.73
(中央値 0.602)と初回からほぼ不変だった。

**根本原因を特定:** `decile-stratified permutation`(risk decile 内でのみラベルをシャッフル)
は decile **間**の陽性率相関を完全に温存する設計欠陥だった——bucket 内シャッフルは bucket の
陽性件数を不変に保つため、AUC(順位統計量)は decile 間の粗い相関だけで chance を大きく
超えるスコアを出せる。合成データでの再現実験で `AUC(risk, decile-permuted target)=0.988`
を確認し、baseline の表現力とは無関係と証明した。

**2 段目の修正で解決:** `_decile_stratified_permutation` を `_destroy_target_structure`
(stratification なしの完全ランダム permutation)へ置き換え、IEEE-CIS(`v041-trackb-03`)・
Santander(`v042-mc-b02`)の両方で再検証した。**両コンペで P2 が独立に成立した**
(IEEE-CIS:opus×P3・sol×P3×xhigh の 2/3 構成、Santander:**3/3 構成全て**、negative
promotion はほぼゼロに)。詳細:
[Track B qualification](verification/v041_track_b_qualification.md) /
[Santander qualification](verification/v042_santander_qualification.md)。

**2 つのコンペで独立に成立したことにより、v0.4.2 の 2 claim(best-of-population 近傍到達・
未知構造発見)は単一コンペの偶然という懸念を脱した。**

## 5. 実行順序(2026-08-29 更新:a〜e、Rossmann 除き完了)

```text
v0.4.2-a  Matched Negative 構築法の修正 + IEEE-CIS での再検証(§4)。完了(2段階の修正を経て)。
v0.4.2-b  汎用 builder(v042_multi_competition_suite.py)への一般化。完了。
v0.4.2-c  低計算量コンペの選定確定(§3・§7)、技術クラス参照物の構築。完了
          (IEEE-CIS・Rossmann・Santander の taxonomy を docs/controller_reference/ に作成)。
v0.4.2-d  追加コンペのデータ取得。完了——2026-08-29、ユーザーが Rossmann・Santander の
          Kaggle コンペ規約に同意、データ取得済み。
v0.4.2-e  複数コンペでの Suite build → 実行 → 開封 → best-of-population 近似度・
          未知構造発見の評価。**IEEE-CIS・Santander で完了、両方で claim 1・2 を確認。**
v0.4.2-f  (新規)Rossmann への回帰対応。§3 に記載の通り、target が連続値(Sales)のため
          現行の AUC ベース pipeline(preflight・decile系→修正後は完全ランダム permutation
          による matched negative)をそのまま適用できない。回帰用の oracle(回帰モデル)・
          識別可能性指標(例:Spearman相関やR² gain)・matched negative 構築(完全ランダム
          permutation は連続値にもそのまま適用可能、修正済みのため流用できる)を設計する
          必要がある。IEEE-CIS・Santander で確立した 2 段階検証(build-only regression
          check → 実 agent batch)を踏襲すること。優先度は IEEE-CIS/Santander の結果が
          確定した後——未着手。
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

## 7. コンペ選定の結果(2026-08-29 更新:第一ラウンド完了)

ユーザーから受領したコンペ候補一覧(2026-08-29)を、**計算量が少ないこと**という新しい
必須基準(§3)で並べ直し、Rossmann・Santander を第一候補として確定(ユーザー承認済み、
2026-08-29:「7時間離席するので、今後は承認なしで全て実行すること」の指示のもと
実施)。データ取得も同日中にユーザーがコンペ規約に同意し完了。

| コンペ | 計算負荷 | discovery の明確さ | v0.4.2 での扱い |
| --- | --- | --- | --- |
| IEEE-CIS Fraud Detection | 中 | 非常に高 | **完了(P2 2/3 構成達成)** |
| Santander Customer Transaction | 低〜中 | 非常に高 | **完了(P2 3/3 構成達成、IEEE-CISより強い結果)** |
| Rossmann Store Sales | 低〜中 | 非常に高 | **データ取得済み、回帰対応が未実装のため見送り(§5 v0.4.2-f)** |
| Jigsaw Unintended Bias | 中 | 高 | 次点(未着手) |
| Airbus Ship Detection | 中〜高 | 高 | 見送り(画像データ、計算量・契約変更コスト大) |
| Riiid Answer Correctness | 高 | 高 | 見送り(計算量大、再現性の懸念も既に指摘あり) |
| H&M Recommendation | 高 | 高 | 見送り(計算量大) |
| M5 Forecasting | 高 | 高 | 見送り(計算量大) |

**第一ラウンド(IEEE-CIS + Santander)の結果、v0.4.2 の 2 claim(best-of-population 近傍
到達・未知構造発見)が 2 コンペで独立に確認された。** 詳細:
[Track B qualification](verification/v041_track_b_qualification.md) /
[Santander qualification](verification/v042_santander_qualification.md)。

**次に確認すべき事項(ユーザー向け):**

1. **Jigsaw を第 3 コンペとして追加するか。** テーブルデータではなくテキスト分類コンペ
   (subgroup metric/error 理解が discovery 対象)——現行 pipeline がテーブル形式・数値列を
   前提にしているため、Jigsaw を追加するには特徴抽出(埋め込み or TF-IDF 等)の設計が別途
   必要になる。追加コストと discovery 価値のトレードオフを判断されたい。
2. **Rossmann の回帰対応(v0.4.2-f)に着手するか。** データは既に取得済みで、いつでも
   着手できる状態。
