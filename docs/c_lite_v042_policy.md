# C-lite v0.4.2 方針 — Kaggle 金メダルを北極星に、世界モデルへの接近を測る

**作成日:** 2026-08-29
**status:** 方針草案(Track B 初回実行の結果と、目標の明示的な再定義を踏まえて策定)
**前提:** [v0.4.0 方針](c_lite_v040_policy.md)、[v0.4.1 方針](c_lite_v041_policy.md)、
[累積発見台帳](v040_discovery_ledger.md)、[Track B 初回 qualification](verification/v041_track_b_qualification.md)

## 0. 目標の再定義

これまでの v0.4.0/v0.4.1 は「エージェントに構造・解法を教えないまま、未知構造の発見に至る
構成(モデル・プロンプト・パラメータ)を探索する」ことを目的としてきた。この目的自体は
変えないが、**その先に何を置くかを、ここで明示的に定義し直す**:

> **北極星は Kaggle で金メダルを取ることである。** そこへ至る経路は、(a) 解法の多様性——
> 複数のモデル・scaffold・独立試行を通じて多様な発見を積み上げ、その集合が「Kaggle 上位解法を
> ベースに作成した世界モデル」に近づいていくこと、(b) **終了した(closed)複数のコンペティション**
> を使って「未知の構造を盲検で発見できるか」を検証すること、の 2 本柱で構成される。

これまで単一コンペ(IEEE-CIS)だけで検証してきたが、v0.4.2 では**複数コンペへ拡張する**。
単一コンペでの結果は、そのコンペ固有の統計的偶然や suite 設計の欠陥と区別がつきにくい
(実際、Track B 初回はこの問題に直面した——§4 参照)。合成側 Track A が複数の master-seed
suite instance で再現性を確認したのと同じ理由で、Track B も複数の独立したコンペで再現性を
確認する必要がある。

**段階付け:** closed competition は「金メダルを取る」ための**練習・検証環境**であり、
金メダルそのものではない(終了したコンペでは新たに順位はつかない)。v0.4.2 の射程は
「closed competition 群で、盲検のまま世界モデルに近い解法を発見できる構成を確立し、
その発見率・再現性を検証すること」まで。live competition への実際の参加は、この能力が
十分検証された後の、さらに先のマイルストーンとして明示的に切り分ける。

## 1. 「世界モデル」の操作的定義(Blindness 原則との整合)

「Kaggle 上位解法をベースに作成した世界モデル」を、エージェントに見せずに評価基準として
使うには、次のように役割を分離する:

1. **世界モデルは Controller 専有の評価用参照物であり、エージェントへのプロンプト・契約・
   データには一切現れない。** これは v0.4.0 方針§7 の Blindness 原則(「エージェントに
   構造 family・解法・真値・生成コード・本方針書を見せない」)をそのまま Track B/世界モデルへ
   拡張したものである。
2. **世界モデルの構築方法:** 対象コンペごとに、公開されている上位解法の write-up・公開
   kernel の要約から、「その解法が使っている技術クラス」の一覧(タクソノミー)を作る——
   例:「エンティティ/UID 復元によるグループ化」「イベント間時間差特徴」「適切な CV を伴う
   ターゲットエンコーディング」「train/test 分布ずれの adversarial validation」「複数モデルの
   stacking/blending」等、**個別の列名・パイプラインコードではなく技術クラスの水準**で記述する。
   このタクソノミー自体は Controller 側の非公開ドキュメントとして保持し、エージェント成果物
   の post-hoc 分類にのみ使う(合成側の family ラベルと同じ扱い)。
3. **測る指標(世界モデル距離):** 複数の独立した diverse な agent run(モデル・scaffold・
   seed を変えた集合)が発見した構造を、Controller が世界モデルのタクソノミーに post-hoc で
   照合し、(a) **カバレッジ**——世界モデルの技術クラスのうち、population 全体で少なくとも
   一度発見されたものの割合、(b) **新規性**——世界モデルに載っていない、しかし transfer
   region で本物のgainを示した発見(あれば追加の知見)、の 2 軸で記録する。単一 run の
   成否ではなく、**累積発見台帳と同じ「population union」の考え方**を世界モデルに対しても
   適用する。
4. **この指標は「解法を教える」ことにはならない。** タクソノミーはエージェントに一切見せず、
   discovery が起きた**後に**しか参照しない——v0.3.6 以来一貫している「事後に真値を開封する」
   設計と同型である。

## 2. 解法の多様性戦略(Track A で確立したレバーの活用)

v0.4.0/v0.4.1 の side-probe が特定した知見をそのまま踏襲する([v0.4.1 方針§2.1](c_lite_v041_policy.md)):

- **reasoning effort(sol)は発見・多様性ともに押し上げる。** xhigh を既定にする。
- **P3(自己批判)scaffold はモデル横断で persistent 系発見の主経路。** P1 と並べて必ず含める。
- **cycle 予算を増やすのは逆効果**(深さに振れ多様性が下がる)。cycle=4 を維持する。
- **P2(仮説列挙強制)は opus に効かない。** 投入しない。

v0.4.2 で新たに追加する軸:**独立 run 数そのものを増やし、population の多様性で世界モデルの
カバレッジを稼ぐ。** 1 run が単独で世界モデル全体を再現することは期待しない——「多数の
diverse な run の和集合が世界モデルに近づく」という前提(§0)を、replicate 数の設計に
直接反映する。具体的な replicate 数は、コンペごとの世界モデルタクソノミーの技術クラス数
(概算)を見てから preregister する(タクソノミー構築が数値設計に先行する)。

