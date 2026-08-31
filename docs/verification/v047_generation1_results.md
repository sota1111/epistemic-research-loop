# v0.4.7 世代1(探索population)結果 — Santanderの核心技術に本プロジェクト初到達

**目的:** [c_lite_v047_policy.md](../c_lite_v047_policy.md)§2.1で計画した世代1
(1競技あたりsol 8体+opus 4体=12体)の実行結果。両競技とも実際のKaggle test.csv全行
(IEEE-CIS 506,691行・Santander 200,000行)を各エージェントに提供し、実test.csv向けの
`final_predictions.csv`を生成させた——本プロジェクトで初めて、エージェントが「本物の
train/test分布」に触れたラウンドである。

## 0. 実行サマリ

- IEEE-CIS(`v047-suite-a01`):12体中11体が完了(`agent-06-r2`はopus・3時間タイムアウト
  ——クラッシュではなく制限時間到達、[env var盲検インシデント](v047_env_var_blindness_incident.md)
  とは別件)。10/11がbaseline超え。
- Santander(`v047-suite-b01`):12体全て完了、12/12がbaseline超え。
- 盲検監査:IEEE-CISはクリーン。Santanderで1件の実インシデント
  (`agent-06-r2`、env var経由の実リポジトリパス漏洩、[別記](v047_env_var_blindness_incident.md)——
  悪用の証拠なし、submission候補・世代2親候補からは除外)、1件の既知false positive
  (`agent-03-r2`、score_confirmation.py自己参照の残存パターン、既に確認済みの無害な型)。

## 1. 最重要発見:Santanderの核心技術(#1 real/synthetic行判定)に本プロジェクト初到達

[v0.4.4-b](v044_cross_competition_synthesis.md)で確立し、[v0.4.6](v046_low_effort_opus_results.md)で
n=26まで拡張しても崩れなかった決定的否定結果——「Santanderの1st place技術(頻度
エンコーディング・real/synthetic行判定)には、列数・population・reasoning effort・
エージェントモデルのいずれを変えても到達しない」——が、**opus 2体(`agent-05-r2`・
`agent-06-r1`)によって独立に破られた**:

> real_test is exactly half synthetic. Counting, per column, how often each value occurs
> inside real_test: precisely 100,000 rows have ZERO features whose value is unique, and
> the other 100,000 average 31 unique-valued features [...] That 100,000/100,000 split is
> the signature of row augmentation by per-column resampling from the real rows.
> (`agent-05-r2`)

> real_test is not a homogeneous sample. Exactly 100,000 of its 200,000 rows contain zero
> values that are unique within their column, while the other 100,000 have 16 such values
> on average [...] That is the signature of 100k synthetic rows built by resampling each
> column independently from the 100k genuine rows. (`agent-06-r1`)

両者とも、実際のSantander 1st place解法が使う診断手法(列ごとの値の出現回数)を
使い、**正確に100,000/100,000という実際の比率**まで言い当てている。

**なぜこれが150 run超で今まで一度も起きなかったか、決定的な説明が得られた:**
この構造は**実際のKaggle test.csv固有の性質**であり、train.csvには存在しない
——v0.4.0〜v0.4.6の「ローカル封印済みtransfer」は常にtrain.csvからの無作為
抽出(またはtrain.csvの一部)だったため、**この現象そのものがエージェントに
提示されたデータの中に一度も存在しなかった**。列数・population・effort・モデルの
どのレバーを引いても見つからなかったのは、探索能力の限界ではなく、**信号が
物理的に不在だった**ためだった、と今回のラウンドで確定した。v0.4.7の
「実test.csvを見せる」という設計変更が、この探索の袋小路を一発で解消した。

**ただし、匿名化された本設定では実用的な性能向上には直結しなかった点も両者が
正直に報告している**——`agent-05-r2`:「頻度エンコーディングを試したが+0.001 AUC
止まり(連続値特徴では出現回数が周辺密度の決定論的な関数になり、追加情報を
持たない)」。実際の公開解法は非匿名化の生の値・列の意味論を利用できたのに対し、
本プロジェクトの匿名化数値だけでは、構造は発見できても、そこから追加の予測力を
引き出せなかった——「発見」と「活用」は別問題である、という重要な但し書き。

