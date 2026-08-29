# C-lite v0.4.3 方針(案)— 複数コンペ検証の頑健化と回帰対応への拡張

**作成日:** 2026-08-29
**status:** 方針草案(v0.4.2 の 2 コンペ確認完了を受けて起案。ユーザー確認前)
**前提:** [v0.4.2 方針](c_lite_v042_policy.md)、
[クロスコンペ統合分析](verification/v042_cross_competition_synthesis.md)、
[IEEE-CIS qualification](verification/v041_track_b_qualification.md)、
[Santander qualification](verification/v042_santander_qualification.md)

## 0. v0.4.2 の到達点と、v0.4.3 で扱う課題

v0.4.2 は 2 つの claim(best-of-population 近傍到達・未知構造発見)を IEEE-CIS・
Santander の**2 コンペで独立に確認した**。これは「単一コンペの偶然ではない」ことの
最低限の証拠だが、まだ次の課題を残している——v0.4.3 はこれらに答えることを目的とする。
**金メダルへの言及は v0.4.2 と同様、依然として対象外。**

1. **「context プーリング」発見は本物の構造か、プロトコルの副作用か、未検証のまま
   確認されていない。** 両コンペ・複数構成で独立に繰り返し現れた最も顕著なパターンだが、
   これが「research/confirmation/transfer × 3 独立 context」という Suite 設計自体が
   誘導する artifact である可能性を否定できていない([クロスコンペ分析](verification/v042_cross_competition_synthesis.md)
   に記載、未検証のまま次に進むべきではない)。
2. **回帰(regression)タスクへの対応が未実装。** 現行 pipeline(AUC ベースの
   preflight/scoring、確率出力を前提とするプロンプト)は分類専用。Rossmann はデータ
   取得済みだが未着手のまま。
3. **技術クラス taxonomy が「コンペ固有の具体技術」水準に偏っている。** 両コンペで
   繰り返し現れたメタ技術(context プーリング、occurrence/sparsity 集約)を
   taxonomy が全く捉えられていない(構造面スコアが IEEE-CIS 0/6・Santander 部分一致
   だった一因)。
4. **opus×P1 のコンペ依存性の原因が未解明。** Santander で 4/4、IEEE-CIS で 1/4。
   「なぜ」が分かっていないまま P3 系を既定にするのは経験則に留まる。
5. **2 コンペでの確認を、より多くのコンペでの一般則に格上げできていない。**

## 1. v0.4.3-a:「context プーリング」発見の由来を検証する(最優先・新規データ不要)

**問い:** promoted パックが繰り返し到達した「3 context は独立regimeではなく単一機構に
支配されている」という claim は、(a) 実データの真の構造の反映か、(b) Suite 設計
(3 独立 context・pack-level 昇格ロジック)が pooling claim を出しやすくする構造的な
バイアスか。

**検証方法(手持ちデータのみで実行可能、新規 agent run 不要):**

1. **Matched Negative パック側で pooling claim がどの程度試みられ、どう扱われたかを
   精査する。** 既に FSPR はほぼクリーン(IEEE-CIS 0/48、Santander 1/48 昇格)——
   つまり negative パックで pooling を主張した場合、ほとんどが正しく `falsified`
   されている。この falsification の**理由**(leave-one-context-out で分離できな
   かった、等)を transcript レベルで確認し、「pooling を主張すれば通りやすい」という
   単純な bias ではなく、「pooling が実際に成り立つ場合にのみ通る」という健全な
   propagation であることを直接示す。
2. **pooling を主張しなかった promoted パックの比率を数える。** 全てが pooling
   claim なら設計バイアスの懸念が強まる。一定数が pooling 以外(activation/sparsity
   集約等、IEEE-CIS で 9 通り中複数)で promoted されていれば、pooling は「よくある
   正しい答えの一つ」であって「唯一の抜け道」ではないと言える。
3. **結果を [クロスコンペ統合分析](verification/v042_cross_competition_synthesis.md)
   に追記し、artifact 説を積極的に反証できたか、あるいは設計修正が必要かを判定する。**
   もし artifact の疑いが強まった場合、pack-level 昇格ロジックか Suite の
   context 分割設計を見直す(v0.4.3-a2 として追加)。

## 2. v0.4.3-b:技術クラス taxonomy の 2 層化

現行 taxonomy(IEEE-CIS・Rossmann・Santander、[docs/controller_reference/](controller_reference/))
は「公開 write-up から抽出した、コンペ固有の具体技術」のみを収録している。
[クロスコンペ分析](verification/v042_cross_competition_synthesis.md)で見つかった
メタ技術(context プーリング、occurrence/sparsity 集約)は、v0.4.2 のスコアリングには
**遡及適用しない**(circular になるため)——v0.4.3 では次の新しいコンペを Suite 化する
**前**に、2 層構造の taxonomy テンプレートを整備する:

- **層1(コンペ固有):** 公開 write-up から抽出する既存の技術クラス(列意味論に依存)。
- **層2(データ形式非依存のメタ技術):** v0.4.2 で観測された「pack-level pooling /
  leave-one-context-out 汎化」「occurrence・sparsity パターンの集約」等、**特定の
  コンペに縛られない技術クラス**。v0.4.3-a の検証結果を踏まえてから確定させる(層2が
  artifact なら taxonomy に入れず、Suite 設計側を直す)。

