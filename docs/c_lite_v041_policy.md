# C-lite v0.4.1 方針 — P1 達成の宣言と Track B への移行

**作成日:** 2026-08-29
**status:** 方針草案(v0.4.0 Track A 世代 1 + 4 つの side-probe の開封結果を統合)
**前提:** [v0.4.0 方針](c_lite_v040_policy.md)、[累積発見台帳](v040_discovery_ledger.md)(102 run)

## 0. 何を変えるか(一段落で)

v0.4.0 は「発見に至る構成の発生」(P1)を主目的に、Track A(構成探索)を世代 1 と 4 つの
side-probe(sol reasoning-effort ablation・scaffold-ladder Stage 1/2・cycle-budget ablation、
計 78 run)にわたって実行した。結果、**opus×P1(claude-opus-5、P1 プロンプト、cycle=4)という
単一の execution configuration が、3 つの独立した study・14 replicate を通じて、false
promotion ゼロのまま 3 つの異なる persistent family(compositional・clear・
delayed_history)を発見した。** これは v0.4.0 が定義した P1 の達成基準
(「同一構成の独立 2 run 以上」での persistent 系発見+Matched Negative の汚染なき棄却)を
満たす。v0.4.0 の停止規則 2(「P1 達成構成が出た時点で Track B へ即時移行」)に従い、**v0.4.1
は Track A のさらなる世代を追わず、Track B(IEEE-CIS blind bridge)の起動を主目的とする。**
Track A で得た知見(scaffold・effort・cycle 予算の効果分離)は、Track B に投入する構成の
選定にのみ使う。

## 1. P1 達成の宣言(証拠)

| 根拠 | suite | 発見 family | false promotion |
| --- | --- | --- | --- |
| gen1(C3、4 replicate) | v040-genA-g01 | persistent_compositional | 0/24 |
| Stage1(L-opus-P1、4 replicate) | v040-scaf-c01 | persistent_compositional, persistent_clear | 0/24 |
| Stage2(T2-opus-P1、6 replicate) | v040-scaf2-d02 | persistent_delayed_history | 0/36 |

同一 execution configuration(claude-opus-5 / P1 / cycle=4 / posterior_commit)が、**3 つの
別々に生成された Suite(master seed が異なる、選抜に使った Suite の再利用なし)で、3 回
独立に、異なる persistent family を発見**している。false promotion は 14 replicate 通じて
一度も出ていない。「一発の偶然」ではなく「構成に帰属できる再現性」という P1 の要件
(v0.4.0 方針§1)を、要求以上の強さで満たしている。

**この宣言の限界:** 発見率自体は低い(3/14 replicate ≈ 21%)。「毎回発見する」構成ではなく
「繰り返せば発見に至る」構成である。Track B(実データ)でも同水準の発見率を期待するのが
妥当で、1 回の run で判定しない設計(§3)にする。

## 2. Track A で確定した知見(v0.4.1 が引き継ぐもの)

### 2.1 モデル・Scaffold・レバーの効果分離

| レバー | 効果 | 根拠 |
| --- | --- | --- |
| **reasoning effort(sol)** | 発見・多様性ともに **effort に対して単調増加**(low→xhigh) | sol ablation(24 run) |
| **scaffold P3(自己批判、新規)** | opus・sol 双方で persistent 系発見の主要経路になった。false promotion を増やさない(opus は 0 のまま、sol は Stage2 で 7→0 に消失=単発の暴走と確認済み) | scaffold-ladder Stage1/2(42 run) |
| **scaffold P2(仮説列挙強制)** | **モデル依存。** fable では効いた(v0.4.0 世代 1: 2→5 件)が、opus には効かない(9=9>7)、persistent 系を一度も割っていない | gen1 + Stage1 |
| **cycle 予算(4→8)** | **effort とは逆方向。** 発見はほぼ横ばい、**多様性は明確に低下**(opus 3.75→2.67、sol 1.67→1.17)。「広く探索」ではなく「深く詰める」方向に働く | cycle-budget ablation(12 run) |
| **codex sandbox(`danger-full-access`)** | 環境修正。修正前は terra が実質全滅していたが、修正後は世代1で発見4件・2件相当まで回復 | 世代1修正 |

**結論:** evidentiary capacity は単一概念ではない。reasoning effort は「広さ・深さの両方」を
押し上げるが、cycle 予算は「深さ」だけを押し上げ「広さ」を犠牲にする。v0.4.1 は **reasoning
effort=xhigh(sol)・cycle=4(両モデル)・scaffold=P3 優先** を既定とする。

### 2.2 累積発見台帳(102 run)からの含意

- persistent ラダー全 4 段階(clear・noisy_proxy・delayed_history・compositional)は
  少なくとも一度は破られた。**「壁」ではなく「低確率事象」**(最頻の persistent_clear でも
  102 run 中 6 件 ≈ 5.9%)。
- grammar-composed 系・observation_routing は「解けた」(50+ 回発見)。今後は主指標から
  外し、false promotion 0 の確認程度に格下げする。
- **単発の suite instance が false promotion を集中的に生む現象が 4 回独立に観測された**
  (gen1 terra/g01、sol ablation high/b05、Stage1 sol×P3/c04、cycle8 sol/e05)。モデル・
  scaffold・effort に依存しない再現パターンであり、v0.4.1 の診断項目に追加する(§5)。

### 2.3 効果量推定の教訓(スクリーニング設計の限界)

