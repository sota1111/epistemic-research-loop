# C-lite v0.4.0 方針 — Gate 追跡から「発見エージェントの発生」へ

**作成日:** 2026-08-28
**status:** 方針草案(v0.3.9 開封結果を Checkpoint 1 として取り込んだ後に preregistration へ固定する)
**前提:** [v0.3.8 検証](verification/v038_fresh_context_qualification.md)、敵対的レビュー(2026-08-28、
progress.md 収録予定)

## 0. 何を変えるか(一段落で)

v0.3.7→0.3.9 は「測定を正直にする」ための版であり、その役目はほぼ終えた。契約・測定レバーの
限界効用は急落しており、目的(上位解法級・未知構造の盲検発見)と最も相関する能力 —
**行を跨ぐ持続構造の仮説形成と証拠構築** — は契約の厳格化では生まれない。v0.4.0 は評価固定・
集団固定で数値を磨く路線をやめ、**エージェント構成(モデル×エピステミック足場×予算)の
変異と選抜**によって「発見に至る個体が発生する」ことを一次成功条件にする。同時に、合成 Gate と
実データの間に**事前登録された橋**を架け、合成での進歩が目的の進歩であることを検証可能にする。

## 1. 成功条件の再定義(re-preregistration)

v0.3.x の 11 Gate 均等追求を廃し、次の 2 つを **Primary** とする。

- **P1(合成・持続構造の発見個体の発生):** ある agent 構成が、fresh context・盲検・
  evidence-based 条件下で、persistent 系 family(L1–L4 相当)の Behavioral Discovery を
  **同一構成の独立 2 run 以上**で達成し、対応 Matched Negative を汚染なく棄却すること。
  一発の偶然ではなく「構成」に帰属できる再現が要件。
- **P2(実データでの未知構造発見):** IEEE-CIS blind suite(§4)で、ある agent 構成が
  Controller 検証済みの構造発見(隠し transfer gain + 構造破壊プローブ通過 + 実データ
  Matched Negative の非昇格)を達成すること。

旧 Gate 群(個体 median TSDR/TSRR、SBR、LOAO、Brier 等)は **Secondary(診断)** に降格する。
廃止ではない:偽昇格制御(FSPR ≤ 0.20)と evidence-based 条件は P1/P2 の**内部要件**として
存続する。数値を捨てるのではなく、**数値の序列を目的に整合させる**。

## 2. 目標モデル(あるべき姿)の v0.4.0 更新

「目標モデル」とは、**Kaggle 上位に到達しうる研究エージェントのあるべき姿**(To-Be capability
model)を指す。数値はこのモデルへの近さを測る道具であり、目的そのものではない。版ごとに
目標モデル自体を見直す。

### 2.1 v0.3.x の目標モデルとその限界

v0.3.x が暗黙に置いていたあるべき姿は「**正直な測定に耐える研究プロトコルの遵守者**」だった
(自己申告を排し、証拠・provenance・盲検に耐える)。v0.3.8 でこの像はほぼ達成された。しかし
プロトコル遵守は上位解法に到達する**十分条件ではない**ことが実測で判明した:遵守した上で、
行を跨ぐ構造の仮説がそもそも立たない(persistent 系 evidence 失敗 46/116)。

### 2.2 v0.4.0 の目標モデル:8 つの能力柱

Kaggle 上位解法級の発見に至るエージェントのあるべき姿を、構造情報を含まない一般能力として
定義する。各柱に Controller 観測可能な行動署名を対応させる。

