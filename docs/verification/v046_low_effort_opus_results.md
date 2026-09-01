# v0.4.6 結果 — reasoning effort=low 断面 + 少数opus screening

**目的:** [c_lite_v046_policy.md](../c_lite_v046_policy.md)で計画した、全列固定・
reasoning effort=low・フィードバック{None,Iterative}×アーム{P1,P3}の2×2に、少数の
opus(claude-opus-5)screening(各セルn=1/競技)を重ねたラウンド。新規36 run
(sol 28 + opus 8)、両コンペ(IEEE-CIS・Santander)、全run成功・0件失敗。

## 0. 実行ノート:盲検監査の誤検出を発見・修正

post-hoc監査で、opus 3run(IEEE-CIS `agent-04-s3002`、Santander `agent-03-s3002`・
`agent-04-s3002`、いずれもfeedbackありセル)が `.controller_truth`・`labels.enc` を
検出した。transcriptのtool_use_idを遡って調査した結果、**全ての検出が同一の原因**——
opusエージェントがオリエンテーションとして `cat agent_packet.json && cat RUNNER.md &&
cat score_confirmation.py` を実行し、**自分のworkdir内にある採点ツール自身のソース
コード**(docstringに ".controller_truth/v044/" という説明文、コード内に
"_confirmation_labels.enc" という文字列リテラルを含む)が読み込まれ、それがそのまま
transcriptに反映されていたことによる誤検出と判明した。実際の env var 解決値・
ディレクトリ一覧・復号ラベル等が現れた形跡は一切ない。

`audit_v044_suite.py` に `_strip_known_scorer_source()` を追加し、採点ツール自身の
既知テキストを事前に除去してからトークン走査するよう修正(実際のリーク——解決済み
env var値やディレクトリ一覧など——には引き続き反応する)。修正後、4 suite全てクリーン。
詳細はコミット `2964a00` を参照。

## 1. 応答変数1(連続値):transfer AUC — 35/36が自前baselineを超えた

| suite | 条件 | baseline | run数 | 超過数 |
| --- | --- | --- | --- | --- |
| a06 (IEEE-CIS) | low + no-fb | 0.8686 | 10 | 10/10 |
| a07 (IEEE-CIS) | low + fb | 0.8347 | 8 | 7/8(*) |
| b06 (Santander) | low + no-fb | 0.8183 | 10 | 10/10 |
| b07 (Santander) | low + fb | 0.7767 | 8 | 8/8 |

(*) `a07/agent-02-s2592`(sol、P3)のみ僅かに未達(AUC 0.8325 vs baseline 0.8347、
0.0022差)。他は全て超過。

**問い1(低effort+feedbackはxhighに迫れるか)への回答——コンペで結果が割れた:**

自前baseline上乗せ幅(agent平均AUC − そのsuiteのbaseline)を、[v0.4.5](v045_factorial_design_results.md)で
算出済みのxhigh断面と比較する(sol限定、opus除く):

| コンペ | 条件 | P1上乗せ | P3上乗せ |
| --- | --- | --- | --- |
| IEEE-CIS | low + no-fb (a06) | +1.6pt | +1.6pt |
| IEEE-CIS | low + fb (a07) | **+3.9pt** | +1.3pt |
| IEEE-CIS | xhigh + no-fb (v0.4.5 E/F) | +1.0pt | +1.1pt |
| IEEE-CIS | xhigh + fb (v0.4.4-b G/H, xhigh分) | +1.8pt | +2.8pt |
| Santander | low + no-fb (b06) | +3.7pt | +3.9pt |
| Santander | low + fb (b07) | +4.9pt | +6.4pt |
| Santander | xhigh + no-fb (v0.4.5 E/F) | +6.6pt | +6.6pt |
| Santander | xhigh + fb (v0.4.4-b G/H, xhigh分) | +5.8pt | +6.2pt |

