# v0.4.3-c 事前登録 — Rossmann 回帰対応パイプラインの設計

**作成日:** 2026-08-29
**status:** §1〜5(metric・oracle・permutation・回帰用 agent 提出契約・プロンプト)は
実装・単体テスト完了。§7 に記載の通り、Rossmann の実行(build-only preflight 含む)は
共有基盤の再設計が必要なブロッカーにより次ラウンドへ持ち越し——本ラウンドでは未実行。
**前提:** [c_lite_v043_policy.md](../c_lite_v043_policy.md) §3(v0.4.3-c)。

## 0. 調査で判明した追加スコープ(policy §3 執筆時点では未確認だった点)

`src/epistemic_loop/controller/v037_agent.py` の agent 提出契約は、分類タスクの数値範囲を
**実行時に検証する**箇所が2つある(policy §3 執筆時は「契約が確率前提のフィールドを持つか
確認する」としていたが、以下で確定した):

- `TranslationPredictions.__post_init__`(L199):`0 <= value <= 1` を全 prediction 値に強制
  ("must be finite probabilities")。回帰の連続値(例:Rossmann `Sales` は概ね 0〜40,000)は
  この範囲外になるため、そのまま提出すると必ず拒否される。
- `V037ContextArtifact.__post_init__`(L216, L218):`research_control_auc`・
  `research_structure_auc`・`independent_implication_strength` を `[0,1]` に強制。
  Spearman 相関に相当する自己申告統計量は `[-1,1]` を取りうるため、そのままでは負の相関を
  報告した瞬間に拒否される。

**結論:** 分類用の契約(`v037_agent.py`)は改変しない(既に qualification 済みの
IEEE-CIS・Santander パイプラインを一切変更しないという既存の不変条件を最優先する)。
代わりに、この2箇所だけを緩めた**別モジュール**
`src/epistemic_loop/controller/v043_regression_agent.py` を新規作成し、cycle/lineage/null
provenance など**タスク非依存の残り全て**(`V037Confidence`・`V037FailureTrace`・
`V037ResearchDescriptor`・`V037Proposal`・`V037CycleRecord`・`FullRefitNullSummary`・
`V037Resolution`・`NullStoppingReason`・`LineagePolicy`・`MAX_CYCLES_PER_PACK`)は
`v037_agent` からそのまま import して再利用する。

## 1. Oracle

`HistGradientBoostingRegressor(random_state=0)`(`HistGradientBoostingClassifier` と対の
sklearn クラス、既存の native NaN 処理という選定理由をそのまま維持)。`.predict(features)`
で連続値を得る(`.predict_proba(...)[:, 1]` の代替)。

## 2. 識別可能性・スコアリング指標

**`_spearman(targets, predictions)`**(`v037_repro_suite.py` に `_auc` と併置で新規追加)。
ランクベースの Spearman 順位相関——タイは平均順位で処理。**退化ケース:** predictions が
定数(分散ゼロ)の場合は相関が数学的に未定義になる(0/0)。`_auc` が退化ケースで chance-level
の `0.5` を返す設計に倣い、`_spearman` は分散ゼロの場合 `0.0`(相関なし = chance level)を
返す。これは control(baseline)モデルが常に「訓練 target の平均値」という定数予測になる
本パイプラインの設計と直接関係する——`control_gain = _spearman(y, oracle) - _spearman(y,
control) = _spearman(y, oracle) - 0.0` となり、gain は事実上 oracle 単体の相関係数と一致する
(分類側の `_auc` 制御が厳密に 0.5 にならない場合があるのとは異なり、回帰側は制御項が
恒等的にゼロになる——この非対称性は許容する、`_auc` 側と完全に対称にする必要はない)。