| # | 能力柱 | 行動署名(Controller 観測) | v0.3.8 実測 | 目標水準 |
| --- | --- | --- | --- | --- |
| 1 | 課題定式化の懐疑(与えられた定式化を疑い、観測単位・独立性・定常性・生成機構の競合定式化を毎 pack 明示する) | 仮定軸被覆(proposal descriptor から抽出) | 部分的(P1 の 1 文依存) | 全 pack で 4 軸列挙 |
| 2 | **構造仮説の生成力**(行を跨ぐ繰り返し単位・履歴・レジームを自発的に仮説化する) | persistent 系 evidence 段階通過率 | **1–2/24(最大の欠落)** | 構成あたり再現的発見 |
| 3 | **識別実験の設計力**(confounder 保存 null・独立含意・破壊テストを自前設計し、結論と証拠が矛盾しない) | falsification bundle 整合率、null/implication provenance | 自己矛盾 73/95 | 矛盾 0(v0.3.9 で契約化) |
| 4 | 検証の漏れ安全性(時間・fold・エンティティ跨ぎのリークを自力で回避する検証設計) | causal safety、Controller LOCO | 概ね達成 | 維持 |
| 5 | 翻訳と転移(構造を複数の特徴・モデル翻訳へ落とし、選択後悔を小さく保つ) | USTR、selection regret | USTR 1.0(発見条件付き) | 維持・対象拡大 |
| 6 | 較正された自信(昇格判断の確率が現実の的中率と一致する) | Brier / ECE | 0.18 / 0.11 | 維持 |
| 7 | 資源配分(深掘り lineage と広い探索の予算を自律配分する) | deep lineage completion、EECR | 0.64 / 0.35 | 深掘り側へ改善 |
| 8 | 内的検証主義(外部リーダーボードに頼らず、隠し区間前提の自己検証を設計する) | hidden-region 契約下の完走・OOF honesty | 達成 | 維持 |

**v0.4.0 の重心は柱 2・3 である。** 柱 4–8 は v0.3.8 で概ね到達しており、維持要件に回す。
上位解法との関係:実データで上位に立つ解法は、例外なく「データの見かけの単位より上位の
反復単位を発見し、その履歴・連結を検証可能な形で特徴化する」行為を含む。柱 2・3 はその
一般形であり、具体的な解法・構造の語彙を含まない。

### 2.3 目標モデルの使い方

- Track A の選抜基準(§3.2)は柱 2・3 の行動署名に直結させる
- 各世代の報告は「Gate 通過表」ではなく「柱別のギャップ表」を一次様式とする
- 目標モデル自体の更新は版の re-preregistration として記録する

## 2b. v0.3.9 から持ち込む是正(敵対的レビュー対応)

1. **Repair-flip 汚染の定量(v0.3.9 開封時に実施)。** repair retry 前後の transcript から
   resolution / implication の flip を抽出し、「差し戻しで反転した棄却」を層別報告する。
   flip 由来 TSRR は括弧付きで扱い、v0.4.0 の baseline に混ぜない。
2. **implication strength の操作的定義と provenance(v0.4.0 契約)。** 「held-out 区間で計算した
   null 参照統計量(自身の full-refit null 分布に対する位置)」であることを要求し、Null と同様に
   計算 artifact を hash 提出させる。閾値 0.05 は評価側で感度分析(0.02/0.05/0.10)を併記する。
3. **多重性と停止規則(§6)。**

## 3. Track A — 構成探索による「発生」(variation–selection)

### 3.1 変異軸(すべて構造情報を含まない generic 軸)

| 軸 | 水準(初期世代) |
| --- | --- |
| LLM(実行基盤) | Claude 系:claude-fable-5 / claude-opus-5(v0.3.x 基準線)/ claude-sonnet-5 / claude-haiku-4-5。codex 系:sol / terra / luna の 3 モデル × 各モデル内のリーズニング努力量水準(モデルとリーズニングは独立の副軸として扱う) |
| エピステミック足場 | P1(現行)/ P2: 仮説列挙の広さを強制(cycle 冒頭に観測単位・独立性・定常性・生成機構の各仮定について競合仮説を明示列挙)/ P3: 自己批判パス(昇格前に「この証拠で最も強い反対仮説」を 1 cycle 使って攻撃) |
| 探索予算 | max cycles 4(現行)/ 8(深掘り許容) |
| Lineage | S1 固定(v0.3.8 で FSPR 低下に寄与、監査可能) |

### 3.1.1 LLM 多様化の規律

LLM は目標モデル(§2)ではなく、**変異の素材**である。あるべき姿(柱 2・3)に到達する構成を
探すために、推論の癖が異なる基盤を widest に張る:

