# C-lite v0.4.6 方針 — reasoning effort=low での「全列×フィードバック×アーム」再検証

**作成日:** 2026-08-31
**status:** 方針草案(ユーザー指定の制約に基づき起案。実験計画のみ、実行は未承認)
**前提:** [v0.4.5 方針](c_lite_v045_policy.md) / [v0.4.5 要因計画結果](verification/v045_factorial_design_results.md)、
[v0.4.4 方針](c_lite_v044_policy.md)

## 0. 背景・動機

直近のユーザーからの質問(「リーズニングの違いによる多様性や未知の構造の発見の性能の
違いはありますか？」)への回答で、既存データから次の2点が判明した:

1. **生の性能(transfer AUC)は reasoning effort に対してコンペ依存**——Santander は
   ほぼ単調(low<medium<high<xhigh)、IEEE-CIS は非単調(high effort が谷になる)。
2. **技術クラスの多様性・未知構造の発見は reasoning effort にほぼ左右されない**——
   adversarial validation は P3 アームの低・中・高・xhighの**全4水準**で独立に出現し、
   effort の高低は関係なかった。一方 Santander の実際の公開技術は xhigh を含む
   全水準・全ラウンド(n=22)で一度も発見されなかった。

ただし、この2点はいずれも**「全列 + フィードバックあり」という単一のフィードバック
条件下でのeffort比較**(`v044-suite-a01`/`b01` のscreeningラウンド)にとどまる。
[v0.4.5のDOE](c_lite_v045_policy.md)はフィードバック要因を分離したが、effortはxhighに
固定していたため、**「フィードバックなし条件でeffortを下げるとどうなるか」
「effortが低くてもフィードバックが性能・発見の質を補えるか」は未検証のまま**である。

今回、ユーザーから次の制約が与えられた:

1. **reasoning effort = low に固定**(高コストのxhighではなく、低コストな水準での
   再現性・実用性を検証する)
2. **フィードバック機構は{None, Iterative}の両方を要因として維持する**
3. **列数は全列のみを使う**(10列条件は本ラウンドで扱わない——v0.4.5で列数の主効果が
   明確になり、10列を維持する理由が薄れたため)
4. **少数の Opus(claude-opus-5)を含める**——[v0.4.5方針](c_lite_v045_policy.md)以来
   「F5(エージェントモデル)はClaude/opus quota枯渇のため検証不能」と記録してきたが、
   quotaに余裕ができたため、小規模な screening として組み込む(下記§2・§3)。

## 1. この設計が答える問い

1. **「低reasoning effort × フィードバックあり」は、xhighに迫る性能を出せるか?**
   もし出せれば、フィードバックループ(疑似採点による反復)は高価なreasoning effortの
   代替になりうる——実務上重要な知見になる。
2. **P3→adversarial validation の紐付けは、effort=lowでも(フィードバックの有無を
   問わず)成立するか?** 既存データ(`F4-low-P3`、全列+feedback)ではn=1で示唆されて
   いるのみ。フィードバックなし条件でも同じパターンが出るかは全くの未検証。
3. **v0.4.5で発見した「feedbackの主効果はコンペ依存(IEEE-CISで強・Santanderで弱)」
   は、effort=lowでも同じ方向・大きさで見られるか、それともeffortとfeedbackの間に
   交互作用があるか?** 「reasoning力が低いエージェントほど、feedbackによる反復補正の
   価値が相対的に大きくなる」という仮説は理論的にもありうる——初手の質が低いほど、
   試行錯誤による修正の余地が大きいため。
4. **(少数のopusで探索的に)sol以外のモデルでも同じ結論が成り立つか?** 本セッションの
   全知見(P3→adversarial validation、列数・feedbackの主効果、その競技依存性)は
   これまで**sol単独**でしか確認されていない。エージェントモデルという別次元でも
   同じ構造が見えるかは、これまで一度も検証されていない盲点だった。少数の opus run は
   統計的な結論を出すためではなく、**「sol固有の癖ではなく、より一般的な現象らしいか」
   の一次スクリーニング**として位置づける。

## 2. 要因の整理

| 記号 | 要因 | 本ラウンドでの扱い |
| --- | --- | --- |
| F1 列数 | 全列に固定(10列条件は本ラウンドで扱わない) |
| F2 フィードバック機構 | {None, Iterative} 可変(主要因) |
| F3 プロンプトアーム | {P1, P3} 可変(主要因) |
| F4 reasoning effort | sol側はlowに固定(v0.4.5のxhigh固定と対をなす断面)。opusには
  このharnessでreasoning effortダイヤルが存在しないため適用外(モデル自体の既定挙動) |
| F5 エージェントモデル | **主力はsol(低コストで4セルを本格的にn=4まで確認)。
  加えて少数のopus(claude-opus-5)をn=1/セル/競技のscreeningとして追加**——
  統計的検定ではなく「sol固有の癖ではなさそうか」の一次確認 |