**sol 8体では1体も到達しなかった**——[v0.4.6](v046_low_effort_opus_results.md)の
「opusはsolにない構造発見に到達する」という知見を、今回もっとも劇的な形で再確認した。

## 2. 発見2:IEEE-CISで初めて「本物の」train/test分布シフトを検出・診断(`agent-05-r2`)

これも実test.csv公開によって初めて可能になった観察。`agent-05-r2`(opus・P1)が
research(train.csvの一部)とreal_test(実test.csv)の間でadversarial validationを
実施したところ、AUC 0.762(null 0.499)という強いシフトを検出した。**さらに掘り下げ、
これが自分自身のデータ読み込み処理由来の測定バグ(float64/float32混在)であることを
突き止めて修正し、修正後も残る「本物の」シフト(0.663)を特定した**——UID/エンティティ
特有ではなく高次の共起構造に拡散しており、狙った補正はできないと判断し、
importance weighting等の「未検証の補正」はあえて適用せず、正則化を強めるという
保守的な対応を選んだ。

対照的に`agent-06-r1`(opus・P3、IEEE-CIS)は同種のシフト検出に対し、
**density-ratio(importance)weightingによる補正を実際に適用した**——同じ「シフトを
見つけたらどうするか」という問いに対し、2つの独立したopus runが異なる、
それぞれ理由のある結論に達している。これは探索枠(§4)の有力候補。

## 3. adversarial validationとP1アーム:v0.4.6の「揺らぎ」がさらに広がった