1. **Claude 系 4 tier**(fable-5 / opus-5 / sonnet-5 / haiku-4-5)と **codex 系 3 モデル**
   (sol / terra / luna)を変異軸に置く。codex 側は**モデルとリーズニング努力量が独立の
   2 副軸**である(sol の中にも複数のリーズニング水準がある)。全組合せは張らず、世代 1 では
   「モデル間比較(既定リーズニング)」を先に行い、有望モデルに対してのみリーズニング水準の
   ablation を世代 2 で行う。実機確認(2026-08-28):`claude -p --model claude-fable-5` 動作、
   codex は `codex exec -m gpt-5.6-sol / gpt-5.6-terra / gpt-5.6-luna` の 3 モデルとも動作
   (既定 reasoning effort は xhigh、`-c model_reasoning_effort` で切替可能)。
   世代 1 の 6 構成:fable-5×P1 / fable-5×P2 / opus-5×P1(基準線)/ sonnet-5×P2 /
   sol×P1 / terra×P1。haiku-4-5・luna・P3・リーズニング ablation・cycle 8 予算は世代 2 の
   候補プールへ(6 slot × 4 replicate の設計上の制約による preregistered 順延)。
2. **基準線の並走。** claude-opus-5 arm(v0.3.x と同一基盤)を必ず含め、「基盤効果」と
   「足場効果」を分離できる比較設計を保つ。
3. **混成集団の意味。** SBR・相補性は同一モデルでは頭打ちの公算(敵対的レビュー攻撃 4)。
   異基盤混成は「盲点がモデル水準にある」仮説の直接検定になる。世代 2 以降、集団評価
   (union・相補性)は**異基盤混成集団**でも計測する。
4. **Provenance。** `run_meta.json` に model id・CLI 名・version を記録し、世代ごとの割当を
   preregistration で固定。世代途中の変更は行わない。
5. **契約の同一性。** どの基盤でも Suite・契約・盲検・Lock 手順は同一。codex 系 run でも
   agent view / deny 相当の隔離(read-only sandbox + 作業ディレクトリ制限)と transcript 保存を
   同水準で構成できることを、本採用前の隔離検証項目とする。

P2/P3 は**仮定の種類(独立性・観測単位・定常性・生成機構)しか名指ししない**。これらは P0 時代
から prompt に存在する抽象軸であり、構造 family・演算・語彙は一切含めない(§7)。

### 3.2 選抜機構

- **世代 1:** 6 構成 × 4 fresh run(= 24 run、従来 1 版と同予算)を、persistent 系を厚くした
  新 Suite(§5)で実行。選抜基準は P1 の前段指標:「persistent 系 Behavioral Discovery 件数
  (Matched Negative 棄却込み)」。TSDR median ではなく**発見イベントの計数**で選ぶ。
- **世代 2:** 上位 2–3 構成を、**新規生成した別 Suite インスタンス**で各 6–8 run 再現確認
  (構成へのメタ過適合を防ぐため、世代ごとに master seed を替え、選抜に使った Suite は再利用しない)。
- **確認:** 世代 2 を通過した構成のみ P1 判定(独立 2 run 再現)へ。通過構成が Track B へ進む。

「発生」の operational な意味はこれである:**どの構成が発見を再現的に出すかを探索し、出た構成を
選抜・増幅する**。集団 3 identity 固定・同一モデルの旧設計では、盲点がモデル水準にあるため
何版回しても「発生」は起きない(敵対的レビュー攻撃 4)。

### 3.3 診断(数値の新しい使い方)

- 仮説空間被覆:proposal descriptor から「検定された仮定軸」の被覆を Controller が抽出
  (行動レベル多様性。IRD のような意味的多様性は使わない)
- 深さ:lineage あたり cycle 数、deep lineage completion
- 上位構成の transcript 差分分析(v0.3.8 で有効だった手法の一般化)

## 4. Track B — IEEE-CIS blind bridge(事前登録する橋)

合成 Gate の予測妥当性を検証可能にするため、**今**受け入れ基準を固定する。

### 4.1 Suite 構成

- `.data/ieee-cis` から時間分離した 3 context(research / confirmation / transfer は時間順)
- 列名 hash 化・ID 不透明化・行 permutation(v0.3.8 と同じ opaque view 機構)
- **実データ Matched Negative:** 候補構造クラスを破壊した対照 pack(周辺分布・時間相関を保存する
  Controller 側 permutation で生成し、同一の見かけ統計を持たせる)
- Truth に相当するものは「Controller 側プローブ定義+隠し区間ラベル」として暗号化保存

### 4.2 発見判定(P2)— エージェントには一切開示しない

1. Locked translation の隠し transfer 区間 gain が、Controller が用意した capacity-matched
   baseline pipeline を上回る(閾値は build 時に oracle-free に事前固定)