閾値は既存のもの(`research > 0.02`・`confirmation > 0`・`transfer > 0`・
`independent > 0.05`)を**そのまま流用する**——これらは「chance level からの小さなマージン」
という意味で選ばれており、AUC の `[0.5, 1]` 有効域と Spearman 相関の `[-1, 1]`(chance=0)
は原点をゼロ基準に取れば同じ尺度感(小さな正のマージン)として扱える。実 Rossmann データの
build-only preflight で、この閾値が意味を成す(強い構造を持つ列グループが確実にクリアし、
統計的に無意味な列グループはクリアしない)ことを確認してから agent batch に進む——閾値が
不適切だと判明した場合はこの preflight 段階で調整し、以降は凍結する。

## 3. Matched Negative 構築

`_destroy_target_structure`(完全ランダム permutation)は**そのまま流用**。連続値配列にも
バイナリ配列にも依存しない実装(`target[rng.permutation(len(target))]`)であり、追加の設計
変更は不要——policy §3 の見積もり通りだった。

## 4. エージェント向けプロンプト

`v040_p1.md`・`v040_p3.md` の分類依存箇所は「Output one aligned probability for every sealed
row」の1文のみ(L52-53、他は完全にデータ形式非依存)。新規プロンプト
`v043_p1_regression.md`・`v043_p3_regression.md` を作成し、この1文だけを
「Output one aligned continuous-valued prediction for every sealed row, on the same scale as
the visible research-split target values; never attempt to recover sealed labels.」に置換する
——既存プロンプトの事後変更は行わず(凍結原則)、新規ファイルとして追加する。

## 5. 提出契約

§0 の通り、`v043_regression_agent.py` を新設し以下を変更する:

- `TranslationPredictions`:値域チェックを `0 <= value <= 1` → `math.isfinite(value)` のみに
  緩和(連続値は範囲を限定しない——Rossmann の `Sales` の実際のレンジはコンペごとに異なり
  ハードコードすべきでない、列意味論を知らない設計と整合)。
- `V037ContextArtifact` 相当のクラス:`research_control_auc`/`research_structure_auc` を
  `research_control_stat`/`research_structure_stat` に改称し値域を `[-1, 1]` に変更、
  `independent_implication_strength` は `[0,1]` のまま維持(実装強度の定義は変えない)。
- 契約辞書(`v037_submission_contract()` 相当):フィールド説明文を「correlation statistic in
  [-1,1]」「continuous prediction aligned to the visible target scale」に書き換えた回帰版を
  返す関数として新設。

`scripts/finalize_v042_suite.py` 相当のスコアリングスクリプトも、`_auc` ではなく `_spearman`
を使う回帰版(`finalize_v043_regression_suite.py`)を新設する(既存スクリプトは分類専用の
まま凍結)。

## 6. 実行順序(既存の設計通り、変更なし)

1. 本ドキュメントで preregister(完了)
2. 小さな合成回帰データで plumbing テスト(unit test、`_spearman`・`_destroy_target_structure`
   の連続値対応・回帰版契約バリデーションの正常系/異常系)
3. 実 Rossmann データで build-only preflight チェック(agent run なし)——4 候補パックが
   識別可能かどうかで閾値の妥当性を確認
4. 問題なければ 12-run batch を実行(実 API コストを伴うため、実行前にその旨をユーザーに
   簡潔に報告する——既存の不変条件6は「実行前の確認」を求めるが、今回のユーザー承認
   ("追加実験と試行錯誤まで承認なしで進めて良い")によりブロッキングな承認取得は不要、
   ただし何を実行するかは可視にする)

## 7. 実装中に判明したブロッカー(2026-08-29、build-only preflight 以前)

metric・oracle・permutation・agent 提出契約(§1〜5)の実装・単体テストは完了し、既存の
分類パイプライン(IEEE-CIS・Santander)に影響がないことを確認した(`make ci` 相当を実行
済み)。しかし `CompetitionSpec` を実データに向けて preflight する前段階で、**Rossmann の
生の数値列数が現行 Suite アーキテクチャの前提を満たさない**ことが判明した:

- `train.csv` の数値列(`Sales`・`Date`・`Customers` 除外後)は `Store`・`DayOfWeek`・
  `Open`・`Promo`・`SchoolHoliday` の**5列のみ**。`store.csv` を `Store` で結合しても
  (`CompetitionDistance`・`CompetitionOpenSinceMonth/Year`・`Promo2`・
  `Promo2SinceWeek/Year`)、うち後者4列は欠損率 32〜49% で既定の missingness 閾値
  (0.02)を超える——missingness 閾値を緩めても、`Date` からの一般的な暦分解
  (year・month・day・week_of_year 等、Rossmann 固有の休日カレンダーではなく任意の
  時系列コンペに適用可能な汎用分解)を加えても、現実的に到達できる数値列数はせいぜい
  15〜20 列程度。
- 一方 `v037_repro_suite.CANONICAL_FEATURES` は **10 個の実特徴スロットを固定長**で
  持ち(`_build_row_dicts` が `zip(real_slots, feature_columns, strict=True)` で
  厳密に長さ一致を要求)、`_CANDIDATE_PACK_COUNT=4` かつ列グループは pack 間で
  **disjoint**(重複なし)という設計のため、**最低 40 個の独立した数値列**が必要
  ——IEEE-CIS(380+ 列)・Santander(200 列)は元々桁違いに列数が多い匿名化コンペ
  だったために気づかれていなかった暗黙の前提。Rossmann はこの前提を構造的に満たせない。

**判断:** この固定長スロット設計(`CANONICAL_FEATURES` の長さ・disjoint pack 制約)は
`v037_repro_suite.py` という、v0.3.7〜v0.4.2 の**既に qualification 済みの全 Suite が
共有する基盤モジュール**に存在する。Rossmann 1件のために、この共有基盤を変更する
(可変長スロット・非 disjoint pack 等)のは影響範囲が大きすぎるため、**今回の
セッション内では実施しない**——「測り直してから切る」という本プロジェクトの規律に従い、
数値合わせのための場当たり的な列合成(暦分解の水増し等)で無理に閾値を満たすことも
避ける。

**結論:** v0.4.3-c は §1〜5(metric・oracle・permutation・回帰用契約・プロンプト)の
実装・テストまでを完了として確定し、**Rossmann の実行(build-only preflight 含む)は
次ラウンド(可変長パック設計の専用 preregistration が必要)に持ち越す**。実装済みの
コンポーネントは全て再利用可能——将来 Jigsaw 等の低列数コンペにも同じ制約が及ぶため、
可変長パック設計は Rossmann 固有ではなく共通の次課題として扱う。

## 8. スコープ外(明示的に対象としない)

- Rossmann の `Sales` が 0 の日(休業日)の扱い——既存コンペの評価規約(RMSPE で Sales=0
  の日を除外)は本パイプラインの transfer 区間評価には適用しない(既存 IEEE-CIS/Santander
  同様、公開 LB との直接換算は行わないため無関係)。`Date` は `time_column` として除外し、
  `Open`(休業日フラグ)は他の数値特徴と同様の missingness/dtype フィルタに従わせる(手で
  除外しない——列意味論を使わない原則)。`Store`(店舗ID)も同様に一般的な数値列として
  扱う(IEEE-CIS の `card1`/`addr1` 等の匿名 ID 風数値列を特別扱いしなかったのと同じ)。
- **`Customers` 列は `id_columns` として除外する。** これは技術クラス選定(手法水準の
  hand-picking)ではなく、データ提供の事実に基づく除外——実際の Kaggle test.csv には
  `Customers` 列が存在しない(予測時点では観測できない量)。`TransactionID`/`ID_code` と
  同じ「予測に使ってはいけない付随変数」というカテゴリであり、`id_columns` docstring の
  「target から派生した列」に該当する(Sales と Customers はほぼ線形関係にあり、含めると
  ほぼ自明な回帰になってしまう)。
