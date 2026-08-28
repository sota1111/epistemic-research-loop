# v0.4.0 Track A Generation 1 — Emergence of Discovering Configurations

## 訂正について(この文書は差し替え版)

初版(2026-08-28 前半)は 23/24 run(codex sol の 1 replicate をインフラ障害で除外)を基に、
「codex 系は終端解決を回避する行動傾向がある」と結論していた。**その後、codex 実行に使っていた
`workspace-write` sandbox(bwrap 依存)がこのコンテナで恒久的に壊れており、除外した 1 replicate
だけでなく世代 1 の codex 実行全体に断続的な計算阻害を与えていたことが判明した**(session ログの
フォレンジックで発覚、真値は未参照)。原因を修正(`danger-full-access` サンドボックス + reasoning
effort 明示固定)した上で **codex 8 スロット全て(除外していた 1 件を含む)を再実行し、24/24 で
再確定した。** 本版はその修正後の結果を正本とする。旧版の raw data は
`.runs/v040/agent_outputs_pre_sandboxfix_backup/`(未 commit)に保全済み。詳細は
[Preregistration の post_registration_deviations](../v040_gen1_preregistration.json) を参照。

## 結論

v0.4.0 は v0.3.x までの「Gate 通過」評価様式を離れ、**発見イベントの計数による構成選抜**
(preregistration: [v040_gen1_preregistration.json](../v040_gen1_preregistration.json))を主指標とする。
世代 1(6 構成 × 4 replicate = 24 run、全 24 run 有効)の結果:

- **5 構成が停止規則の閾値(発見イベント >= 2)を通過し、世代 2 へ進む資格を得た:**
  C3(opus-5×P1、7 件)> C2(fable-5×P2、5 件)> **C5(codex sol×P1、4 件)** > C1(fable-5×P1、
  2 件)= **C6(codex terra×P1、2 件)**。非通過は C4(sonnet-5×P2、1 件)のみ。
  **サンドボックス修正前は codex 系(C5=1、C6=0)が最下位だったが、修正後は codex sol が
  claude fable-5×P1 と並ぶかそれを上回る成績を出した。** 「codex は弱い」という初版の解釈は
  誤りだったことになる——少なくとも大部分は環境障害が原因だった。
- **未知構造(structure-grammar generator による machine-composed 構造)の発見が実際に発生した。**
  grammar_composed_a 7/24・grammar_composed_b 12/24。これは方針
  ([c_lite_v040_policy.md](../c_lite_v040_policy.md))が主眼とした「未知の構造の発見に至る
  エージェントの発生」の直接的な観測事例である。
- **懸念すべき退行は残存:persistent ラダーの L1–L3(clear / noisy_proxy / delayed_history)が
  0/24 のまま**(v0.3.9: 7/24・1/24・5/24)。persistent_compositional のみ 2/24。**この退行は
  claude 側(C1–C4)でのみ発生しており codex とは無関係**——sandbox 修正後も codex 側の persistent
  ラダー発見は 0 件で、退行の原因は別にある(下記)。
- **codex sol/terra とも matched-negative 側で新たな false promotion が出現した**(sol 2 件・
  terra 5 件、修正前はいずれも 0 件)。特に terra は `v040-genA-g03` の 1 replicate で 14 pack 中
  11 pack を `validated_actionable_transferred` と過剰に確信しており、単発の暴走的な run である
  可能性が高い(他 3 replicate は逆に保守的)。

## 実行記録

- 6 構成 × 4 replicate = 24 run を preregistration。当初 g04/agent-03-s17(C5、codex sol)を
  「コンテナの非特権 user namespace 遮断により codex の workspace-write sandbox が書き込み
  不能」として開封前に除外し、23 run で一度確定・開封・文書化した。
- **ユーザーからの指摘(「平等な評価ができるように」)を受け、除外の根本原因(bwrap)を
  session ログでフォレンジック調査した結果、この障害は除外した 1 run に限らず、世代 1 の
  codex 8 スロット全てで断続的に発生していたことが判明した。** 最終採用(Lock 済み)attempt の
  コマンド成功率:2 スロットは軽微(bwrap 失敗率 2–5%、数百コマンド完走)、**4 スロットは重度**
  (失敗率 38–45%、最終 attempt のコマンド数がわずか 8–17 件——14 pack 分のフル解析には
  明らかに不足)。terra の transcript には「sandbox がブロックされたため `artifact_complete`/
  `oof_honesty_passed` の 2 フィールドだけを書き換えた」という記述もあった。
- 原因:codex の `-s workspace-write` は bwrap(Linux user namespace)に依存するが、この
  コンテナは user namespace 作成を恒久的に禁止している(`unshare` が root でも EPERM)。
  修正として `-s danger-full-access`(OS サンドボックスを経由しない実行モード)に切り替え、
  isolated smoke test で bwrap エラーが解消することを確認した。あわせて、共有
  `~/.codex/config.toml` の reasoning effort 既定値が世代 1 実行中に xhigh→low へ無断で
  変化していた別件(g03/agent-03-s42、C6)も、`-c model_reasoning_effort` を毎回明示指定する
  形で恒久修正した。