つまり本ラウンドは、v0.4.5と同じ2×2要因計画(フィードバック×アーム)を、
effort=lowという新しい断面で実施しつつ、同じ4セルにごく少数のopus screeningを重ねる。

## 3. 設計表

**sol(主力、n=4/セル/競技が目標):**

| セル | フィードバック | アーム | データ源 | 状態 |
| --- | --- | --- | --- | --- |
| I | None | P1 | — | 新規構築(n=4×2競技) |
| J | None | P3 | — | 新規構築(n=4×2競技) |
| K | Iterative | P1 | `v044-suite-a01`/`b01` の `F4-low-P1`(既存n=1/競技)+新規n=3/競技 | 一部既存、追加構築 |
| L | Iterative | P3 | `v044-suite-a01`/`b01` の `F4-low-P3`(既存n=1/競技)+新規n=3/競技 | 一部既存、追加構築 |

sol新規実行数 = (I:4 + J:4 + K:3 + L:3) × 2競技 = **28 run**。
既存の`F4-low-P1`/`F4-low-P3`(各競技1run、盲検監査済み)をセルK/Lにそのまま合算する。

**opus(少数screening、n=1/セル/競技):**

| セル | フィードバック | アーム | 状態 |
| --- | --- | --- | --- |
| I-opus | None | P1 | 新規構築(n=1×2競技) |
| J-opus | None | P3 | 新規構築(n=1×2競技) |
| K-opus | Iterative | P1 | 新規構築(n=1×2競技) |
| L-opus | Iterative | P3 | 新規構築(n=1×2競技) |

opus新規実行数 = 4セル × n=1 × 2競技 = **8 run**。

**合計新規実行数:28(sol) + 8(opus) = 36 run。**

## 4. 参照比較(既存データ、再実行不要)——effort×feedbackの交互作用を追加コストゼロで評価

同一の列数・フィードバック条件でeffort=xhighの結果が既にあるため、再実行せず
参照点として使う:

- セルG/H(`v044-suite-a01/a02/a03`・`b01/b02/b03`、全列+feedback+xhigh、
  P1:n=4/競技・P3:n=11/競技) vs 本ラウンドK/L(全列+feedback+low)
- セルE/F(`v044-suite-a05`・`b05`、全列+no-feedback+xhigh、各n=4/競技)
  vs 本ラウンドI/J(全列+no-feedback+low)

これにより、新規構築ゼロで「effort×feedback×アーム」の3元交差を評価できる
——4つの新規セル(I・J・K・L)と4つの既存セル(E・F・G・H)を組み合わせた、
実質2×2×2(effort×feedback×アーム、列数=全列固定)の分析になる。

## 5. 分析計画

- **応答変数1(連続値):transfer AUC。** 4象限(low×no-fb=I/J、low×fb=K/L、
  xhigh×no-fb=E/F、xhigh×fb=G/H)のセル平均を比較し、feedbackの効果量が
  effort水準で変わるか(交互作用)を見る。特に問い1(低effort+feedbackがxhighに
  迫れるか)は、K/LのAUCをG/Hと直接比較することで判定する。
- **応答変数2(二値):adversarial validation出現率。** P3アーム限定で、
  low×no-fb(J)・low×fb(L)・xhigh×no-fb(F)・xhigh×fb(H)を比較する。
  「P3さえあれば、effort・feedbackの組み合わせに関係なく出現するか」を検証する
  ——もしJ・Lがいずれも高頻度で出現すれば、「P3が唯一のゲート条件であり、
  effortもfeedbackも出現の有無そのものには影響しない(出現率の微調整のみ)」という
  v0.4.5の結論がeffort軸でも成り立つことになる。
- **opus screening(n=1/セル/競技、統計的検定なし)。** sol側で確定した主要パターン
  (P3アームでのみadversarial validationが出現する等)がopusの8 runでも定性的に
  同じ方向に見えるかを目視確認する。**一致しなければ「sol固有の現象」に格下げし
  追加確認の優先課題とする。一致すれば「モデルを跨いだ頑健な現象」として確度が
  上がるが、n=1のため確定的な結論(出現率の数値等)は出さない**——単一replicateの
  noveltyを過信しないという[v0.4.3-fの教訓](c_lite_v043_policy.md)をここでも適用する。

## 6. 実装方針

既存インフラ(`build_v044_suite`の`column_limit=None`・`enable_confirmation_scoring`
パラメータ、v0.4.5-bで実装済み)がそのまま使えるが、**opus対応には
`scripts/run_v044_agent.py`の一般化が新たに必要**——現状このスクリプトは
`command = ["codex", "exec", ..., "-m", "gpt-5.6-sol", ...]`とCLI・モデルを
決め打ちしている(docstring通り「Sol/codex only」)。config辞書自体は既に
`cli`/`model`フィールドを持つ汎用的な形をしている(v0.4.0〜v0.4.3で
`cli: "claude", model: "claude-opus-5"`を使ってきた実績あり、
`scripts/run_v040_agent.py`の`_command()`が参照実装)ため、以下の変更で足りる:

1. **`run_v044_agent.py`にCLI分岐を追加。** `run_v040_agent.py`の`_command()`を
   参考に、`config["cli"]`に応じてcodex(既存の`-m`/`-c model_reasoning_effort`
   コマンド、ただし`config["model"]`を直読みするよう修正——現状の決め打ちを解消)と
   claude(`claude -p <prompt> --output-format stream-json --verbose
   --dangerously-skip-permissions --model <model> --max-turns 1000`、
   reasoning_effort関連の引数なし)に分岐する関数を追加する。
2. **claude用の`.claude/settings.json`をworkdirに書き込む。** `run_v040_agent.py`の
   `CLAUDE_SETTINGS`(`//workspaces/**`等への読み取り拒否)をそのまま流用——
   v0.4.4系のworkdirは`$HOME/erl-v044-runs/...`で実リポジトリ外にあるため、
   この拒否リストは安全にそのまま使える。
3. **`_environment()`・スコアリングツール配布・盲検監査はCLI非依存のためそのまま。**
   `V044_TRUTH_ROOT`/`V044_KEY_FILE`注入・`score_confirmation.py`コピー・
   `agent_packet.json`の`confirmation_scorer_command`有無判定は、いずれもCLIの
   種類を参照していないため無改修で動く。
4. `v044_full_feature_pilot.py`に新しいconfig辞書を追加(sol・opus 両方):
   - `V046_LOW_NOFB_CONFIGS`(セルI/J、sol新規4 seed×2アーム + opus新規1 seed×2アーム、
     `column_limit=None`)
   - `V046_LOW_FB_CONFIGS`(セルK/L、`F4-low-P1`/`F4-low-P3`の既存seedと重複しない
     sol新規3 seed×2アーム + opus新規1 seed×2アーム)
   run_id命名は既存の`agent-01-s*`(P1)/`agent-02-s*`(P3)の慣習を踏襲し、
   opusには`agent-03-s*`(P1)/`agent-04-s*`(P3)を割り当てて衝突を避ける。
5. `build_v044_suite.py`/`run_v044_batch.py`/`audit_v044_suite.py`/
   `finalize_v044_suite.py`に`--config-set low-nofb`・`low-fb`を追加
   (v0.4.5の`10col-fb`/`full-nofb`と全く同じパターン)。
6. `build_v044_suite`自体の関数シグネチャ変更は不要——`column_limit=None`
   (デフォルト)・`enable_confirmation_scoring`の真偽を切り替えるだけ。
7. 既存セルK/Lの「既存n=1」を含めた集計は、`finalize_v044_suite.py`実行後、
   `v044-suite-a01`/`b01`の診断JSONから該当run(`F4-low-P1`/`F4-low-P3`)を
   抽出して新規run群と結合する(新規コード不要、既存JSONの読み出しのみ)。
8. `run_v044_agent.py`のCLI分岐追加は単体テストを追加する(`_command()`が
   `cli="codex"`/`cli="claude"`それぞれで正しいコマンド列を返すことを確認する
   同期テスト——実際のCLI呼び出しは行わない)。

## 7. 実行順序(案)

```text
v0.4.6-a  基盤整備:run_v044_agent.pyのCLI一般化(codex/claude分岐、単体テスト追加)+
          config辞書追加(sol・opus)・CLI配線
v0.4.6-b  セルI・J構築(全列×フィードバックなし×low、P1・P3、sol+opus混在)
          → build-only preflight → 盲検監査 → 実行(sol 8run + opus 2run/競技)
v0.4.6-c  セルK・L構築(全列×フィードバックあり×low、P1・P3、sol+opus混在)
          → 同上(sol 6run[既存n=1/競技と合算しn=4に] + opus 2run/競技)
v0.4.6-d  分析:4象限(low/xhigh × no-fb/fb)のAUC比較・adversarial validation
          出現率比較(sol、n=4基準)+ opus screening(n=1、定性確認のみ)。
          問い1〜4への回答をレポート化。
```

## 8. 不変条件

[c_lite_v045_policy.md §7](c_lite_v045_policy.md)までの全不変条件を継続。追加なし
(本ラウンドは新しい機構を導入せず、既存機構をeffort=low断面で再検証するのみ)。

## 9. ユーザーへの確認事項

1. **この設計(セル定義I〜L・サンプルサイズsol n=4/セル/競技・opus n=1/セル/競技・
   既存データ再利用方針)でよいか。**
2. **opusのn=1/セル/競技(計8 run)という規模感でよいか。** opusはsolよりトークン
   コストが高く、過去にquota枯渇でF5全体が検証不能になった経緯があるため、
   あえて統計的検定を狙わないscreening規模に抑えた——増減の希望があれば調整する。
3. **実行してよいか。** 新規36 run(sol 28 + opus 8)。sol側は既存インフラの
   config追加のみで実装コストは小さいが、opus側は`run_v044_agent.py`のCLI一般化
   という新規実装が必要(§6)。いずれもreal API costが発生する。