2. **構造破壊プローブ:** transfer 区間で候補連結構造を Controller が破壊すると、当該 agent の
   gain が消失する(gain が生き残る場合は表面統計への適合であり構造発見と認めない)
3. 実データ Matched Negative を昇格していない(FSPR 制御)
4. Evidence bundle(null provenance・implication provenance・LOCO)が合成側と同一契約で有効

「上位解法に至る可能性」はここで初めて操作化される:上位解法の**答えを照合するのではなく**、
「破壊すると性能が消える連結・時間構造を、自力で見つけて使ったか」を判定する。既知解法の
語彙・列名・レシピは、本文書を含むいかなる artifact にも書かない。

## 5. 新 Generator family — 構造文法(未知性の強化)

同一 Synthetic 系統へのメタ過適合(レビュー攻撃 5)への対処として、v0.4.0 で
**structure-grammar generator** を追加する:持続効果・遅延履歴・レジーム切替・階層キー・
経路依存などの**モチーフを文法から機械合成**し、preflight(識別可能性)を通った構造だけを
Suite 化する。設計者(私)も個々のインスタンスの形を事前に知らないため、「未知の構造」への
一般化を合成側でも検証できる。世代 2 の再現確認と P1 判定はこの新 family を含む Suite で行う。

## 6. 予算・多重性・停止規則

- **版予算:** Track A は最大 3 世代(≈ 24 + 20 + 12 run)。世代を跨ぐ選抜は preregistered
  基準のみで行い、事後の基準変更は re-preregistration として明記する。
- **停止規則 1(合成の切り上げ):** 世代 2 終了時点で persistent 系発見を再現する構成が
  1 つも無い場合、合成での構成探索を打ち切り、最良構成でも Track B を実行して橋の予測妥当性
  データを取る(合成完璧主義で目的を無期限延期しない)。
- **停止規則 2(成功時):** P1 達成構成が出た時点で Track B へ即時移行。旧 Gate の完全通過は
  Track B の前提条件に**しない**。
- Communication / population scaling は引き続き封印(個体の発生が先)。

## 7. 不変条件(Blindness 原則)

1. エージェントに構造 family・解法・真値・生成コード・本方針書を見せない
2. プロンプト・契約への追加は「仮定の抽象軸」「証拠手続き」のみ。Entity/Time/Feature の
   具体語彙・演算名を追加しない
3. fresh context / opaque view / 暗号化 Truth / transcript 監査 / 出力 Lock 後開封は全 run 維持
4. repair feedback はエージェント自身の数値のみ参照
5. IEEE-CIS の既知解法情報は Controller 文書にも列名・レシピ水準では記載しない

## 8. 実行順序

```text
Checkpoint 1  v0.3.9 開封:repair-flip 汚染定量 + TSRR/matched-negative 予測の検証
              → 整合性契約の効果を「flip 由来」と「実質」に分けて記録
v0.4.0-a     implication provenance 契約 + structure-grammar generator + persistent 厚め Suite
             + 目標モデルを claude-fable-5 へ更新(opus-5 基準線 arm を並走)
v0.4.0-b     Track A 世代 1(6 構成 × 4 run)→ 選抜 → 世代 2(新 Suite で再現確認)
v0.4.0-c     Track B IEEE-CIS blind suite build(受け入れ基準は build 前に lock)
v0.4.0-d     P1 通過構成(または停止規則 1 発動時は最良構成)で Track B 実行
```

## 9. この方針が敵対的レビューの各攻撃に答えているか

| 攻撃 | 対応 |
| --- | --- |
| 1 契約適合の学習 | Checkpoint 1 で flip 定量。以後、契約レバーは凍結し能力レバーへ |
| 2 未較正スカラー | implication の操作的定義 + provenance + 閾値感度分析 |
| 3 目的関連能力の停滞 | 選抜基準を persistent 系発見イベントに直結(P1) |
| 4 モデル水準の盲点 | モデルを preregistered 変異軸に。SBR は診断へ降格 |
| 5 メタ過適合・橋の欠如 | 構造文法 generator + 世代間 Suite 非再利用 + P2 事前登録 |
| 6 多重性・停止規則 | 版予算 3 世代 + 停止規則 2 本 |
| 7 Gate 序列の歪み | P1/P2 を Primary に、旧 Gate を診断に再序列 |