**IEEE-CISでは、低effortの上乗せ幅がxhighと同等かそれを上回った**(特にlow+fb+P1が
+3.9ptと、xhigh+fb+P1の+1.8ptを上回る)——低コストなeffortでも、feedbackループさえ
あれば十分な性能改善が得られることを示唆する。**Santanderでは逆に、低effortの上乗せ幅は
xhighより一貫して小さい**(全条件でxhigh側が上回る)——Santanderの実際の信号
(下記§3のクラス条件付き分散効果)は、より深い体系的な特徴探索(高effort)から
恩恵を受けやすい構造である可能性が高い。**「effortを下げても性能が保てるか」は
IEEE-CISとSantanderで答えが逆転する**——[v0.4.5](v045_factorial_design_results.md)で
確認した「列数とfeedbackのどちらが効くかはコンペ依存」という知見と同じ形の非対称性が、
effort軸でも観測された。

(n=3〜4/セルの単一ラウンドであり、この非対称性自体の確度は追加ラウンドなしには
高くない——[v0.4.3-fの教訓](../c_lite_v043_policy.md)通り、方向性の記録に留める。)

## 2. 応答変数2(二値):adversarial validationの出現 — P3の「必要条件」性が初めて崩れた

**最重要の更新:** これまで本プロジェクト全体(v0.4.3-f・v0.4.4-b・v0.4.5、150 run超)を
通じて、adversarial validationはP3アームのrunにのみ出現し、P1アームでの出現は
**一度もなかった**。本ラウンドで**初めて、P1アームのrunが2件、独立にadversarial
validationを実施した**:

- `a06/agent-01-s2001`(sol、IEEE-CIS、P1、no-feedback):「Adversarial validation
  found no meaningful multivariate research/transfer separation.」
- `a07/agent-03-s3002`(opus、IEEE-CIS、P1、feedback):「Adversarial validation gave
  AUC 0.50 for research-vs-confirmation and 0.50 for research-vs-transfer, so the
  splits are IID and CV is an unbiased guide.」