- 旧 8 submission・run_meta・transcript を `.runs/v040/agent_outputs_pre_sandboxfix_backup/`
  へ保全した上でクリアし、除外していた g04/agent-03-s17 を含む codex 8 スロット全てを
  修正済み runner で再実行。**全 8 スロットとも最終 attempt で bwrap 失敗 0 件、14 pack /
  42 context / 5 replicate 以上の完全な submission を得た。** 24/24 で盲検監査(view 24・
  transcript 48、findings 0)→ Lock → 再開封。評価コードは無変更(v0.3.7 系列 verbatim)。

## 構成別選抜表(P1 前段指標:発見イベント数、修正後・確定版)

| 構成 | CLI / モデル | Prompt | Replicate | 発見イベント | 発見 family | False promotion |
| --- | --- | --- | ---: | ---: | --- | ---: |
| **C3** | claude / opus-5(baseline) | p1 | 4 | **7** | grammar_a, grammar_b, persistent_compositional | 0 |
| **C2** | claude / fable-5 | p2 | 4 | **5** | grammar_a, grammar_b, persistent_compositional | 0 |
| **C5** | codex / gpt-5.6-sol | p1 | 4 | **4** | grammar_a, grammar_b | 2 |
| **C1** | claude / fable-5 | p1 | 4 | **2** | grammar_a, grammar_b | 0 |
| **C6** | codex / gpt-5.6-terra | p1 | 4 | **2** | grammar_a, grammar_b | 5 |
| C4 | claude / sonnet-5 | p2 | 4 | 1 | grammar_b | 0 |

**世代 2 選抜候補(方針§3.2「上位 2–3 構成」):C3・C2・C5。** 修正前の想定(C3・C2・C1、全て
claude)から変わり、**codex sol が上位 3 に入る。** false promotion を tie-break に含めると
C1(0 件)を優先する余地もあるため、最終的な世代 2 構成は次段階で確定する。

読み取れる構造(修正後):

1. **Model 選択が依然として第一次要因だが、"claude が codex より強い" は一般化できない。**
   opus-5(C3=7)が最上位である点は変わらないが、**codex sol(C5=4)は claude fable-5×P1(C1=2)
   を上回った。** 修正前の解釈(「codex 系は終端解決を回避する」)は環境障害の影響を強く受けており、
   純粋な model capability の比較としては無効だった。
2. **false promotion は codex 側でのみ新規に発生。** claude 4 構成は全て 0 件のままだが、
   sol(2 件)・terra(5 件)は matched-negative 側で過剰確信を示した。terra の 5 件は
   `v040-genA-g03` の 1 replicate に集中しており(14 pack 中 11 pack を validated と判定)、
   他 3 replicate は保守的(useful_encoding_unvalidated・inconclusive 中心)。**単発の暴走的な
   run である可能性が高く、terra の一般的傾向と断定するには replicate 数が不足している。**
3. **persistent ラダー L1–L3 の 0/24 は codex とは無関係の現象。** sandbox 修正後も codex は
   persistent family を 1 件も発見しておらず、claude 側の C1–C3 と同じ壁に当たっている。これは
   環境障害ではなく、下記「退行の分析」で扱う契約/Suite 側の論点である。

## 未知構造の発見(structure-grammar generator)

`grammar_composed_a`/`grammar_composed_b` は §5 の structure-grammar generator が
motif(persistent effect・delayed history・regime flip・cross-key link・path decay・routed
signal)から 2–3 個を機械合成し、識別可能性 preflight を通過したインスタンスのみを Suite 化した
もので、**設計者もインスタンスの具体的な組成を事前に知らない**。この family での発見(7/24・
12/24)は、既知の v0.3.x persistent ラダーへの過学習ではなく、未知の構造クラスへの汎化が実際に
起きたことを示す一次データである。**claude・codex 双方の上位構成(C3・C2・C5)がこの family で
発見しており、CLI に依存しない現象であることが sandbox 修正後のデータで確認できた。** 世代 2 は
この family を含む新規 Suite インスタンス(新 master seed、選抜に使った Suite は再利用しない)で
再現確認を行う。

## 退行の分析:persistent L1–L3 が 0/24(claude・codex 共通)

| Family | v0.3.9(24 run中) | v0.4.0 世代 1(24 run中、修正後) | 主な失敗経路 |
| --- | ---: | ---: | --- |
| persistent_clear | 7 | **0** | evidence/promotion 段階の失敗が中心 |
| persistent_noisy_proxy | 1 | **0** | 同上 |
| persistent_delayed_history | 5 | **0** | 同上 |
| persistent_compositional | 3 | 2 | 同上(claude C2・C3 のみ発見) |

