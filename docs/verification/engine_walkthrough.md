# エンジンを CLI から通した — 記録

**実施:** 2026-09-06
**再現:** `uv run python scripts/engine_walkthrough.py --home /tmp/erl-walkthrough`
**テスト:** `tests/e2e/test_engine_walkthrough.py`(14 手すべての終了コードと replay を検査)

---

## 0. これは何で、何ではないか

[ERL を完成させるための引き継ぎ書](../v050_course_correction.md) §3 の**作業 1 ではない。**
作業 1 は「**実運用で 1 コンペを最後まで回す**」であり、それには実データと実提出が要る。

本記録が示すのはその手前の、**一度も確かめられていなかったこと** ——
**README に書いてある `erlctl` の手順が、並べたとおりに動くか**である。§1.1 が言うとおり
唯一の campaign はエンジンを迂回した。**迂回されたものが動くかどうかは、
迂回されたままでは分からない。**

14 手すべてを**別プロセスの `erlctl` 呼び出し**として実行する
(in-process のテストでは、CLI の経路そのものが検査対象から外れる)。

## 1. 通した手順と結果

    init -> run start -> hypotheses request -> hypotheses record
         -> experiments request -> experiments propose -> experiments select
         -> experiments dispatch -> experiments import-result
         -> beliefs update -> run advance -> run status -> report run -> run replay

| | |
| --- | ---: |
| 手数 | 14(全て終了コード 0) |
| event | **28** |
| observation | 1 |
| 仮説 | 2(1 件が supported へ) |
| report | 4,139 bytes |
| replay | **28 / 28**(hash chain 検証を含む) |

**worker はスタブで、固定の metrics を書くだけである。**コンペについては何も示していない。

## 2. 通す過程で見つけたもの

### 2.1 【欠陥・修正済み】prompt テンプレートを run の home から探していた

`erlctl hypotheses request` は `$ERL_HOME/prompts/<agent>/v1.md` を読む。**home は run の
置き場所**であり、実コンペでは**そのコンペのリポジトリ**である
([引き継ぎ書](../handover.md) の「1 エージェント = 1 `agent/*` ブランチ」)。
そこに prompt は無い。結果は `typer` のエラーではなく **生の
`FileNotFoundError` トレースバック**だった。

**このリポジトリの中で回している限り絶対に踏まない。**エンジンを実運用へ持ち出した
最初の 1 手で踏む。§1.1 が「使われなかっただけかもしれない」と書いた欠陥の実物である。

**修正:** prompt は run ではなくリポジトリに属するものとして
`ERL_PROMPTS_ROOT` → `$ERL_HOME/prompts` → 同梱 `prompts/` の順に解決し、
どれも無ければ**探した場所を並べた `typer` のエラー**を出す。

### 2.2 【欠陥ではない】選定が最初の 2 回、候補を拒否した

| 拒否理由 | 何を守っているか |
| --- | --- |
| `System C epistemic experiments require preregistered likelihood forecasts` | 情報利得を**自己採点ではなく**事前登録した尤度と belief から計算する(仕様 §31) |
| `EIG hypotheses require an explicit alternative: H-001` | **対抗仮説の無い尤度比は識別ではない。**代替仮説の明示を要求する |

**どちらもエンジンが働いた結果である。**walkthrough 側を直して通した
(尤度ベクトルを事前登録し、対抗仮説 H-002 を立てた)。
**この 2 つは、campaign が「スコアの argmax」で回していたときには一度も要求されなかったものである**(§2.2)。

### 2.3 report が欠測を欠測として出す

作業 8 の結果が実際の report に出ている。`preferred_state_total_gap` は **0 ではなく `null`**、
`preferred_state_missing` に 7 次元、`unmeasured_states` に**測っていない 7 状態**が名前で並ぶ。

## 3. これで言えること・言えないこと

| | |
| --- | --- |
| **言える** | ループは**シェルから迂回せずに駆動できる。**event log が残り、そこから report が出て、replay が一致する |
| **言える** | 実運用へ持ち出す最初の 1 手で踏む欠陥が 1 件あり、直った(§2.1) |
| **言えない** | 61 件の enforced が**実コンペで役に立つか。**worker はスタブで、データも提出も無い |
| **言えない** | **作業 1 は未完のままである。**実データ・実提出は都度の明示承認が要る |