両方とも実文を確認済み——本物のresearch/confirmation/transfer分布シフト検定であり、
[v0.4.5](v045_factorial_design_results.md#1-応答変数1二値adversarial-validation-の出現有無--最も明確な結果)で
注意喚起した「context プーリング」等の誤検出パターンではない。**いずれも、明示的な
「自分の最良解を攻撃せよ」という指示なしに、通常のEDA手順の一環として実施されていた**
——P3プロンプトの自己批判指示への直接的な反応ではなく、探索を広く行うP1プロンプトの
指示(「Explore it broadly」)の範囲内で、十分に周到なエージェントが自発的に行った
ように見える。

新規36 runでの出現率をアーム別に集計すると:

| アーム | 出現/対象 | 出現率 |
| --- | --- | --- |
| P1 | 2/18 | 11% |
| P3 | 6/18 | 33% |

**P3は依然としてより強く出現と結び付いている(約3倍の出現率)が、もはや「絶対的な
必要条件」とは言えなくなった。** 解釈の候補:reasoning effortを下げた・feedbackを
加えた等、本ラウンドで初めて導入した条件がP1でも周到な探索を後押しした可能性、
あるいは単に本ラウンドのP1エージェント(特にopus)がたまたま念入りだった可能性——
n=2という小さいサンプルでは切り分けられない。**この発見単体では確定させず、次ラウンドで
P1アームのみを対象にした追加確認(n=4以上)を優先課題とする。**

## 3. 発見:opusが独立に到達した、本プロジェクト最深の構造発見(4/4のIEEE-CIS opus runが収束)

**IEEE-CIS opusの4 run全て**(`a06/agent-03-s3001`・`a06/agent-04-s3001`・
`a07/agent-03-s3002`・`a07/agent-04-s3002`、P1/P3・feedback有無を問わず)が、
**匿名化された数値列から独立に、実データの意味論的構造(count/amount ペア・
compositional比率・nested window階層)を再構築した**——sol runではこの水準の
再構築は本プロジェクト通じて一度も観測されていない。代表的な記述(`a07/agent-04-s3002`):

> The continuous columns are MONETARY AMOUNTS and the integer columns are COUNTS,
> and they come in exact (sum, count) pairs. For 28 pairs [...] the zero patterns
> agree on 100.0% of all 8000 rows [...] I therefore built explicit average-ticket
> features amount/count, which trees cannot construct themselves.

4 run中3 runが同種の(sum,count)ペア構造・compositional比率構造を独立に発見し
(`a06/agent-03-s3001`は log-ratio による同型の発見)、AUC上の実質的な寄与
(+0.01〜0.03程度)も確認している。

**さらに重要:`a07/agent-04-s3002` は、IEEE-CIS 1st place解法の技術クラス#1
(エンティティ/UID復元)に本プロジェクトで初めて到達した。**
[technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md)の
技術クラス#1〜#4(UID復元・時間集約・時間差・カテゴリターゲットエンコーディング)は、
v0.4.0以降の全ラウンド(150 run超)を通じて一度も到達されていなかった——匿名化された
数値列だけでは再現困難と想定されていた。本runは高cardinality列 `x_102` を
「反復するエンティティID」(2102種、最大134行/グループ)と正しく同定し、
**StratifiedGroupKFold(x_102でグループ化したCV)を実施してエンティティレベルの
記憶効果を約0.008 AUCと定量化し、かつ「confirmation・transferともに同程度のx_102
重複率(78.5%・81.5%)を持つため、この効果はtransfer推定を歪めない」という正しい
因果的判断まで下している**——UID復元という技術クラスへの到達に加え、その効果の
評価バイアスへの影響までを正確に切り分けた、taxonomy上も方法論上も本プロジェクト
最高水準の到達点。`a06/agent-04-s3001` も同じ列 `x_102` を独立に調査し、
StratifiedGroupKFoldで似た低下(0.856→0.845)を観測した上で「(この配置では
group-disjointではないため)通常CVの方が正しい」と結論しており、同種の分析が
2 runで再現している。

**Santander opusの4 run全て**も同様に収束したが、対象は既知の層1技術クラス#2
(特徴独立性モデリング)の**より精密な特殊化**である:4 runとも「200特徴はほぼ完全に
独立(相関はnull水準)」から出発し、単純な加法的線形効果だけでなく、**クラス条件付き
分散(variance)/isotropicな二次(quadratic)効果**——「陽性クラスでは多くの特徴の
分散がわずかに拡大する」という、指数傾斜(exponential-tilt)/対角QDA生成モデルに
相当する機構——を4 run独立に定量化した(代表:`b06/agent-04-s3001`「An ISOTROPIC
QUADRATIC / 'extremeness' component [...] ONE shared isotropic term beats 200 free
per-feature quadratic coefficients (0.877 vs 0.865)」)。既存の層1#2の記述
(「特徴ごとに寄与を計算し合成する」)よりも一段階精緻化された機構的説明であり、
今後のtaxonomy更新候補として記録する。

**ただし、Santanderの本当の核心技術(#1 real/synthetic行判定・#3 頻度エンコーディング)
には、opus 4 runを含め今回も一度も到達しなかった**——[v0.4.4-b](v044_cross_competition_synthesis.md)で
確立したn=22の決定的否定結果が、今回のopus screening(n=4追加、モデルという別次元での
検証)によってn=26に拡張されても揺るがなかった。**列数・population・effort・
エージェントモデルのいずれを変えても到達しない、という4つの独立したレバーでの否定は、
このコンペの「頻度エンコーディング」という着眼点そのものが、これらのモデル群にとって
根本的に想起しにくい仮説空間の外側にあることを強く示唆する。**

## 4. late submissionでの上位到達可能性についての考察(分析のみ、実提出はしない)

ユーザーの指示通り、**これは考察であり、実際のKaggle提出は行っていない**——本
プロジェクトはこれまで一貫して「疑似採点による代替」を採用しており、この方針を
変更していない。

**IEEE-CIS:** 本リポジトリには、過去の別ラインの実験(`docs/verification/ieee_cis_arm_comparison.md`、
本セッションの盲検agent研究とは異なる、実データ・非匿名化での過去のsubmission比較)に
実際のpublic leaderboardスコアの記録がある——untunedなepistemic-armベースラインが
0.934969、20ラウンドチューニング済みのexploiter-armが0.938967。**これはIEEE-CISの
1st placeスコアではなく、本プロジェクトの過去の非匿名化runが実際に達成したpublic LB
参考値**であり、1st placeの正確な数値はリポジトリ内に記録がない。

本ラウンドの最良transfer AUC(`a06/agent-04-s3001`、opus、P3、no-feedback、0.8987)は、
この参考値(0.935前後)を**0.03〜0.05ポイント下回る**。ただし比較には
重大な留保が必要:(1) 参考値は実際のKaggle test.csv(時系列分割・非匿名化列)に
対するもので、本ラウンドのtransfer AUCは同一train.csvから無作為抽出した1500行の
sealed holdoutに対するもの——母集団も分割方式(時系列 vs iid)も異なる。(2) 参考値の
runは列名・識別子が非匿名化されており、技術クラス#1〜#4(UID復元・時間集約等)に
直接アクセスできた可能性が高い。(3) 本ラウンドでは技術クラス#1(UID復元相当)に
初めて到達した(§3)ものの、時間集約(#2)・時間差(#3)・カテゴリターゲット
エンコーディング(#4)には依然未到達。

**総合すると:** 「上位」(1st place水準)には技術クラス#1〜#4のうち複数が組み合わさって
初めて到達しうると1st place解説は示唆しており、本ラウンドは#1に単発で到達したのみ
——**実際のリーダーボードで上位を狙える水準にはまだ届いていないと考えるのが妥当**だが、
untunedな参考ベースライン(0.935)には手が届く距離まで来ている、というのが最も
正直な評価。

**Santander:** リポジトリ内に実際のleaderboardベンチマーク数値の記録は**見つからなかった**
(`docs/controller_reference/santander_technique_taxonomy.md`は技術クラスの説明のみで
具体的なスコアは記載していない)——数値を創作せず、この点は明示的に「不明」として扱う。
定性的には、Santanderの1st place解法の核心(頻度エンコーディング・real/synthetic行判定)
は本プロジェクト全体(n=26、列数・population・effort・モデルの4レバー全てで否定)で
一度も到達しておらず、**現在のtransfer AUC(opusで最大0.8891、b06)は「特徴独立性を
前提とした加法的/分散効果モデリング」という技術クラス#2相当の到達点で頭打ちになっている
可能性が高い**——1st place解法が組み合わせる5クラスのうち1クラスのみへの到達であり、
Santanderについては「上位に近づいている」というより「土台となる構造は掴んでいるが、
このコンペ固有の核心的着眼点には依然届いていない」と評価するのがより正確である。

## 5. 限界

- opusは各セルn=1/競技——本ラウンドの「opusが到達した」という発見(§3)は、単一
  replicateの観測としては異例に一貫している(IEEE-CIS 4/4・Santander 4/4が同種の
  構造に収束)ものの、正式な統計的検定ではない。[v0.4.3-fの教訓](../c_lite_v043_policy.md)
  に従い、次ラウンドでの追加opus replicateによる確認を推奨する。
- P1アームでのadversarial validation出現(§2)はn=2の初出であり、確定した知見としては
  扱わない。
- F5(エージェントモデル)は今回sol/opusの2水準のみ。他モデルは未検証。
- 本ラウンドはeffort=lowに固定——mid/highでの同じ2×2は未実施。

## 正本

- [c_lite_v046_policy.md](../c_lite_v046_policy.md)(本ラウンドの事前登録)
- [c_lite_v045_policy.md](../c_lite_v045_policy.md) / [v0.4.5要因計画結果](v045_factorial_design_results.md)
- [IEEE-CIS technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md) /
  [Santander technique taxonomy](../controller_reference/santander_technique_taxonomy.md)
- 生データ:`docs/v044_v044_suite_a06_diagnostics.json`・`a07`・`b06`・`b07`
- 盲検監査誤検出の修正:コミット `2964a00`(`scripts/audit_v044_suite.py`)
