# v0.4.2 クロスコンペ統合分析 — IEEE-CIS(`v041-trackb-03`)× Santander(`v042-mc-b02`)

**⚠️ 訂正(2026-08-30):** 本ドキュメント全体(および参照先の v0.4.3-f 分析)は、
ユーザーの承認を得ずに継承されていた固定10列制約の下で行われた
([インシデント記録](v044_ten_column_constraint_incident.md))。特に「IEEE-CIS の
layer1(上位解法技術クラス)一致率が0%」という記述は、本文中では「匿名化の効果」
とのみ説明しているが、v0.4.4 pilot(全106列)の結果、列数不足も主要因だった可能性が
高いことが判明した——「匿名化」と「列数不足」を切り分けた再検証は未実施のまま。
best-of-population・未知構造発見という2つの claim 自体(性能面での存在命題)は
10列という制約下でも内部的に妥当だが、「上位解法相当の技術に到達できるか」という
問いへの答えはこの訂正を踏まえて読むこと。今後の計画は
[c_lite_v044_policy.md](../c_lite_v044_policy.md) を参照。

**目的:** [c_lite_v042_policy.md](../c_lite_v042_policy.md) §0 の 2 つの claim(best-of-
population 近傍到達・未知構造発見)を、修正済み permutation のもとで完了した 2 コンペの
**クリーンな全データ**で統合評価する。IEEE-CIS 側は
[v042_best_of_population_ieee_cis_retrospective.md](v042_best_of_population_ieee_cis_retrospective.md)
(v041-trackb-01 の汚染された 2 run のみが対象)を置き換える、より完全な分析。

## サマリ