[v0.4.6](v046_low_effort_opus_results.md#2-応答変数2二値adversarial-validationの出現--p3の必要条件性が初めて崩れた)で
初めてP1アームでの出現(2件)が観測されたが、今回はさらに広がった:IEEE-CISだけで
P1アーム2件(`agent-01-r1`系の分布シフトチェック、`agent-05-r1`・`agent-05-r2`
いずれもP1)が確認された。P3アームでの出現率は引き続き高いが、**「P3が実質的な
ゲート」という当初の理解は、v0.4.6に続き今回も部分的にしか支持されない**——
むしろ「十分に周到なエージェント(特にopus、あるいはfeedbackループ込みの設計)は、
アームを問わず標準的なEDA手順としてこれを行うようになりつつある」という、
より一般的な仮説の方が今のデータに合う。

## 4. 世代1・ローカルAUC結果(全23 run、baseline比較)

**IEEE-CIS(baseline 0.8533、11 run中10がbaseline超え):**

| run | config | model | local transfer AUC | baseline超え |
| --- | --- | --- | ---: | :---: |
| agent-02-r2 | low-P3 | sol | **0.8784**(最良) | ✓ |
| agent-02-r1 | low-P3 | sol | 0.8780 | ✓ |
| agent-05-r2 | opus-P1 | opus | 0.8732 | ✓ |
| agent-04-r2 | xhigh-P3 | sol | 0.8730 | ✓ |
| agent-06-r1 | opus-P3 | opus | 0.8692 | ✓ |
| agent-01-r1 | low-P1 | sol | 0.8645 | ✓ |
| agent-05-r1 | opus-P1 | opus | 0.8637 | ✓ |
| agent-04-r1 | xhigh-P3 | sol | 0.8597 | ✓ |
| agent-03-r1 | xhigh-P1 | sol | 0.8556 | ✓ |
| agent-03-r2 | xhigh-P1 | sol | 0.8555 | ✓ |
| agent-01-r2 | low-P1 | sol | 0.8530 | ✗(僅差) |
| agent-06-r2 | opus-P3 | opus | — | タイムアウト(不完了) |

**Santander(baseline 0.7914、12/12がbaseline超え):**

| run | config | model | local transfer AUC | baseline超え |
| --- | --- | --- | ---: | :---: |
| agent-05-r1 | opus-P1 | opus | **0.8854**(最良) | ✓ |
| agent-06-r1 | opus-P3 | opus | 0.8762(★real/synthetic発見) | ✓ |
| agent-06-r2 | opus-P3 | opus | 0.8590 | ✓(env漏洩、除外対象) |
| agent-05-r2 | opus-P1 | opus | 0.8565(★real/synthetic発見) | ✓ |
| agent-04-r1 | xhigh-P3 | sol | 0.8537 | ✓ |
| agent-03-r1 | xhigh-P1 | sol | 0.8522 | ✓ |
| agent-04-r2 | xhigh-P3 | sol | 0.8466 | ✓ |
| agent-03-r2 | xhigh-P1 | sol | 0.8452 | ✓ |
| agent-02-r2 | low-P3 | sol | 0.8339 | ✓ |
| agent-01-r1 | low-P1 | sol | 0.8338 | ✓ |
| agent-01-r2 | low-P1 | sol | 0.8311 | ✓ |
| agent-02-r1 | low-P3 | sol | 0.8198 | ✓ |

**注目すべき点:** Santanderの「最良」個体(`agent-05-r1`、AUC 0.8854)は、real/synthetic
行判定という本ラウンド最大の発見をした2体(`agent-05-r2`・`agent-06-r1`、AUC 0.8565・
0.8762)より**高いスコア**を出している——「最良性能」と「最も新規性の高い発見」が
別の個体に宿っている、という結果になった。§2.3(探索/exploitation両枠の設計)が
まさにこの状況を見越したものであり、設計の妥当性を裏付けている。

## 5. 世代2の親候補(§2.2、ローカルAUC最良個体)

- **IEEE-CIS:`agent-02-r2`**(sol・low effort・P3、AUC 0.8784)
- **Santander:`agent-05-r1`**(opus・P1、AUC 0.8854)

(`agent-06-r2`はローカルAUCでは3位相当だが、[env漏洩インシデント](v047_env_var_blindness_incident.md)
により親候補から除外済み)

## 6. 探索枠(§2.3)の多様性キャラクタリゼーション(選定はまだ確定させない)

主要な「異なる着眼点」のクラスタ:

1. **加法的コンパクトモデル + 構造発見なし系**(sol低effort中心、IEEE-CIS
   agent-01/03、Santander agent-01/02/03/04):素直な特徴プロファイリング+
   GBM/線形モデル比較。個体間の差は小さい。
2. **compositional/ratio構造発見系**(IEEE-CIS agent-02・agent-04・agent-05・
   agent-06):count/amountペア・compositional比率の発見(v0.4.6と同型、sol・opus
   双方で再現)。
3. **real/synthetic行判定系**(Santander agent-05-r2・agent-06-r1):★本ラウンド
   最大の新規発見(§1)。
4. **分布シフト診断・対応系**(IEEE-CIS agent-05-r2の「測定バグ発見+保守的な
   非補正判断」・agent-06-r1の「density-ratio補正の実施」):同じ問いに異なる
   結論を出した好対照。
5. **isotropic quadratic/dispersion系**(Santander agent-05-r1・opus全般):
   v0.4.6で確立した層1#2拡張パターンの継続的再現。

探索枠2つの最有力候補:IEEE-CIS側は`agent-05-r2`(測定バグ発見+シフト診断、
クラスタ2と4の橋渡し)、Santander側は`agent-06-r1`(real/synthetic発見の非タイント版、
`agent-05-r2`より高いAUC)。ただし最終選定は世代2完了後、ユーザーの許可を得て
実際にsubmission.csvを作る段階で確定する。

## 正本

- [c_lite_v047_policy.md](../c_lite_v047_policy.md)
- [env var盲検インシデント記録](v047_env_var_blindness_incident.md)
- [v0.4.6結果(opus screeningの先行知見)](v046_low_effort_opus_results.md)
- 生データ:`docs/v047_v047_suite_a01_diagnostics.json`・`v047_suite_b01_diagnostics.json`