新しいコンペ(Rossmann 含む)の taxonomy は、当初から層1・層2 の両方を持つ形式で
preregister する。

## 3. v0.4.3-c:回帰(Rossmann)への対応

v0.4.2 policy §5(v0.4.2-f)で見送ったスコープをここで着手する。**分類専用の現行
pipeline を回帰対応に拡張する作業は、既存の classification pipeline と同等の慎重さ
(preflight-only の regression check → 盲検監査 → 初めて agent batch)を踏襲する。**

必要な変更(現時点での見積もり、着手前に preregister すること):

1. **Oracle:** `HistGradientBoostingClassifier` → `HistGradientBoostingRegressor`。
2. **識別可能性・スコアリング指標:** AUC → 相関ベースの指標(Spearman 順位相関、または
   R² gain)。`_auc` に相当する回帰版のヘルパーを追加。
3. **Matched Negative 構築:** `_destroy_target_structure`(完全ランダム permutation)は
   **連続値にもそのまま適用可能**(修正済みのため流用できる、追加の設計変更は不要と
   見込まれる)。
4. **エージェント向けプロンプト:** 現行 `v040_p1.md`/`p3.md` は「確率を1つ出力せよ」と
   明記しており、回帰タスク用には新しいプロンプト variant(連続値予測を指示)が必要
   ——**既存プロンプトを流用せず、新規に作成・凍結(freeze)してから Suite を build
   すること**(プロンプトの事後変更は許されない、という既存の不変条件と同じ)。
5. **提出契約:** `v040_submission_contract`/`validate_v040_submission` が確率前提の
   フィールド(例:予測値の 0-1 範囲チェック等)を持つか確認し、回帰用の contract
   variant が必要か判定する。

**実行順序:** (1) 上記設計を preregister → (2) 小さな合成データで plumbing テスト
(このセッションで `v042-mc-a01` に対して行ったのと同様の build-only regression check
に相当するものを、回帰版の合成データで実施)→ (3) 実 Rossmann データで build-only
preflight チェック(agent run なし)→ (4) 問題なければ 12-run batch を実行。

## 4. v0.4.3-d:実行構成の既定を P3 系に更新

v0.4.2 で観測された「opus×P1 はコンペ依存(Santander 4/4・IEEE-CIS 1/4)、P3 系
(opus×P3・sol×P3)は両コンペで頑健(3/4 以上)」という知見を受け、**v0.4.3 以降の
新規コンペ投入では P3 系構成を主軸とする**。P1 は比較対照(baseline)としてのみ残す
(完全に外すと「P1 とP3の差」という重要な観測軸自体を失うため)。

## 5. v0.4.3-e:コンペ数の拡大(検討事項、優先度低)

2 コンペでの確認を「一般則」へ格上げするには、さらに 1〜2 コンペの追加が有効。候補:

- **Rossmann(回帰対応後、v0.4.3-c 完了後に自動的に対象となる)。**
- **Jigsaw Unintended Bias:** [v0.4.2 方針§7](c_lite_v042_policy.md) で次点評価。
  テーブルデータでなくテキスト分類のため、特徴抽出(埋め込み/TF-IDF 等)の設計が
  別途必要——v0.4.3 の優先度としては v0.4.3-a〜c の後。

## 6. 実行順序

```text
v0.4.3-a  「context プーリング」発見の由来検証(手持ちデータのみ、新規実行不要)。最優先。
v0.4.3-b  技術クラス taxonomy の 2 層化(v0.4.3-a の結果を踏まえて層2を確定)。
v0.4.3-c  Rossmann 回帰対応の設計・preregister・段階的検証・実行
          (実データを扱う判断のため、agent batch 実行前にユーザー確認を取る)。
v0.4.3-d  実行構成の既定を P3 系に更新(ドキュメント上の方針変更、即時反映可)。
v0.4.3-e  (優先度低)Jigsaw 追加の検討。
```

## 7. 不変条件(v0.4.0〜v0.4.2 から継続)

1. エージェントに構造 family・解法・真値・生成コード・本方針書・技術クラス参照物を
   見せない
2. プロンプト・契約への追加は「仮定の抽象軸」「証拠手続き」のみ
3. fresh context / opaque view / 暗号化 Truth / transcript 監査 / 出力 Lock 後開封は
   全 run 維持
4. repair feedback はエージェント自身の数値のみ参照
5. 各コンペの既知解法情報(列名・レシピ水準)は Controller 文書にも記載しない
6. 新規コンペのデータ取得・Suite build・agent batch 実行は実データ・外部サービスを
   伴うため、実行前にユーザー確認を取る(v0.4.3-c の Rossmann agent batch も対象)
7. suite_id にコンペ名を含めない(v0.4.2 で発見・修正済みの盲検リーク——opaque 命名を
   維持)

## 8. ユーザーへの確認事項

1. **この v0.4.3-a〜e の順序・優先度でよいか。** 特に v0.4.3-a(pooling artifact 検証)
   を最優先に置いたのは、これを未検証のまま taxonomy 2層化や新規コンペ追加を進めると、
   誤った基盤の上に積み上げるリスクがあるため。
2. **v0.4.3-c(Rossmann 回帰対応)は、設計・preregister までは承認なしで進めてよいか。**
   実データでの agent batch 実行(12 run)は、既存の不変条件どおり実行前に別途確認を
   取る。
