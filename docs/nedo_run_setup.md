# NEDO をエンジンで回すための準備 — 何が揃っていて、何が要るか

**作成:** 2026-09-06
**対象:** [引き継ぎ書](v050_course_correction.md) §3 の **作業 1**(エンジンを実運用で 1 回通す)
**設定:** [`configs/competitions/nedo_baggage_loading.yaml`](../configs/competitions/nedo_baggage_loading.yaml)
**まだ回していない。**着手には人の承認が要る(下記 §4)

---

## 0. 何を「準備」と呼んでいるか

**手順書ではない。**この文書が指すのは、次の 4 つの**実物**である。

| 実物 | どこ |
| --- | --- |
| NEDO 用の run 設定(競技リポジトリを開発させる executor、提出を機械には絶対にさせない予算) | `configs/competitions/nedo_baggage_loading.yaml`(読み込みテストあり) |
| campaign の採点結果をエンジンの課題ごとスコア置き場へ入れる変換 | `scripts/import_nedo_results.py`(**campaign の composite を誤差 0.00000 で再現**) |
| 分解能ゲートを実データへ当てた結果 | [記録](verification/nedo_resolution_gate.md) |
| 世界モデルの NEDO 予測(**符号化前に事前登録**) | [prediction_nedo.md](world_model/prediction_nedo.md) |

## 1. 済んでいること

### 1.1 実データで測定の規律が通った

15 個体 × 128 課題を取り込み、`erlctl measure rank` を当てた。
**15 個体は 7 層にしかならず、首位はラウンド 2 と 3 に跨る 3 体で分解できない**
([記録](verification/nedo_resolution_gate.md))。
「ラウンド 3 がラウンド 2 を超えた」は 128 課題では支持されない。

    uv run python scripts/import_nedo_results.py \
        --results $NEDO_REPO/results/all48 --out .data/nedo/all48.jsonl --verify
    uv run erlctl measure rank --scores .data/nedo/all48.jsonl --spec .data/nedo/all48.spec.json

### 1.2 世界モデルの予測を先に固定した

**点予測は RMC(Representation / Model Coverage)のみ「決定的」、他 12 状態は「記録なし」。**

**そして重要なのはこちら:corpus は NEDO の context セルを 1 件も観測していない**
(8 セル中 6 セルしか埋まっておらず `(0,1,1)` は空)。
**したがって NEDO でテストされるのはチェックリストであって、context 条件付けではない。**
詳細と判定規則は [prediction_nedo.md](world_model/prediction_nedo.md)。

### 1.3 設定が「勝手に提出しない」ことをテストで縛った

`max_final_submissions: 0` / `max_daily_submissions: 0` / `max_public_queries: 0` /
`holdout: strict_blind`。`tests/unit/test_shipped_configs.py` が落ちる形にしてある。
**プラットフォームは 1 日 5 回まで提出を許すので、縛らなければループはそれを使い切る。**

## 2. NEDO 側に必要なもの(**まだ無い**)

`competition_repo` executor は、**競技リポジトリ自身の規約**として
`results/<experiment>/metrics.json` を読む。NEDO 側の現在の出力は
`results/<name>.json` で、形も場所も違う。**ここを合わせる必要がある。**

| 要るもの | 中身 | なぜ |
| --- | --- | --- |
| `results/<experiment>/metrics.json` | 指標名 → 数値のフラットな JSON。最低限 `composite_score`・`fill_score`・`cog_score`・`placement_score`・`soft_item_score`・`stability_score`・`n_gate_failed` | executor が完了判定に使う唯一の下流インターフェース |
| `results/<experiment>/per_task.json` | 既存 `results/*.json` の `per_task` と同じ形(課題ごとの生ベクトル) | 分解能ゲートと再計算に要る。**合成値だけでは順位を検証できない** |

**これは NEDO 側リポジトリへの変更である。**このセッションでは触っていない
(作業ディレクトリの外にある)。**着手の承認と同時に、どちらのリポジトリを変更するかも決めること。**

## 3. 回すときの手順

    export NEDO_RUN_ID=nedo-001 NEDO_SEED=101 NEDO_REPO=$HOME/dev/2026/erl-nedo-baggage-loading
    export LINEAR_API_KEY=...            # ~/dev/2026/.erl-secrets/ から
    uv run erlctl init  --competition nedo-baggage-loading \
        --config configs/competitions/nedo_baggage_loading.yaml --run-id $NEDO_RUN_ID
    uv run erlctl run start --run-id $NEDO_RUN_ID --package docs/nedo_competition_package.json
    uv run erlctl run loop  --run-id $NEDO_RUN_ID --rounds 4 --size 1
    uv run erlctl report run --run-id $NEDO_RUN_ID

`configs/competitions/nedo_baggage_loading.yaml` は `executor.linear_team_id` /
`linear_project_id` を持っていない。**ticket を実際に立てるならこの 2 つが要る**
(`configs/competition.example.yaml` に実 ID がある)。**入れた時点で本物の ticket が立つ** ——
`linear_state_id` を Backlog にしても worker は拾う(README の当該節)。**空打ちはできない。**

## 4. 着手前に決めること(**人の判断**)

1. **競技として回すのか、研究として回すのか。**§2.6 で「目的の置き換えを明示しなかった」ことを
   誤りとして挙げた。**勝つためには貪欲系が正しく、学ぶためには誤っている。**
   締切は 2026-10-19。**どちらで回すかを先に書き出すこと**
2. **`results/` の規約を、どちらのリポジトリに合わせるか**(§2)
3. **実提出をするか。**するなら 1 件ごとに承認する。ループは提出しない設定になっている
4. **世界モデルを NEDO のエージェントへ渡さないこと。**Controller 専有である
   ([coding_rules.md](world_model/coding_rules.md) §8)。渡した相手で予測は検証できない

## 5. これで作業 1 が終わるわけではない

作業 1 の完成条件は「**`erlctl` で 1 コンペを最後まで回した run が 1 本あり、
その event log から `erlctl report run` が出ている**」である(§5 の 1)。
上の手順を実行して初めて満たされる。**設定と変換と予測が揃っただけである。**