scaffold-ladder Stage 1(n=4)は opus×P3 の多様性を「3 倍」と推定したが、Stage 2(n=6)の
確認では実際には「+18%」程度だった。**n=4 のスクリーニング推定値は効果量を大きく
過大評価しうる。** v0.4.1 では、スクリーニング段階の効果量は「方向」の参考にのみ使い、
「倍率」を確定的な数字として引用しない。

## 3. Track B — IEEE-CIS blind bridge(起動)

v0.4.0 方針§4 の設計をそのまま引き継ぐ(受け入れ基準は変更しない)。v0.4.1 が追加するのは
「どの構成を投入するか」の決定のみ。

### 3.1 投入構成

| 構成 | 選定理由 |
| --- | --- |
| **opus×P1(cycle=4)** | P1 を達成した実績構成。基準線として必須。 |
| **opus×P3(cycle=4)** | Stage2 で opus×P1 と同点最高の発見イベント数、かつ多様性で上回る。persistent_clear も発見済み。 |
| **sol×P3×xhigh(cycle=4)** | codex 系で唯一 persistent 系を複数発見(compositional・noisy_proxy)。false promotion は単発の暴走であり Stage2 で 0/36 に消失済み。 |

sol×P1×xhigh(effort ablation の主力構成)は Track B には含めない——sol×P3 が同じ effort
条件でより多くの persistent family を発見しており、information的に優位。fable・terra・GLM
は使用量制約・実績不足のため Track B 初回には含めない(§4)。

### 3.2 Replicate 数

実データでは合成 Suite ほど多数の独立インスタンスを安価に生成できない(時間分離区間は
単一の実データセットから作る)。**各構成 4 run**(3 構成×4=12 run)を初回投入とし、
P2 判定(v0.4.0 方針§4.2 の 4 条件)は「独立 2 run 以上」を要求する——合成の P1 と同じ
再現性要件を実データにも適用する。

### 3.3 実行順序

```text
v0.4.1-a  Track B Suite build(.data/ieee-cis から時間分離、opaque 化、実データ Matched
          Negative、受け入れ基準を build 前に lock)——本方針の承認後、別途実行確認を取る
v0.4.1-b  3 構成 × 4 run = 12 run 実行(danger-full-access・xhigh・cycle=4 を踏襲)
v0.4.1-c  開封・P2 判定。達成すれば「上位解法級・未知構造の実データ発見」を宣言。
          未達なら、合成側の P1 が実データへ転移しなかった理由を transcript 差分で診断
```

**Track B は実データ・不可逆に近い意思決定を伴うため、Suite build の実行前にユーザー確認を
取る**(v0.4.0 方針の「合成→実データ」境界を、本方針でも維持する)。

## 4. 保留にする項目(Track A 側の未消化課題)

1. **単発 suite instance の false promotion 集中現象。** 4 回独立観測されたが未調査。
   Track B と並行して、該当 suite instance の transcript 差分分析を行う価値がある。
2. **GLM(zai)の正式 study。** runner 統合・smoke test 済みだが実 study 未実施。v0.4.1 では
   Track B を優先し、GLM は Track B 完了後(または並行する余力があれば)独立 side-probe として
   投入する。
3. **fable・terra のさらなる検証。** 世代 1 以降深掘りしていない。優先度は Track B より低い。
4. **cycle 予算と P3 scaffold の組み合わせ。** 「cycle を増やしつつ multi-lineage を強制する
   scaffold」があれば、深さと広さを両立できる可能性がある(cycle-budget ablation の考察、
   未検証)。

## 5. 新しい評価基準(v0.4.1 が追加するもの)

1. **累積発見台帳を正本の一部にする。** 各 study の finalize は、単体の discovery event 数
   だけでなく「この発見は台帳に対して新規か」を明示する。
2. **suite-instance レベルの false promotion 集中を診断指標にする。** 1 replicate に
   false promotion が 3 件以上集中した場合、その suite instance を「要注意」として記録し、
   将来の transcript 差分分析の対象リストに追加する。
3. **スクリーニング段階(n≤4)の効果量は「方向」のみ報告し、確定的な倍率として引用しない。**
   確認段階(n≥6)の数字のみを policy 判断に使う。
4. **evidentiary capacity を単一指標として扱わない。** reasoning effort と cycle 予算を
   分けて報告する(§2.1)。

## 6. 不変条件(v0.4.0 から継続)

v0.4.0 方針§7 の Blindness 原則をそのまま維持する:

1. エージェントに構造 family・解法・真値・生成コード・本方針書を見せない
2. プロンプト・契約への追加は「仮定の抽象軸」「証拠手続き」のみ
3. fresh context / opaque view / 暗号化 Truth / transcript 監査 / 出力 Lock 後開封は全 run 維持
4. repair feedback はエージェント自身の数値のみ参照
5. IEEE-CIS の既知解法情報は Controller 文書にも列名・レシピ水準では記載しない

## 7. この方針が Track A で得た証拠にどう対応しているか

| 知見 | 対応 |
| --- | --- |
| opus×P1 が P1 達成基準を満たした | Track B へ移行(v0.4.0 停止規則 2 の発動) |
| P3 がモデル横断で最有力レバー | Track B 投入構成に P3 を 2/3 採用 |
| P2 はモデル依存で opus に効かない | Track B には P2 を含めない |
| cycle 予算は逆効果 | Track B は cycle=4 を維持 |
| n=4 スクリーニングは効果量を過大評価 | Track B の判定は「独立 2 run 以上」の再現要件を維持 |
| suite instance 依存の false promotion 集中 | 診断指標として正式に追加(§5.2)、Track B でも監視 |
