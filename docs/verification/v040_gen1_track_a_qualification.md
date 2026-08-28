# v0.4.0 Track A Generation 1 — Emergence of Discovering Configurations

## 結論

v0.4.0 は v0.3.x までの「Gate 通過」評価様式を離れ、**発見イベントの計数による構成選抜**
(preregistration: [v040_gen1_preregistration.json](../v040_gen1_preregistration.json))を主指標とする。
世代 1(6 構成 × 4 replicate、うち 1 replicate をインフラ障害により事前登録した上で除外、
実行 23 run)の結果:

- **3 構成が停止規則の閾値(発見イベント >= 2)を通過し、世代 2 へ進む資格を得た:**
  C3(opus-5×P1、7 件)> C2(fable-5×P2、5 件)> C1(fable-5×P1、2 件)。
  C4(sonnet-5×P2、1 件)・C5(codex sol×P1、1 件)・C6(codex terra×P1、0 件)は非通過。
- **未知構造(structure-grammar generator による machine-composed 構造)の発見が実際に発生した。**
  grammar_composed_a 5/23・grammar_composed_b 9/23(構造 family・語彙とも設計者が個別インスタンスを
  事前に知らない生成系)。これは方針([c_lite_v040_policy.md](../c_lite_v040_policy.md))が主眼と
  した「未知の構造の発見に至るエージェントの発生」の直接的な観測事例である。
- **懸念すべき退行:persistent ラダーの L1–L3(clear / noisy_proxy / delayed_history)が
  0/23 に沈んだ**(v0.3.9: 7/24・1/24・5/24)。persistent_compositional のみ 2/23 で v0.3.9 の
  3/24 相当を維持。原因は単一ではなく、下記「退行の分析」を参照。
- **事前登録した主予測は的中しなかった:** 「少なくとも 1 構成が baseline(C3)から発見イベント数で
  分離する」という予測に対し、実際には baseline 自身が最上位だった。予測が意図した「離陸」方向
  ではなく、"model choice がまず効く" という別の教訓を与えた(下記)。
- **codex 系の行動差は世代 1 でも継続:** terra は 4 replicate 全 24 pack が非終端(発見 0 件、
  matched_negative 段階の失敗も 1 件のみ = ほぼ全て inconclusive/useful_encoding_unvalidated)。
  sol は 3 replicate(18 pack)中 1 件のみ発見。Claude 系(C1–C4)はいずれも codex 系を上回る。

## 実行記録

- 6 構成 × 4 replicate = 24 run を preregistration。うち **g04/agent-03-s17(C5、codex sol)は
  コンテナの非特権 user namespace 遮断(`unshare` が root でも EPERM)により codex の
  workspace-write sandbox が shell 経路・file-edit 経路とも決定的に書き込み不能と判明**(独立
  smoke test で再現)。2026-08-26 の同一構成の run は 381/388 command 成功しており、環境側の
  regression と判断。**開封前に**この除外を preregistration の deviation エントリとして記録し
  (`post_registration_deviations`)、パイプライン側(suite 定数・lock・finalize・評価器の
  `excluded_pairs` 引数)を対応させた上で 23 run で確定した。C5 は 3 replicate でも P1 の
  「2 独立 run 以上での再現」要件は充足する。
- 盲検監査:view 24・transcript 54 とも実 findings 0。codex transcript に repository パスの言及が
  2 件(5 箇所)あったが、いずれも `which python3` / `ls -l` が agent の python3 実行系(venv 経由の
  symlink)を示しただけで、src・prompt・view・truth への接触は伴わない。v0.3.8 の numpy 警告と
  同じ interpreter-level の既知制約として allow-list を `.venv/` 全体へ拡張した(実 repository
  path 言及は引き続き Fail する設計を保持)。
- 24 run 中 23 run が Lock → SHA 再照合 → 開封。評価器は v0.3.7 系列を verbatim 再利用しつつ、
  preregistered 除外を扱うため `evaluate_v037_runs`/`evaluate_v038_runs` に後方互換な
  `excluded_pairs` 引数を追加した(デフォルト空集合、v0.3.7/8/9 の呼び出しは無変更)。