failure_stage の内訳(24 run 全体)は evidence 96 件・promotion 33 件・matched_negative 5 件。
**sandbox 修正は persistent ラダーの退行に影響しなかった**(claude 側は元々サンドボックス問題と
無関係、codex 側も修正後なお 0 件)——これは v0.4.0 が新規追加した implication provenance 契約
(held-out 統計の自己 null 分布内位置が validated には 2 Context 以上で 0.95 以上)が全 CLI 共通の
ボトルネックになっている可能性を強めて示唆する。候補説明(transcript 差分分析で検証可能、未検証):

1. **契約レバー(implication provenance)の厳格さそのもの。** 0.95 という位置閾値は v0.3.9 の
   0.05(強度の絶対値)よりはるかに厳しい統計的要求であり、真の構造がある場合でも到達しにくい
   可能性がある。CLI に依存せず全構成で同じ壁に当たっている事実は、この仮説を補強する。
2. **Suite 内の注意配分の変化。** grammar-composed 2 種の新規追加により、既知ラダー位置への
   cycle 配分が相対的に減った可能性。
3. **この世代の master seed(20260910)固有のインスタンス難度。**

**方針上の含意:** v0.4.0 は契約レバーを凍結し構成探索(能力レバー)へ移行する方針だったが、
今回追加した implication provenance 自体が新しい契約レバーとして機能してしまっている可能性が
高まった(CLI 非依存の現象であるため)。世代 2 では方針§3.3 の「上位構成の transcript 差分分析」で
この経路を優先的に切り分けることを推奨する(構造語彙を足さない範囲での診断)。

## 二次予測:モデル系統間の Shared Blind-spot Rate(診断、修正後)

| Suite × Seed | Union TSDR | Union TSRR | SBR | LOAO TSRR |
| --- | ---: | ---: | ---: | ---: |
| g01 × s17 | 0.571 | 0.857 | 0.429 | 0.571 |
| g01 × s42 | 0.143 | 1.000 | 0.857 | 0.286 |
| g02 × s17 | 0.286 | 0.857 | 0.714 | 0.714 |
| g02 × s42 | 0.286 | 1.000 | 0.714 | 0.429 |
| g03 × s17 | 0.429 | 1.000 | 0.571 | 0.857 |
| g03 × s42 | 0.429 | 1.000 | 0.571 | 0.857 |
| g04 × s17(C5 復元済み、3 agent) | 0.429 | 1.000 | 0.571 | 0.714 |
| g04 × s42 | 0.429 | 1.000 | 0.571 | 1.000 |

SBR は 0.429–0.857 で v0.3.9 の 0.5625 と同程度〜悪化しており、「異基盤混成で盲点重なりが下がる」
という二次予測は世代 1 単独では確認できない。persistent ラダー自体がほぼ全構成で未発見
(0/24 x3 family)であるため、`shared_blind_spot_rate` の分母(未発見の一致)が構造的に高止まり
している影響が大きく、退行の分析が先に解消されない限り二次予測の検定力は低い。

## 判定

- **P1 前段(選抜)基準は機能した:** 発見イベント数で構成間に明確な分離(1〜7 件)が生じ、
  5 構成が世代 2 進出の閾値を通過。停止規則 1 は不発動。
- **未知構造発見という主眼は達成、かつ CLI 非依存であることが確認できた:** structure-grammar
  family での発見は claude・codex 双方の上位構成で再現しており、モデル多様化(方針の目標モデル
  更新の核)の妥当性を支持する一次データになった。
- **codex の当初の「弱さ」は主として環境障害だった。** サンドボックス修正により codex sol は
  世代 2 進出候補に入り、terra も閾値を通過した。ただし terra の false promotion 5 件(1
  replicate に集中)は次段階で要観察。
- **持続構造ラダー L1–L3 の全滅は CLI 非依存の未解決問題であり、次の優先度はここにある。**
- **次の作業:** 世代 2([policy §3.2](../c_lite_v040_policy.md))を C3・C2・C5(または tie-break
  次第で C1)について新規 Suite インスタンス(新 master seed、6–8 run/構成)で実行し、
  (a) persistent L1–L3 退行の transcript 差分診断(CLI 非依存と判明したため優先度が上がった)、
  (b) implication provenance 契約の厳格さの影響切り分け、(c) codex sol の reasoning-effort
  ablation(別途 side-probe として計画中)を進める。

## 正本

- [Preregistration](../v040_gen1_preregistration.json)(除外・修正の事前/事後登録記録を含む)
- [Selection Table](../v040_gen1_selection.json) / [Diagnostics](../v040_gen1_diagnostics.json)
- [v0.4.0 方針](../c_lite_v040_policy.md)