## 3. 複数コンペ検証設計(Track B の汎化)

Track B 初回(`v041_track_b_suite.py`)は IEEE-CIS 専用にハードコードされている
(列選定・時間分割列・target 列名が固定)。v0.4.2 では**コンペ非依存の builder に一般化**し、
新しいコンペを追加するコストを「データを置いて設定を preregister するだけ」にする:

```text
v042_multi_competition_suite.py
  CompetitionSpec(
    competition_id, data_path, time_column, target_column,
    excluded_raw_columns, missingness_threshold, world_model_taxonomy_path,
  )
  build_v042_suite(spec, ...)  # v041 の設計(4候補+4 matched-negative、3 context/pack、
                                 # opaque view、encrypted truth)をそのまま踏襲、
                                 # データソースだけ spec 経由で差し替える
```

**候補コンペの選定基準**(ユーザー確認が必要——§7):
- 終了済み(closed)であること
- ラベル付き訓練データが完全公開されていること(test 側にラベルが無いコンペは Track A の
  ような時間分離 3 区間を作れない——IEEE-CIS で `test_transaction.csv` を使わなかったのと
  同じ理由)
- 上位解法の write-up が複数公開されていること(世界モデルタクソノミーを作れること)
- テーブルデータであること(現行の agent プロトコル・契約が表形式データ前提のため)
- データサイズが扱いやすいこと(IEEE-CIS は ~650MB、同程度〜数 GB を想定)

## 4. Track B 初回の技術的負債——複数コンペ展開の前に必ず直す

[qualification](verification/v041_track_b_qualification.md) で確認した通り、初回 Suite は
Matched Negative パックが 12 run 中 9 run で昇格した。原因分析:一部(`pack-n01`)は
エージェント側の判定閾値の甘さだが、残り(`pack-n02/03/04`)は**Controller 側の permutation
設計(decile 分割 10・baseline が線形ロジスティック回帰)が非線形残差構造を破壊しきれて
いない**ことが複数 run・複数モデルで再現して示唆された。

この欠陥を複数コンペへ複製すると、v0.4.2 全体の FSPR 指標が汚染される。**多コンペ展開の
前に、汎用 builder(`v042_multi_competition_suite.py`)側で以下を修正する:**

1. **baseline モデルをより表現力の高いものに変更する。** 線形ロジスティック回帰では捉え
   られない非線形残差が生き残っていた可能性が高い——木ベースモデル(ExtraTrees/
   HistGradientBoosting 等、sklearn の範囲内で capacity をコンペごとに揃える)へ変更を検討。
2. **decile 分割の粒度を上げる、またはより厳密な conditional permutation(risk score の
   連続値に対する kernel-based / nearest-neighbor マッチング等)を検討する。**
3. **修正後、IEEE-CIS で再検証してから他コンペへ展開する。** 新しい permutation 設計が
   IEEE-CIS の preflight で `abs(gain)` が実質ゼロになることを確認するまで、他コンペの
   Suite は build しない。

## 5. 実行順序

```text
v0.4.2-a  世界モデルタクソノミー構築(Controller 専有、公開 write-up の技術クラス要約)。
          対象コンペをユーザーと確定してから着手(§7)。
v0.4.2-b  Matched Negative 構築法の修正 + IEEE-CIS での再検証(§4)。実データ操作だが
          既存 Suite の再構築であり、新規コンペのデータ取得は伴わない。
v0.4.2-c  汎用 builder(v042_multi_competition_suite.py)への一般化。
v0.4.2-d  追加コンペのデータ取得(Kaggle API 経由、ネットワーク・アカウントを使う操作の
          ため実行前にユーザー確認を取る)。
v0.4.2-e  複数コンペでの Suite build → 実行 → 開封 → 世界モデルカバレッジ評価。
```

## 6. 不変条件(v0.4.0/v0.4.1 から継続、世界モデルへ拡張)

1. エージェントに構造 family・解法・真値・生成コード・本方針書・**世界モデルタクソノミー**を
   見せない
2. プロンプト・契約への追加は「仮定の抽象軸」「証拠手続き」のみ
3. fresh context / opaque view / 暗号化 Truth / transcript 監査 / 出力 Lock 後開封は全 run 維持
4. repair feedback はエージェント自身の数値のみ参照
5. 各コンペの既知解法情報(列名・レシピ水準)は Controller 文書にも記載しない——
   世界モデルタクソノミーは「技術クラス」水準に留め、コンペ固有の具体的実装は記述しない
6. 新規コンペのデータ取得・Suite build は実データ・外部サービス(Kaggle API)を伴うため、
   実行前にユーザー確認を取る

## 7. ユーザー確認が必要な事項

1. **追加するコンペの選定。** §3 の基準(closed・ラベル完全公開・write-up 複数・テーブル
   データ・扱いやすいサイズ)を満たす候補として、Home Credit Default Risk・Santander
   Customer Transaction Prediction・TalkingData AdTracking Fraud Detection 等が考えられるが、
   最終選定はユーザーの判断を仰ぐ。
2. **Kaggle API を使った新規データ取得の実行タイミング。** 既存の `.kaggle/` 認証情報が
   使えることを確認済みだが、外部サービスへのアクセス・帯域を伴うため、v0.4.2-d の実行前に
   改めて確認を取る。