## 構成別選抜表(P1 前段指標:発見イベント数)

| 構成 | CLI / モデル | Prompt | Replicate | 発見イベント | 発見 family | False promotion |
| --- | --- | --- | ---: | ---: | --- | ---: |
| **C3** | claude / opus-5(baseline) | p1 | 4 | **7** | grammar_a, grammar_b, persistent_compositional | 0 |
| **C2** | claude / fable-5 | p2 | 4 | **5** | grammar_a, grammar_b, persistent_compositional | 0 |
| **C1** | claude / fable-5 | p1 | 4 | **2** | grammar_a, grammar_b | 0 |
| C4 | claude / sonnet-5 | p2 | 4 | 1 | grammar_b | 0 |
| C5 | codex / gpt-5.6-sol | p1 | 3(除外 1) | 1 | grammar_b | 0 |
| C6 | codex / gpt-5.6-terra | p1 | 4 | 0 | — | 0 |

**世代 2 選抜(方針§3.2「上位 2–3 構成」):C3・C2・C1。** いずれも claude CLI。False promotion は
全構成で 0(FSPR 面の安全性は維持)。

読み取れる構造:

1. **Model 選択が第一次要因。** 同一 Prompt(p1)・同一 CLI 条件下で opus-5(C3=7)は fable-5
   (C1=2)の 3.5 倍の発見イベントを出した。
2. **Prompt-arm の効果は fable-5 の対で確認できる。** 同一モデル(fable-5)で p2(C2=5)は
   p1(C1=2)の 2.5 倍。P2 が要求する「4 仮定軸での競合仮説の事前列挙」がこのモデルには効いている。
   ただし sonnet-5×p2(C4=1)は同じ p2 でも低く、prompt 単独の効果ではなくモデルとの交互作用である。
3. **codex 系は依然として終端解決そのものを避ける傾向が強い。** sol/terra は「証拠不足で
   inconclusive」ではなく、構造的に resolution を確定させない振る舞いが観測される(下記参照)。

## 未知構造の発見(structure-grammar generator)

`grammar_composed_a`/`grammar_composed_b` は §5 の structure-grammar generator が
motif(persistent effect・delayed history・regime flip・cross-key link・path decay・routed
signal)から 2–3 個を機械合成し、識別可能性 preflight を通過したインスタンスのみを Suite 化した
もので、**設計者もインスタンスの具体的な組成を事前に知らない**。この family での発見(5/23・9/23、
matched-negative 側の false promotion 0)は、既知の v0.3.x persistent ラダーへの過学習ではなく、
未知の構造クラスへの汎化が実際に起きたことを示す一次データである。世代 2 はこの family を含む
新規 Suite インスタンス(新 master seed、選抜に使った Suite は再利用しない)で再現確認を行う。

## 退行の分析:persistent L1–L3 が 0/23

| Family | v0.3.9(24 run中) | v0.4.0 世代 1(23 run中) | 主な失敗経路 |
| --- | ---: | ---: | --- |
| persistent_clear | 7 | **0** | falsified 申告 11/23、promotion 段階失敗 5 |
| persistent_noisy_proxy | 1 | **0** | falsified 申告 14/23(61%)、promotion 段階失敗 4 |
| persistent_delayed_history | 5 | **0** | falsified 申告 8/23、inconclusive 8/23 |
| persistent_compositional | 3 | 2 | falsified 申告 7/23、promotion 段階失敗 5 |

failure_stage の内訳は evidence 86 件・promotion 41 件・matched_negative 1 件・implementation 7 件
(v0.3.9: evidence 88・promotion 16・matched_negative 5)。**promotion 段階の失敗が 16→41 に急増**
しており、これは v0.4.0 が新規追加した implication provenance 契約(held-out 統計の自己 null 分布内
位置が validated には 2 Context 以上で 0.95 以上、falsified には 1 Context 以下)が新しいボトル
ネックになっている可能性を示す。ただし persistent_clear/noisy_proxy の主要因は **falsified 申告
そのものの急増**(48%・61%)であり、契約の厳格化だけでは説明しきれない。候補説明(いずれも
transcript 差分分析で検証可能、未検証):