| 指標 | IEEE-CIS(v041-trackb-03) | Santander(v042-mc-b02) |
| --- | --- | --- |
| P2 再現要件達成構成 | 2/3(opus×P3・sol×P3) | **3/3(全構成)** |
| Matched Negative 昇格 | 0/48 | 1/48 |
| Negative AUC 中央値 | 0.522 | 0.503 |
| Promoted 候補パック数 | 27/48(56%) | 37/48(77%) |
| Population 最大 gain(vs baseline AUC) | **+0.1878** | +0.0904 |
| opus×P1(合成P1構成)の成否 | 1/4(非達成) | **4/4(完全達成)** |
| taxonomy との構造一致 | 0/6(下記参照) | 部分一致(技術クラス#2) |

## Claim 1(best-of-population 近傍到達)への回答

**両コンペで performance 面の claim 1 は成立する**——population 内に capacity-matched
baseline を明確に上回る候補が複数・独立に存在した(IEEE-CIS 最大 +0.19 AUC、Santander
最大 +0.09 AUC)。gain の絶対値は IEEE-CIS の方が大きいが、これは元々の signal-to-noise
比の違い(§7 のコンペ選定表通り Santander は「強い stress test」)を反映しており、
「diverse population の中にベストな1つが存在する」という存在命題自体はどちらでも真である。

**構造面(taxonomy 一致)は非対称。** IEEE-CIS は
[technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md) の 6 クラスと
0/6 一致(匿名化により UID 復元・カテゴリエンコーディング等の列意味論依存クラスに到達
しにくいため、と分析済み)。Santander は
[technique taxonomy](../controller_reference/santander_technique_taxonomy.md) の技術クラス
#2(特徴独立性前提のモデリング)と部分一致した——「単一の共有線形方向が文脈を越えて
汎化する」という発見は、Santander の実際の上位解法が持つ「200特徴がほぼ独立、per-feature
線形寄与の合成」という設計思想と構造的に近い。

**両コンペを跨いで独立に繰り返し現れた、taxonomy 未収載のメタ技術パターン(新規発見):**

1. **「Context プーリング/leave-one-context-out 汎化」——最も顕著な共通パターン。**
   IEEE-CIS では 12 run 中複数(`agent-02-s17`「3つのcontextはexchangeableな shard」、
   `agent-03-s17`「context 間の invariant phenotype」、`agent-03-s93`「context-invariant
   risk surface」)、Santander では検証した全 3 run が独立に「3つのcontextは別々の
   regimeではなく単一の共有機構に支配されている」という同型の claim へ到達した。
   これは**コンペ固有の技術クラスではなく、Track B/v0.4.2 のプロトコル自体
   (research/confirmation/transferの3区間×3独立contextという設計)が誘導する、
   データ形式非依存のメタ技術**——「pack-level の観測単位が正しいか、context-level か」
   という検証幾何そのものを疑うという未知構造発見の一形態。
2. **「Activation/sparsity-profile 集約」(IEEE-CIS のみ、複数run で独立再現)。**
   `agent-01-s42`(scale-free panel-burden)・`agent-02-s42`(active-channel breadth
   count)・`agent-02-s93`(identity-free row-profile aggregate)が独立に、「どの特徴が
   非ゼロか」という occurrence パターン自体が予測力を持つという構造に到達した——v1の
   retrospective で見た「hurdle-type occurrence/log-magnitude decomposition」
   (opus×P3、v041-trackb-01)と同系統の発見が、修正済み Suite でも複数モデル・複数
   seed で独立に再現している。これは taxonomy には無いが、実際の欠損値パターン・
   カウント特徴を使う実務的な fraud detection 技術(例:非欠損 D-column 数)と構造的に
   近い——**taxonomy 側が「技術クラスの記述粒度が細かすぎる」ことを示唆する**(個別列名
   ではなく「occurrence/sparsity-pattern の集約」という水準で記述すべきだった)。

これらは**このラウンドの構造スコアには算入しない**(taxonomy はスコアリング前に固定された
参照物であるべきで、事後に見つかったパターンを遡及して taxonomy に追加するのは
circular になる)。次ラウンドの taxonomy 設計への入力として記録するに留める。

## 解法の多様性(v0.4.2 §2 のレバーが実際にもたらした多様性の実測)

promoted パックの `translation_kind`(採用された解法の要約記述)をユニーク化して数えると:

- **IEEE-CIS:promoted 27 パック中、9 通りの異なる `translation_kind`**——
  activation/sparsity 系(active-channel breadth count 等)、pooled context-invariant
  model 系(CatBoost・HistGradientBoosting をそのまま pooled fit)、burden/phenotype 系
  (signed-log・robust-scale 特徴)、threshold-state ensemble 系など、**アプローチの
  「種類」自体が複数存在する**——単一の解法が繰り返し当たっているのではない。
- **Santander:promoted 37 パック中、12 通りの異なる `translation_kind`**——ほぼ全てが
  「pooled/shared linear score」という同じ大枠のバリエーション(ridge・L2 logistic・
  z-scored・ECDF正規化・marginal-rank 等、正規化/推定方法の違い)——IEEE-CIS より
  収束度が高い。これは Santander の真の構造(特徴のほぼ独立性、線形分離可能性)が
  そもそも単純であることの反映と考えられる。

**この非対称性自体が claim 1 の重要な観測結果:** 「diverse な population の中にベストな
1つが存在する」という best-of-population の存在命題は、**構造が複雑なコンペ(IEEE-CIS)
では複数の質的に異なるアプローチが population に共存し、構造が単純なコンペ(Santander)
では同じアプローチの精緻化バリエーションが多数を占める**——多様性戦略(§2 のレバー:
reasoning effort・P3 自己批判・独立 run 数)の価値は、コンペの構造的複雑さに応じて
異なる形で発揮されるとわかった。

## Claim 2(未知構造の発見)への回答

**両コンペで成立。** 上記のメタ技術パターン(context プーリング、activation/sparsity 集約)
は、Controller が(technique taxonomy 構築時点で)事前に想定していなかった構造であり、
blind discovery の枠組みが機能した証拠である。

## opus×P1 のコンペ依存性——新しい知見

合成 Track A で P1 達成基準を満たした唯一の構成(opus×P1、cycle=4)が、実データでは
**IEEE-CIS で 1/4、Santander で 4/4** と正反対の成否を示した。P3(自己批判 scaffold)は
両コンペで安定して機能した(IEEE-CIS 3/4、Santander 4/4)。**単一の合成側最良構成を
複数の実コンペに無条件で持ち込むのはリスクが高く、P3 のような自己批判機構を伴う構成の方が
コンペを跨いだ頑健性が高い**——今後の複数コンペ展開(Rossmann 含む)では、P1 単独ではなく
P3 系構成を優先すべきという実践的な示唆。

## 追記(v0.4.3-a):「context プーリング」発見は artifact か、実データの構造か

[v0.4.3 方針](../c_lite_v043_policy.md) §1 の検証を、新規 agent run なしで手持ちデータ
(`agent_submission.json` の `claim` テキスト・`leave_one_context_out_stable`・診断 JSON の
`promoted`/`family`)のみを使って実行した。全 96 パック(IEEE-CIS)+ 全 96 パック
(Santander)を `opaque_pack_id` で診断 JSON と突合し、claim テキストがプーリング(context
間の共有機構・exchangeable・context-invariant 等)を主張しているかを分類した。

**IEEE-CIS(v041-trackb-03):**

| | 件数 | 内訳 |
| --- | --- | --- |
| Promoted(27件) | プーリング主張 17(63%)/ 非プーリング 10(37%) | 非プーリングは activation/sparsity・burden/phenotype・threshold-ensemble 系 |
| Matched Negative(48件) | プーリング主張を試みた 21件 | **昇格 0 / falsified 21(100%)** |
| 上記21件中 `leave_one_context_out_stable` | True 8 / False 13 | LOCOを通過しても昇格には至らない |

**Santander(v042-mc-b02):**

| | 件数 | 内訳 |
| --- | --- | --- |
| Promoted(38件) | プーリング主張 38(100%) | 非プーリングの promoted は 0 |
| Matched Negative(48件) | プーリング主張を試みた 48件(100%) | **昇格 1 / falsified・却下 47(98%、既知の FSPR 汚染1件と一致)** |
| 上記48件中 `leave_one_context_out_stable` | True 6 / False 42 | True 6件のうち昇格は1件のみ——残り5件は別ゲートで却下 |

**重要な発見:`promotion_passed` は `leave_one_context_out_stable` とは独立な、より厳しい
下流ゲートである。** Matched Negative パックがプーリングを主張して LOCO を通過しても
(IEEE-CIS 8/21、Santander 6/48)、`promotion_passed` はほぼ全てを追加で棄却している——
FSPR がほぼゼロ(IEEE-CIS 0/48、Santander 1/48)である理由は、この 2 段階ゲートが機能して
いるためだと確認できた。代表的な却下理由(Santander の Matched Negative、LOCO通過後に
`promotion_passed: False`):「pooling は real だが unvalidated な予測gainをもたらす……LOCO
AUC 0.551、permutation p=0.0125……しかし independent implication が—」。別例では明示的に
「context 間の係数ベクトルは自身の permutation null を超えて一致しない(cosine -0.012 vs
null -0.013)」として falsified。

**結論(artifact 説は積極的に反証された、ただし留保あり):**

1. Matched Negative でのプーリング主張は IEEE-CIS 100%・Santander 98% が正しく棄却されて
   おり、Suite 全体の FSPR とほぼ一致する。プーリング主張が昇格ロジックに優遇されている
   なら、プーリング主張に限定して false promotion 率が高くなるはずだが、逆にほぼゼロである。
2. IEEE-CIS では promoted 27 件中 37% が非プーリング(activation/sparsity 集約等)で
   昇格しており、**プーリングは昇格への唯一の抜け道ではない**——これが artifact 説への
   最も強い反証。
3. **留保:** Santander は promoted・negative の**両方**で claim 試行率が 100% であり、
   Santander 単独では「エージェントがプーリングを主張しがちである」と「Santander の真の
   構造がプーリング(=共有線形方向)そのものである」を区別できない(taxonomy 技術クラス#2
   との部分一致と整合的)。この区別を可能にしているのは IEEE-CIS の非プーリング昇格の
   存在である。また `leave_one_context_out_stable` が非プーリング promoted パック(IEEE-CIS
   10件全て)で一律 `True` になっている点は、この field がプーリング以外の claim に対して
   意味のある negative signal として機能しているかは未確認——ただし今回の artifact 判定
   自体には影響しない。

**判定:v0.4.3-a の問いへの回答は「本物の構造(2段階ゲートに正しく守られている)」。**
taxonomy 2層化(v0.4.3-b)は計画通り進めてよい——プーリングは artifact ではなく、
taxonomy 層2(データ形式非依存のメタ技術)に正式に組み込む価値のある発見だったと判断する。

## 追記(v0.4.3-f 準備):解法多様性・上位解法一致・探索幅の全数監査(2026-08-30)

ユーザーが新たに提示した価値基準(解法多様性・その中の上位解法相当の存在・未知構造探索
エージェントの識別)に基づき、既存の promoted 全パック(IEEE-CIS 27件・Santander 38件)を
layer1(コンペ固有)・layer2(データ形式非依存)taxonomy 双方に対して**全数**照合した
(従来は 2 run のみの spot check、または `translation_kind` のユニーク数カウントに留まって
いた)。

**技術クラス一致率:**

| | IEEE-CIS(27件) | Santander(38件) |
| --- | --- | --- |
| L1 #1〜#6 一致(いずれか) | 6件(UID復元2・GBMアンサンブル4、22%) | 17件(特徴独立性モデリング、45%) |
| L2 #1 context プーリング | 19件(70%) | 38件(100%) |
| L2 #2 occurrence/sparsity 集約 | 7件(26%) | 0件(0%) |
| 未分類(層1・層2いずれとも不一致) | 4件(15%) | 0件 |
| **多様性指数(観測された技術クラスの組み合わせの種類数)** | **6** | **2** |

**解釈:** IEEE-CIS は上位解法クラスとの部分一致(UID復元・GBMアンサンブル)を持ちながら
質的に異なる複数の技術クラスが共存する、多様性指数6の population。Santander は
layer2#1(プーリング)がほぼ全件を占め、layer1側もほぼ単一クラス(特徴独立性モデリング)
に収束する多様性指数2の population——[解法の多様性セクション](#解法の多様性v042-2-のレバーが実際にもたらした多様性の実測)
の `translation_kind` ユニーク数(IEEE-CIS 9通り・Santander 12通り)と一見矛盾するように
見えるが、`translation_kind` はパラメータ化・正規化方法の違いまで区別する細かい粒度で
あるのに対し、taxonomy 一致は「技術クラス」という粗い粒度である——両指標は補完的:
Santander は「同じ技術クラスの精緻化バリエーションが多い」、IEEE-CIS は「異なる技術
クラスが複数共存する」という、既存の分析と整合する結果が数値でも裏付けられた。

**探索幅(未知構造探索エージェントの識別、新設の評価軸):** run 単位で「サイクル横断で
提案された `hypothesis_family` の異なり数」+「保持された `shadow_candidate_ids` 総数」を
探索幅の代理指標として全 24 run(両コンペ計)をランク付けした。

- **両コンペで一貫して、opus run(agent-01/02、config MC/TB-opus-P1・P3)が sol run
  (agent-03、config MC/TB-sol-P3)を探索幅で明確に上回った。** IEEE-CIS:opus 45〜67 点
  vs sol 19〜26点。Santander:opus 47〜89点 vs sol 26〜33点。同じ P3 プロンプトアーム
  でも sol の shadow candidate 保持数は opus のおよそ半分。
- 最高探索幅:IEEE-CIS は `agent-01-s93`(TB-opus-P1、shadow 64件)、Santander は
  `agent-01-s124`(MC-opus-P1、hypothesis_family 9種・shadow 80件)。
- `failure_trace.above_row_unit_considered`・`history_or_link_intervention_considered` は
  全 run で True——プロンプトが要求する最低限の考慮事項であり、この2つ単独では
  run 間の弁別力を持たない(プロンプト設計上の天井効果)。

**v0.4.3-f(進行中の sol reasoning-effort 多様性ラウンド)への含意——重要な留保:**
この監査は sol エージェント(config_id `*-sol-P3`、reasoning_effort=xhigh)が、同一
プロンプトアーム P3 であっても opus より探索幅が構造的に狭いことを示した。現在進行中の
`V043_SOL_EFFORT_CONFIGS`(sol のみ、reasoning_effort を low〜xhigh で振る)ラウンドの
結果を解釈する際は、**reasoning effort を上げることが探索幅を opus 相当まで引き上げるか
どうか自体を観察すべき問いとして扱う**(それを所与の前提とせず)。もし xhigh でも探索幅が
opus に届かない場合、それは「sol というモデル自体の探索スタイルの違い」であって
reasoning_effort 単独では代替できない可能性を示唆する——これ自体もこのラウンドの発見と
して記録する。

## 追記(v0.4.3-f 総括):sol reasoning-effort 多様性ラウンド、3ラウンド・28 run を終えて

Claude(opus)クォータ枯渇を受け、sol(codex/gpt-5.6-sol)単独・reasoning-effort 多様性
という代替レバーで、2コンペ・3ラウンド(screening n=1 → 確認 n=4 → population拡大
n=8)・計28 run を実施した。詳細は
[IEEE-CIS側](v043_sol_effort_diversity_ieee_cis.md)・
[Santander側](v043_sol_effort_diversity_santander.md)・
[ps -ef 盲検リーク事例](v043_blindness_incident_ps_ef_leak.md)を参照。ここでは
3つの価値基準への最終的な回答をまとめる。

**1. 解法多様性:** sol 単独では、opus を含む元の混合構成(多様性指数 IEEE-CIS 6・
Santander 2)には届かなかったが、**population を広げる(n=4→n=8)ことで新たな技術
クラスが出現し続けた——特に IEEE-CIS では「収束」ではなく「増加」が観測された**
(発見14)。一方 Santander は population を広げても均質なまま(発見16)——**多様性が
population サイズに応じて伸びるかどうか自体が、コンペの構造的複雑さに依存する**、
という新しい知見が得られた。

**2. 上位解法相当の存在:** IEEE-CIS は全ラウンドを通じて layer1(列意味論依存)一致
ゼロを維持(匿名化の効果は reasoning effort・population サイズに依存しない頑健な
制約)。Santander は 87.5%(n=8中7件)が layer1#2(特徴独立性モデリング、公開1st
place解法の設計思想)と一致——高水準を維持した。

**3. 未知構造探索エージェント:** これが今回のラウンドの最も重要な方法論的教訓を
生んだ。**単一 seed の screening で見えた「脱出」(IEEE-CIS `SD-high-P3`/seed93 の
occurrence/sparsity、Santander `SD-low-P1`/seed17 の非線形多変量)は、いずれも
n=4 の確認では再現しなかった**(発見9・11・13)——単発の novel-structure 発見を
過大評価してはならないという直接的な教訓。**しかし population をさらに n=8 まで
広げると、IEEE-CIS では全く別の新規 unclassified パターンが出現し、うち1件
(seed402)は Santander の当初の脱出claim(seed17)と構造的にほぼ同一の
「加法性の限界」を主張していた**(発見15)——収集済み全データ(8 suite・60 run)を
対象に事後検索したところ、この claim は**独立4件**(両コンペ、3種の effort/arm
構成、うち3件は実際に一部パックが promoted まで到達)確認され、単なる偶然の
一致ではなく**繰り返し現れる仮説フレーミング**であることが分かった——ただし
4件全てが sol 単独ラウンドに限られ、opus では1件も観測されていない(下記
「今後の方針への含意」参照)。**十分な population サイズがあれば、コンペを跨いで
繰り返し現れる新しいメタ技術候補を見出せる**、という、より頑健な形で未知構造探索の
価値が確認された——ただし今回見つかった候補が「データ形式非依存の構造」なのか
「sol というモデル特有の仮説生成スタイル」なのかは、opus での追加確認が必要で
未確定のままである。

**方法論的な副産物:** (a) 両コンペとも、round4(残りの確認漏れセルを埋める)を経て
**2つずつの頑健な sol 単独構成**を確定した——IEEE-CIS:`SD-high-P3`(n=8中6/8)・
`SD-high-P1`(n=4中4/4)。Santander:`SD-high-P1`(n=8中6/8)・`SD-xhigh-P3`
(n=4中4/4)。(b) 8 seed目にして Santander 側で初めて FSPR 汚染が1件観測され、
Controller 側の独立検証が正しく機能することを実地で確認した(発見17)。(c) バッチ
オーケストレータの起動引数経由の盲検リーク(`ps -ef`)を発見・修正し、新しい不変
条件として記録した——suite_id だけでなく、エージェントバッチを起動する全ての
コマンドの引数がコンペ名を含まないよう徹底する必要がある。(d) 「加法性の限界」
候補パターンは最終的に**5件独立観測**(両コンペ、4種のeffort/arm構成)まで
積み上がったが、**Santander では低effortにのみ紐づき、高effort構成では一貫して
不在**という、コンペ固有の条件依存性が新たに判明した——「データ形式非依存」か
「sol特有の仮説生成スタイル」かの判定に加え、「コンペごとに出現条件が異なる」
という3つ目の未解決の問いを残した。

**v0.4.3-f 最終スコアカード(4ラウンド・計34 run):**

| | IEEE-CIS | Santander |
| --- | --- | --- |
| 頑健な sol 単独構成数 | 2(SD-high-P3 6/8、SD-high-P1 4/4) | 2(SD-high-P1 6/8、SD-xhigh-P3 4/4) |
| population拡大での新規技術クラス出現 | あり(2件のunclassified) | なし |
| 「加法性の限界」候補の観測数 | 3件(medium-P1・high-P3・high-P1) | 2件(low-P1のみ、高effortでは0件) |
| FSPR汚染(全34 run中) | 0件 | 1件(round3、seed402) |
| layer1(上位解法)一致率 | 0%(全ラウンド共通) | 87.5%(n=8中7件) |

## 今後の方針への含意

1. **v0.4.2 の 2 claim は 2 コンペで独立に実証された。** 3 コンペ目(Rossmann、回帰対応後)
   または Jigsaw の追加は、「2 コンペでの実証」を「N コンペでの一般則」に格上げするための
   次のステップとして位置づけられる。
2. **技術クラス taxonomy は、コンペ固有の具体的技術(列意味論依存)とデータ形式非依存の
   メタ技術(context プーリング、occurrence/sparsity 集約等)の 2 層で設計し直す価値が
   ある。** 現行 taxonomy は前者に偏っており、後者を捉えられていない。第3の候補
   (「加法性の限界」)は、収集済み全データ(8 suite・60 run)を対象にした事後検索の
   結果、**独立4件**(両コンペ、3種の effort/arm 構成)まで確認数が伸びた——ただし
   4件全てが sol 単独ラウンドでのみ観測され、元の opus+sol 混合バッチには1件も
   出現しなかった。「データ形式非依存の構造発見」ではなく「sol 特有の仮説生成
   スタイル」である可能性が排除できないため、[層2 taxonomy](controller_reference/meta_technique_taxonomy_layer2.md)
   には**候補**として記録し、opus での再現が確認されるまで正式な層2クラスへの
   昇格を保留した。
3. **実行構成の選定は「合成側の最良構成」ではなく「複数コンペでの頑健性」で判断すべき。**
   P3 系(自己批判)構成を今後の多コンペ展開でも優先する。
4. **単一 seed の discovery を「エージェントが未知構造の探索に成功した」と主張する際は、
   必ず追加 seed での再現確認を経ること。** これが v0.4.3-f で最も重い教訓であり、
   今後の全ラウンドに適用する標準的な作法とする。
5. **多様性を求める場合、reasoning effort やプロンプトアームを変えるより、同一の
   頑健な構成で population を広げる方が有効な場合がある**(IEEE-CIS の事例)——ただし
   これはコンペの構造的複雑さに依存し、普遍的な処方箋ではない(Santander では
   効かなかった)。

## 正本

- [IEEE-CIS qualification](v041_track_b_qualification.md) / [Diagnostics](../v041_trackb_03_diagnostics.json)
- [Santander qualification](v042_santander_qualification.md) / [Diagnostics](../v042_mc_b02_diagnostics.json)
- [IEEE-CIS technique taxonomy](../controller_reference/ieee_cis_technique_taxonomy.md)
- [Santander technique taxonomy](../controller_reference/santander_technique_taxonomy.md)
- [初期の限定分析(superseded)](v042_best_of_population_ieee_cis_retrospective.md)