1. **Suite 内の注意配分の変化。** 世代 1 の 14 pack には grammar-composed 2 種が新規に加わり、
   Prompt(P1/P2)も implication provenance の記述を追加した。既知ラダー位置への cycle 配分が
   相対的に減った可能性。
2. **契約レバー(implication provenance)の厳格さそのもの。** 0.95 という位置閾値は v0.3.9 の
   0.05(強度の絶対値)よりはるかに厳しい統計的要求であり、真の構造がある場合でも到達しにくい
   可能性がある。
3. **この世代の master seed(20260910)固有のインスタンス難度。** 4 Suite すべてで同じ退行方向
   なので疑わしいが、単一 seed では切り分けられない。

**方針上の含意:** v0.4.0 は契約レバーを凍結し構成探索(能力レバー)へ移行する方針だったが、
今回追加した implication provenance 自体が新しい契約レバーとして機能してしまっている可能性がある。
世代 2 では方針§3.3 の「上位構成の transcript 差分分析」でこの経路を優先的に切り分けることを
推奨する(構造語彙を足さない範囲での診断)。

## 二次予測:モデル系統間の Shared Blind-spot Rate(診断)

| Suite × Seed | Union TSDR | Union TSRR | SBR | LOAO TSRR |
| --- | ---: | ---: | ---: | ---: |
| g01 × s17(fable P1, opus P1, sol P1) | 0.571 | 0.857 | 0.429 | 0.571 |
| g01 × s42(fable P2, sonnet P2, terra P1) | 0.143 | 1.000 | 0.857 | 0.286 |
| g02 × s17 | 0.286 | 0.857 | 0.714 | 0.857 |
| g02 × s42 | 0.286 | 1.000 | 0.714 | 0.429 |
| g03 × s17 | 0.429 | 1.000 | 0.571 | 0.857 |
| g03 × s42 | 0.286 | 1.000 | 0.714 | 0.857 |
| g04 × s17(C5 除外、2 agent のみ) | 0.286 | 1.000 | 0.714 | 0.286 |
| g04 × s42 | 0.429 | 1.000 | 0.571 | 0.429 |

SBR は 0.429–0.857 で v0.3.9 の 0.5625 と同程度〜悪化しており、「異基盤混成で盲点重なりが下がる」
という二次予測は世代 1 単独では確認できない。これは persistent ラダー自体がほぼ全構成で未発見
(0/23 x3 family)であるため、`shared_blind_spot_rate` の分母(未発見の一致)が構造的に高止まり
している影響が大きく、退行の分析が先に解消されない限り二次予測の検定力は低い。

## 判定

- **P1 前段(選抜)基準は機能した:** 発見イベント数で構成間に明確な分離(0〜7 件)が生じ、
  3 構成が世代 2 進出の閾値を通過。停止規則 1(世代 2 終了時に persistent 系再現構成が皆無なら
  合成探索打ち切り)は不発動。
- **未知構造発見という主眼は部分的に達成:** structure-grammar family での発見は本物の一次データ。
  ただし持続構造ラダー L1–L3 の全滅は新しい未解決問題であり、次の優先度はここにある。
- **次の作業:** 世代 2([policy §3.2](../c_lite_v040_policy.md))を C1・C2・C3 について新規
  Suite インスタンス(新 master seed、6–8 run/構成)で実行し、(a) persistent L1–L3 退行の
  transcript 差分診断、(b) implication provenance 契約の厳格さの影響切り分けを優先する。

## 正本

- [Preregistration](../v040_gen1_preregistration.json)(除外の事前登録記録を含む)
- [Selection Table](../v040_gen1_selection.json) / [Diagnostics](../v040_gen1_diagnostics.json)
- [v0.4.0 方針](../c_lite_v040_policy.md)
