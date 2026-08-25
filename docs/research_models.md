# Deep Research 依頼文

Kaggleコンペティションを自律的に攻略するAIシステムについて調査してください。 背景 現在想定しているベースラインは、複数のAIエージェントが共通のKPI（Local CV、Leaderboard Score等）の改善を目標とし、それぞれ異なるモデル、特徴量、検証方法、データ処理等を探索しながら、進化・淘汰・探索を繰り返す方式です。 しかし、この方式では解法の多様性を確保できても、全エージェントが同じKPIや誤ったvalidationを最適化し、「そもそも何を調べるべきか」「現在の問題理解のどこが間違っているか」を発見できない可能性があります。 そこで、Thomas Parr、Giovanni Pezzulo、Karl Fristonによる以下の書籍を主要な理論的出発点とします。 Active Inference: The Free Energy Principle in Mind, Brain, and Behavior MIT Press https://direct.mit.edu/books/oa-monograph/5299/Active-InferenceThe-Free-Energy-Principle-in-Mind 特に以下の概念に注目してください。 _ Preferred states _ Generative model _ Belief states _ Uncertainty _ Expected Free Energy _ Epistemic value / Information gain _ Pragmatic value _ Active exploration _ Belief update 目的はActive Inferenceを忠実に実装することではありません。これらの考え方を利用し、単なる「KPIを改善するAI」から、「Kaggleで勝つための未知の勝ち筋を発見するAI」へ発展させることに実証的な価値があるかを検証することです。 中心仮説 過去のKaggle上位解法には、特定モデルや特徴量を超えて共通する「勝てる研究状態」が存在する可能性があります。 例えば、 _ 問題・データ生成過程を十分理解している _ Local validationがPrivate Leaderboardを適切に近似している _ train/test distribution shiftを理解している _ entity、time、group等の潜在構造を理解している _ leakageやlabel noiseを検証している _ 重要な未知・不確実性を把握している _ 有力仮説について反証実験を行っている _ 複数のsolution familyを探索している _ error diversityを持つモデル群を保持している _ ensembleの多様性が確保されている といった状態です。 このような状態を過去の上位解法からモデル化し、現在の研究状態との差を推定しながら、複数エージェントが「性能向上」と「不確実性削減」の双方を目的として実験を選択する方式を検討します。 ただし、過去の勝者から作ったPreferred Stateそのものへの過学習やconfirmation biasも重大なリスクとして扱ってください。 ⸻ Research Questions 以下を中心に調査してください。 RQ1：Kaggle上位解法に再利用可能な「勝てる研究状態」は存在するか 過去のKaggleコンペを幅広く調査し、Top solutionが高順位に到達するまでに行った重要な発見を分析してください。 最終的なモデル名やハイパーパラメータだけではなく、 _ validation strategyの変更 _ train/test distribution分析 _ adversarial validation _ time consistency _ entity identification _ leakage発見 _ label noise分析 _ subgroup分析 _ feature representationの変更 _ target transformation _ external data _ pseudo-labeling _ post-processing _ candidate generation _ model diversity _ ensemble diversity _ error analysis _ ablation _ domain knowledge _ 失敗した仮説から得た知識 などを重点的に調査してください。 最低20〜30コンペ、可能なら50コンペ以上を対象とし、tabular、time-series、CV、NLP、recommendation等、異なる問題タイプを含めてください。 1位だけでなくTop 3〜10の解法も可能な範囲で比較してください。 ⸻ RQ2：KPIを直接改善しない実験は、最終的な勝利に寄与しているか 特に、 Local CVを直接改善しなかったが、その後の重要な発見やPrivate LB性能につながった実験 を探してください。 例えば、 _ time splitを試した結果、random CVが不適切だと判明した _ adversarial validationからdistribution shiftを発見した _ subgroup分析から未知のデータ構造を発見した _ 弱いモデルを試したことでensemble diversityが向上した _ 特徴量を追加して性能が下がったことで誤った仮説を排除できた といった事例です。 この種の「Information Gainを目的とした実験」がKaggle上位者の研究プロセスで実際に重要なのかを評価してください。 ⸻ RQ3：Evolution + Quality Diversityだけで十分ではないか 以下を調査してください。 _ Population-Based Training _ Evolutionary Algorithms _ Genetic Algorithms _ MAP-Elites _ Quality-Diversity _ Novelty Search _ Bayesian Optimization _ Multi-Armed Bandit _ Bayesian Experimental Design _ Active Learning _ Optimal Experimental Design _ Scientific Discovery Agent _ Multi-Agent Research System _ Falsification / hypothesis testing agents Kaggle攻略を、 Performance + Exploration + Diversity だけで十分に実現できる可能性と、 Performance + Exploration + Diversity + Epistemic Value まで必要になる可能性を比較してください。 特に、 diversityのためのexploration と、 uncertaintyを減らすためのepistemic exploration を明確に区別してください。 ⸻ RQ4：Active Inferenceを導入する理論的・実証的必然性はあるか Active Inferenceそのものを採用することを前提にしないでください。 以下を比較してください。 _ Active Inference _ Bayesian Experimental Design _ Information Gain maximization _ Active Learning _ Bayesian Optimization _ Reinforcement Learning with intrinsic motivation _ Curiosity-driven exploration _ Quality-Diversity _ Population-Based Training _ Scientific method / falsification Kaggle自動研究システムに必要な機能を、より単純な既存理論で実現できるなら、その点を明確に指摘してください。 Expected Free Energy等を厳密に実装することに実用上のメリットがない場合も、そのように結論してください。 ⸻ RQ5：Preferred Research Stateをどう定義すべきか 過去コンペの分析から、 Kaggle Winning Research State として利用可能な状態変数を提案してください。 例えば、 _ Problem Understanding _ Data Generating Process Understanding _ Validation Confidence _ Distribution Shift Understanding _ Error Understanding _ Hypothesis Coverage _ Hypothesis Confidence _ Falsification Coverage _ Feature-space Coverage _ Model-space Coverage _ Solution Diversity _ Error Diversity _ Robustness _ Performance などです。 各状態について、 _ 定義 _ 観測方法 _ 定量化方法 _ uncertainty _ 更新方法 _ 実験との関係 _ Private LBとの関係 を検討してください。 「最終的に勝ったから高評価」のような事後的・循環的な指標は避けてください。 ⸻ RQ6：複数エージェントはどのような役割分担が適切か 全エージェントを同じ解法へ収束させるのではなく、hypothesis diversityを維持する方法を調査してください。 例えば、 _ Data Scientist Agent _ Validation Scientist Agent _ Feature Scientist Agent _ Model Scientist Agent _ Distribution Shift Agent _ Explorer _ Falsifier _ Ensemble Agent _ Meta Researcher などです。 solution diversityとepistemic diversityの違いを考慮してください。 ⸻ RQ7：Information Gainを実際にどう測定するか 最重要項目の一つとして調査してください。 実験 (e) の価値を、 Performance Gain だけでなく、 Information Gain として評価する方法を検討してください。 例えば、 _ hypothesis posteriorの変化 _ entropy reduction _ uncertainty reduction _ hypothesis space reduction _ validation confidenceの改善 _ downstream experiment selectionへの影響 _ CV→Private LB予測精度の改善 _ unexplained residualの減少 などを候補として比較してください。 LLMが主観的に「情報価値が高い」と判断するだけの設計は避け、可能な限り測定可能な方法を探してください。 ⸻ 過去Kaggleによる検証方法 最終的には過去コンペを利用した反証可能な実験設計を提案してください。 最低でも以下の3方式を比較します。 System A：KPI Hill Climbing Local CV等のKPIを直接改善する。 System B：Evolutionary Multi-Agent 複数Agentによる、 _ Explore / Exploit _ Evolution _ Quality Diversity を利用する。 System C：Epistemic Evolutionary Multi-Agent System Bに、 _ Preferred Research State _ Belief State _ Explicit Uncertainty _ Information Gain _ Epistemic Experiment Selection _ Falsification _ Belief Update を追加する。 以下の条件を可能な限り統一してください。 _ 使用LLM _ token budget _ compute/GPU budget _ wall-clock time _ experiment数 _ submission数 _ 初期情報 _ 利用可能な外部情報 評価には少なくとも、 _ Private Leaderboard score / rank _ Public Leaderboard score _ Local CV _ CV→Private correlation _ discoveryした重要仮説数 _ 上位解法のcritical discovery再発見率 _ hypothesis diversity _ solution diversity _ error diversity _ experiment efficiency _ compute cost を含めてください。 特に、System CがSystem Bを上回らない場合には、 Active-Inference-inspiredなEpistemic Layerを追加する価値は確認できない と反証できる設計にしてください。 ⸻ 検証に適した過去コンペ この比較実験に適した過去Kaggleコンペを調査してください。 条件として、 _ Private Leaderboardが確定済み _ 上位解法のwrite-upが十分存在する _ 単純なハイパーパラメータ探索だけでは上位に到達しにくい _ validation設計、distribution shift、特徴量発見等が重要 _ critical discoveryを後から特定可能 \* 現在でもデータ・評価環境を可能な限り再現可能 なものを優先してください。 特にIEEE-CIS Fraud Detectionが適切か詳細に評価し、それ以外の候補も複数提示してください。 ⸻ 最終的に判断してほしいこと 調査結果から、以下について明確な結論を出してください。 1. 過去のKaggle winnerから「Winning Research State」をモデル化できるか。 2. KPI改善とは独立したEpistemic Valueを実験選択に導入する価値があるか。 3. Evolution + Quality Diversityだけで十分ではないか。 4. Active Inferenceを採用する必然性があるか、それとも他理論の方が適切か。 5. 実装するなら最小構成は何か。 6. この仮説を最も効率よく反証できる過去Kaggleコンペは何か。 7. System A/B/Cの比較実験をどのように設計すべきか。 8. この研究アイデアの最大の弱点・失敗条件は何か。 Active Inferenceを肯定することを目的にしないでください。 最も単純なEvolutionary Multi-Agent方式で十分なら、そのように結論してください。 逆に、過去Kaggleの証拠から、Information Gain・Belief Update・Falsification等を明示的に持つことで追加的な価値が期待できるなら、その根拠を具体的に示してください。 情報源 可能な限り一次情報を優先してください。 優先順位： 1. Kaggle公式competition / winning solution / discussion / write-up 2. 原著論文 3. MIT Press等の原著書籍 4. 著者・研究機関公式ページ 5. 信頼できる技術ブログ Kaggle上位解法については、二次的なまとめ記事だけで判断せず、可能な限り実際のwinner write-upを確認してください。 最終報告では、重要な主張ごとに情報源を示し、事実・推論・仮説を明確に区別してください。

# 調査結果 Kaggleを「KPI最適化」から「未知の勝ち筋の発見」へ進化させるAIシステムの研究

## 結論

本調査の結論は、**Active InferenceをそのままKaggleエージェントへ実装する必然性はない。しかし、現在のEvolutionary / Quality-Diversity型の自動ML研究エージェントに「明示的な不確実性」「仮説」「反証」「Information Gain」を追加する研究には、十分な実証的価値がある**、というものです。

特に重要なのは、Active Inferenceの数式体系ではなく、

> **「良い行動とは、いま一番スコアが上がりそうな行動だけではなく、将来の意思決定を改善するために重要な不確実性を解消する行動でもある」**

という考え方です。Active Inferenceでは、Expected Free Energyの中にepistemic valueとpragmatic valueが入り、行動が「望ましい結果を得ること」と「隠れた状態について情報を得ること」を同時に考慮します。Parr、Pezzulo、Fristonの書籍はActive Inferenceを知覚・計画・行動を確率的推論として扱う枠組みとして整理しており、Pezzuloらもepistemic valueを情報獲得、extrinsic/pragmatic valueを目的達成として分けています。citeturn28search6turn28search0turn28search2

しかしKaggleに必要なのは、この認知科学的理論全体ではありません。**Bayesian Experimental Design（BED）のExpected Information Gain、Quality-Diversity、明示的な仮説レジストリ、反証実験、OOF error diversityを組み合わせれば、必要機能のほぼ全部をより直接的に実装できます。** BED自体が「次にどの実験をすれば未知パラメータについて最も情報を得られるか」をExpected Information Gainで定式化する一般的な実験設計フレームワークです。citeturn28search1turn28search5

さらに、現在の自律MLエージェント研究は「まずEvolution + Diversityを強いベースラインとして倒すべきだ」という方向をかなり強く支持します。MLE-benchは75のKaggle competitionを自律ML engineering benchmark化しており、初期研究ではo1-preview+AIDEが16.9%のcompetitionで少なくともメダル水準に到達しました。また単に独立attempt数を増やすだけでもpass@1の16.9%からpass@8の34.1%まで上昇しました。citeturn23view2turn24view0 その後の研究ではGreedy、MCTS、Evolutionary searchとoperator設計の組み合わせによりMLE-bench Liteのmedal success rateを39.6%から47.7%へ改善しています。citeturn23view0turn25academia31 さらに2025年の11,000 trajectory、約120万search nodeを分析した研究では、agentのideation diversityと性能に相関があるだけでなく、diversityを実験的に減らすと性能が低下するという介入結果まで報告されています。citeturn26view0

したがって、**System Cが倒すべき相手は単純なgreedy hill climbingではなく、既に相当に強いEvolutionary/QD searchです。**

私の最終判断を先にまとめると次の通りです。

| 問い                                               | 判断                                                                                                                                                        |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WinnerからWinning Research Stateをモデル化できるか | **できる。ただし「正解状態」ではなく、不確実性付きresearch-state distributionとして定義すべき**                                                             |
| KPIとは独立したEpistemic Valueに価値はあるか       | **かなり有望。ただしKaggle write-upから得られる証拠は主にretrospectiveで、因果効果はまだ未証明**                                                            |
| Evolution + QDだけで十分か                         | **十分である可能性は高く、強い帰無仮説として扱うべき。ただしsolution diversityだけではvalidation/DGPについての集団的誤信念を防げない**                      |
| Active Inferenceは必要か                           | **不要。理論的着想は有用だが、厳密なExpected Free Energy実装は現時点では過剰**                                                                              |
| 最小実装                                           | **Evolution/QD + hypothesis registry + validation-world uncertainty + EIG/VoI experiment selection + falsifier + error-diversity ensemble**                 |
| 最初の反証用competition                            | **IEEE-CIS Fraud Detection。ただし単独では危険。Rossmann/Airbus/RiiidまたはH&Mを追加する**                                                                  |
| A/B/C実験                                          | **同一LLM・総token・compute・実験budgetで、hidden private evaluatorと事前定義critical discoveriesを使う**                                                   |
| 最大の弱点                                         | **winner write-up由来のhindsight/survivorship biasと、現代LLMによるKaggle solution memorization。次いで「belief entropyを減らすが間違っている」Goodhart化** |

## Kaggle上位解法に存在する再利用可能な研究パターン

### 調査範囲

一次情報の質を優先し、本調査では**38 competitionをコアケース**として調べました。50件へ機械的に増やすより、1stだけでなくTop 3〜10付近のofficial discussion/write-upまたは当事者論文を確認できるものを優先しています。対象はtabular、forecasting/time-series、CV、NLP、recommendation/online prediction、multimodalを含みます。

これは「38 competitionの統計的meta-analysis」ではありません。write-upに記録される情報は不均一で、失敗実験は特に欠落します。したがって以下では、**観察事実とそこからの推論を分けます。**

### 上位解法で観察されたcritical discoveries

| Competition                               | タイプ                   | モデルそのものより重要だった研究上の発見・構造                                                                                                                                                                                                                                                                                                                        |
| ----------------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| IEEE-CIS Fraud Detection                  | Tabular/Fraud            | 1st solutionは時間を意識したvalidationを用い、最初の4か月でtrain、1か月空けて後月をpredictする実験を行った。さらにUID/client/card identityの再構成が、fraud detection、seen/unseen client validation、post-processingへつながった。複数上位解法でもadversarial validationやtime validationが検討された。citeturn18search0turn5search4turn5search12turn18search5 |
| Santander Customer Transaction Prediction | Tabular                  | 上位解法ではtest中のsynthetic/fake rowsを識別し、real test rowsとtrainを用いたfrequency/count representationが「magic」と呼ばれる重要要素になった。通常のmodel tuningというよりtest生成構造の理解が勝ち筋を変えた。citeturn19search0turn19search1turn19search3turn19search4                                                                                     |
| Home Credit Default Risk                  | Tabular/Relational       | 上位勢は単純な表形式だけでなく、複数relational table、時間順序、sequence representationを扱った。Top-10 solutionにはcredit-scoring文献・domain knowledgeをfeatureへ落とす研究もあった。citeturn20search0turn20search1turn20search2turn20search3                                                                                                                 |
| Elo Merchant Category Recommendation      | Tabular/Temporal         | 上位write-up群ではCV設計、集約特徴、時間情報、ensembleが中心で、Public LBよりCVを信頼するという研究判断が明示的に共有された。citeturn6search4turn6search6turn6search8                                                                                                                                                                                            |
| TalkingData AdTracking Fraud Detection    | Temporal/Tabular         | 上位解法ではday単位のholdout、時系列を意識したtarget/count encoding、時間・メモリ制約を考慮したfeature engineeringが中心となった。citeturn8search9turn8search6turn8search0                                                                                                                                                                                       |
| Avito Demand Prediction                   | Multimodal               | text/image/tabularの異種representationを探索。3rd solutionでは通常の5-fold ensembleとtime-series validation系ensembleを併用している。citeturn8search1turn8search7turn8search4                                                                                                                                                                                    |
| Mercari Price Suggestion                  | NLP/Tabular              | 1stはむしろsingle sparse-input MLPへ集中し、2ndはRidge/ngram等4モデル、3rdはCNN/FTRL-FM系だった。**「多数family探索・複雑ensembleは必須」というWinning Stateを反証する重要なcounterexample。** citeturn8search2turn8search8turn8search11                                                                                                                         |
| American Express Default Prediction       | Tabular/Temporal         | 上位解法は顧客時系列集約、autoregressive representation、OOF/time features、巨大ensembleなど異なる経路を採用。16th solutionはfeature diversity/ensembleを明示的テーマにした。citeturn17search6turn17search2turn17search10turn17search27turn17search13                                                                                                          |
| Jane Street Market Prediction             | Online/Financial         | 1stはsupervised autoencoder+MLP。上位〜中上位write-upではtime embedding、stock/entity構造、target denoising、online inference設計が重要テーマだった。citeturn17search11turn17search14turn17search3turn17search17                                                                                                                                                |
| Rossmann Store Sales                      | Forecasting              | WinnerはPublic LBよりも**信頼できるholdoutの設計が最重要の洞察だった**と説明。未来のprivate periodへ外挿するための時間的holdout、曜日/promotion/event-distance等を扱った。citeturn7search5turn7search8                                                                                                                                                            |
| Corporación Favorita Grocery Sales        | Forecasting              | 上位勢はLightGBM、CNN/DNN、seq2seq等かなり異なるfamilyを使い、時系列representation自体が主要探索対象となった。citeturn7search19turn7search14turn7academia24                                                                                                                                                                                                      |
| M5 Forecasting Accuracy                   | Hierarchical Forecasting | 上位にはDeepAR系、LightGBM/Poisson/Tweedie等が混在。後続の評価研究ではM5 metricの階層aggregation/scaling等が評価安定性に影響することが示されており、「validation metric自体の理解」が重要な問題だった。citeturn14search3turn14search2turn14search16turn14academia25                                                                                             |
| Web Traffic Time Series                   | Forecasting              | 1stを含む上位解法でseasonality、robust statistics、time-series特有のrepresentation/ensembleが中心となった。citeturn13search0turn13search3                                                                                                                                                                                                                         |
| Recruit Restaurant Visitor Forecasting    | Forecasting              | calendar/holiday handling、target encoding、時間的補完などの問題固有featureが重要で、holidayを同曜日へ対応付けるようなdomain/time correctionも報告された。citeturn13search1turn13search13turn13search9                                                                                                                                                           |
| ASHRAE Great Energy Predictor III         | Forecasting/Tabular      | 上位solutionでは建物・meter・weather・時間構造のfeature engineeringに加え、leak/external informationの扱いが大きな研究テーマとなった。citeturn6search9turn6search1turn6search7turn6search11                                                                                                                                                                     |
| TGS Salt Identification                   | CV/Segmentation          | 上位解法はarchitectureだけでなくaugmentation、resolution、mask/post-processing、loss等の組み合わせを探索した。citeturn10search0turn10search25turn10search16turn10search23                                                                                                                                                                                       |
| Airbus Ship Detection                     | CV/Detection             | 上位write-upには「LBよりCVを信じる」という明示的教訓があり、train image間のoverlapを検出する探索も行われた。classification/detection/segmentationという異なるproblem decompositionも存在した。citeturn10search17turn10search1turn10search9turn10search13                                                                                                        |
| Severstal Steel Defect Detection          | CV/Segmentation          | 上位勢でclassification+segmentationやclass-wise decomposition等が使われ、問題を独立サブタスクへ分解することで安定化を狙う解法もあった。citeturn10search14turn10search10turn10search26turn10search29                                                                                                                                                             |
| RSNA Pneumonia Detection                  | Medical CV               | RetinaNet系、single-stage detector、U-Net segmentationなどTop solution間でproblem representation自体が異なった。6th solutionではedge detection的性質が重要な洞察とされた。citeturn11search1turn11search7turn11search21                                                                                                                                           |
| SIIM-ACR Pneumothorax                     | Medical CV               | classification+segmentation、semi-supervision、mask filtering/scoringなど複数のproblem decompositionが上位に存在した。citeturn11search22turn11search17turn11search26turn11search8turn11search11                                                                                                                                                                |
| Humpback Whale Identification             | Metric Learning/CV       | classification、ArcFace、SIFT+Siameseと上位solution familyが大きく異なる。model diversityより前に**representation/hypothesis diversity**が有効だった好例。citeturn11search3turn11search15turn11search9                                                                                                                                                           |
| Bengali.AI Handwritten Grapheme           | CV                       | 上位では強力なCNN family、multi-head formulation、seed bagging等が使われた。5thは同一SEResNeXt familyのseed diversity中心であり、「異なるmodel familyが必ず必要」という仮説への反例でもある。citeturn15search12turn15search0turn15search8                                                                                                                        |
| Planet Amazon                             | Multi-label CV           | architecture、augmentation、thresholding/ensembleに加え、Public/Private順位のshake-upも観測され、LBのみへの適応リスクを示すケースとなった。citeturn15search5turn15search1turn15search13                                                                                                                                                                          |
| Carvana Image Masking                     | Segmentation             | 1stを含む上位で高解像度segmentation、coarse-to-fine/refinementなどproblem decompositionの工夫が重要だった。citeturn15search2turn15search6turn15search10                                                                                                                                                                                                          |
| DSTL Satellite Imagery                    | Remote Sensing           | multispectral bands、spectral indices、boundary treatmentなどdomain representationが重要だった。3rd-place論文は複雑ensembleなしでも上位と競える結果を報告しており、ここも「ensemble diversity万能論」の反例。citeturn15search7turn14academia24turn15search11                                                                                                     |
| Quora Insincere Questions                 | NLP                      | pretrained embedding、meta-embedding、EMA/ensemble等に加え、短い実行時間の中でLocal CVとLBをどう対応させるかが重要だった。大きなPublic→Private shake-upの事例もある。citeturn12search12turn12search4turn12search20turn12search24                                                                                                                                |
| Jigsaw Toxic Comment Classification       | NLP                      | 1st solutionではpseudo-labelingによりunlabeled testから追加学習信号を得ることが有効とされた。citeturn12search9turn12search5                                                                                                                                                                                                                                       |
| Jigsaw Unintended Bias                    | NLP/Fairness             | global AUCだけでなくsubgroup/BPSN/BNSP系評価構造を直接意識したloss/modelingが上位で使われた。**metric decompositionとsubgroup error understanding**の明確な例。citeturn12search2turn12search28turn12search10                                                                                                                                                     |
| Quora Question Pairs                      | NLP/Graph-like           | 上位解法は大量feature、複数level model、duplicate/question relationship等を組み合わせる方向に進み、単一text classifierだけではない研究空間だった。citeturn12search3turn12search7                                                                                                                                                                                  |
| Tweet Sentiment Extraction                | NLP/Span Extraction      | token start/end predictionだけでなくrerankingやpost-processingが上位差分になった。label生成ルールをreverse-engineerする探索も報告された。citeturn16search28turn16search1turn16search4                                                                                                                                                                            |
| Google QUEST Q&A Labeling                 | NLP                      | BERT familyに加えてmulti-model、target/post-processingの研究が行われ、「post-processing magic」の独立探索も存在した。citeturn16search5turn16search20turn16search17                                                                                                                                                                                               |
| CommonLit Readability Prize               | NLP                      | Winnerはexternal data、teacher/student、sentence representationなどを組み合わせ、training distributionを越えたrepresentation learningを利用した。citeturn17search0turn17search4                                                                                                                                                                                   |
| Feedback Prize ELL                        | NLP                      | pretrained modelだけでなくback-translation、rank loss、pseudo-labeling、pooling等を探索。2nd solutionではrank loss/back-translationのCV/PB寄与を記録している。citeturn16search0turn16search3turn16search9                                                                                                                                                        |
| H&M Personalized Fashion Recommendations  | Recommendation           | 上位解法の中心は単純なclassifier選択ではなく、**candidate generation → feature engineering → ranking → ensembling**という研究構造。candidate recallの確保がsolution spaceを規定した。citeturn17search1turn17search15turn17search20                                                                                                                               |
| Santander Product Recommendation          | Recommendation           | 上位解法ではcustomer history/temporal product transitions、ranking/ensemble等を利用し、raw multiclass prediction以上の構造化が行われた。citeturn21search2turn21search12turn21search9                                                                                                                                                                             |
| Riiid Answer Correctness Prediction       | Online/Sequence          | Transformer/SAKT/LSTM/GBDTなど多様なfamilyが存在し、lag/time featuresとonline inference consistencyの理解が重要だった。28th solutionではTransformer単体のCVが高くなくてもensembleへ貢献したと報告されている。citeturn21search5turn21search22turn21search11turn21search8                                                                                         |
| Google Landmark Retrieval                 | Retrieval/CV             | 1st-place系研究ではmetric learning、clean-sample weighting、異なるtraining dataset、high-resolution fine-tuning、ensemble等を組み合わせた。citeturn14academia26                                                                                                                                                                                                    |
| NOMAD Materials                           | Scientific/Tabular       | Top solutionsはcrystal graph、handcrafted descriptors+GBDT、SOAP+NNなどrepresentationから大きく異なり、representation/model error correlationを比較する科学的探索になっていた。citeturn14academia28                                                                                                                                                                |

### 「Winning Research State」は存在するか

**[推論] 存在します。ただし「上位者が共通してXGBoostを使う」「ensemble数が多い」のようなrecipeではありません。**

38ケースから最も再利用可能なのは、特定のアルゴリズムではなく次のような**研究上の認識状態**です。

第一に、**validationを問題そのものとして研究している状態**です。RossmannではWinner自身がreliable holdoutを最重要洞察として挙げています。IEEE-CISではtime-based splitとclient identityの理解が結びつきました。Airbusでは上位解法がLBよりCVを信頼する教訓を明示しています。Riiidではonline inference protocolとの整合性が問題になります。M5では、そもそもevaluation procedureの安定性自体が後続研究の対象になっています。citeturn7search5turn18search0turn10search17turn21search11turn14academia25

第二に、**row単位のsupervised learning問題として受け取らず、背後のデータ生成過程を推定している状態**です。IEEE-CISのclient/card identity、Santanderのfake/real test rows、Airbusのoverlapping images、Jane Streetのstock/time structure、H&Mのcandidate-generation processはこの例です。citeturn5search12turn19search1turn10search1turn17search17turn17search15

第三に、**評価metricの平均値だけでなく、どこで、なぜ、誰に対して間違うかを分解している状態**です。Jigsaw Unintended Biasのsubgroup metric分解、Riiidのsequence/time consistency、RSNA/SIIMのclassification vs localization decompositionが典型です。citeturn12search28turn21search11turn11search1turn11search17

第四に、**solution familyがcollapseしていない状態**には価値があります。ただし「常に多数familyを保持する」ことをPreferred Stateにしてはいけません。Mercari 1stはsingle modelへ集中し、DSTL 3rdも複雑ensembleなしで競争的でした。Bengali.AIでは同一architectureのseed diversityだけでも上位になりました。つまりPreferred Stateは「多様性が大きいほどよい」ではなく、**まだ解けていない不確実性に対して必要な独立仮説が残されているか**で評価すべきです。citeturn8search2turn14academia24turn15search8

### KPIを直接改善しない実験は重要だったか

ここは証拠の強さを慎重に区別する必要があります。

**[事実] 上位者が、即時KPIよりvalidation/DGP/structureを理解するための実験を行った例は多数存在します。** IEEE-CISでのtime split、adversarial validation、UID探索、Santanderでのfake-row identification、Airbusでのimage overlap探索などは典型です。citeturn18search0turn18search1turn18search5turn19search1turn10search1

**[事実] 「弱い単体modelでもensembleには価値がある」ケースも存在します。** Riiidの28th-place write-upではTransformerがCV単体では高くなかったにもかかわらずensembleに貢献したと説明されています。これは「個体KPI」と「population value」が一致しない具体例です。citeturn21search8

**[推論] これらはEpistemic Valueの存在を強く示唆しますが、因果証明ではありません。** Winner write-upは成功後に書かれます。失敗したadversarial validationを100回試した人は書かないかもしれず、成功した「magic」だけが後から重要に見えるsurvivorship/hindsight biasがあります。

したがってRQ2への厳密な答えは、

> **Kaggle上位者の研究プロセスがinformation-seekingである証拠は強い。一方、「Epistemic Valueを明示的にobjectiveへ入れると最終Private LBが上がる」という証拠はまだない。これは実験で検証すべき未確立仮説である。**

です。

## Evolution、Quality Diversity、Active Inferenceをどう位置付けるべきか

### まず強い帰無仮説は「多様な探索だけで十分」

PBTは固定compute budgetの中でpopulationを維持し、performanceを基準にexploitしながらhyperparameterをmutateして探索します。citeturn29search0 MAP-Elitesはユーザーが定義したbehavior dimensionsごとにhigh-performing eliteを保持するため、単一最適解ではなく「異なるタイプの良い解」のarchiveを作れます。citeturn29search1

この考え方はKaggleに非常によく合います。

たとえばarchiveの軸を、

`validation=random/time/group`

`model=GBDT/linear/NN/transformer`

`representation=raw/aggregate/sequence/graph`

`data=train-only/transductive/external`

などにすれば、同一CV最適化でもsolution collapseをかなり防止できます。

実際、自律Kaggle研究でも探索の効果は既に確認されています。MLE-benchではAIDEのようなKaggle専用tree-search scaffoldがgeneral-purpose agentより強く、AIRA系研究はGreedy/MCTS/Evolutionary searchとoperator設計の重要性を示しています。citeturn24view0turn25search0turn25academia31 Ideation diversityを明示的に減らすとMLE-bench performanceが低下する介入実験もあり、**System Bは弱いbaselineではありません。** citeturn26view0

### Diversity explorationとEpistemic explorationは同じではない

ここが本研究の核心です。

**Diversity exploration**とは、

> 「まだ試していない種類のsolutionを試す」

ことです。

CNNしかないのでTransformerを試す、GBDTしかないのでlinear modelを残す、異なるfeature familyをarchiveに埋める、という探索です。

一方、**Epistemic exploration**とは、

> 「現在競合している世界モデルのうち、どれが正しいかを最も区別できる実験をする」

ことです。

例えば、

- random CVとtime CVのどちらが未来Privateを近似しているかを判別するためにpseudo-backtestを作る。
- `H₁: test shiftはtime由来` と `H₂: entity composition由来` を区別できるslice experimentを行う。
- UIDが本物のcustomer identityなのか偶然のfrequency artifactなのかを見るため、UID内/UID外generalizationを比較する。
- high CV modelとlow CV modelのresidual correlationを測り、ensemble価値仮説を検証する。

という行動です。

MAP-Elitesは異なるbehavior cellを埋められますが、**cellが「model family」だけなら、population全体が同じ間違ったvalidationを信じたまま多様化できます。** PBTもperformance maximizationがfitnessなので同じです。citeturn29search0turn29search1

逆に、MAP-Elitesのbehavior descriptorに

`validation worldview`

`shift hypothesis`

`entity hypothesis`

`label-noise hypothesis`

などを入れ、archive selectionに仮説のdiscrimination valueまで組み込めば、QD自身がかなりepistemicになります。

つまり、

> **「QDでは不十分だからActive Inferenceが必要」という二択は誤りです。十分に一般化したQDはSystem Cのかなりの部分を吸収できます。**

したがって比較実験には、A/B/Cだけでなく後述する**System B+**が不可欠です。

### 理論比較

| 枠組み                           | 強い点                                                                 | Kaggleでの欠点                                                  | 評価                               |
| -------------------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------- |
| Hill Climbing / BO               | KPI改善をsample-efficientに探索                                        | KPIやvalidation自体が間違っていると高速に間違った方向へ進む     | 必要だが不足                       |
| PBT / Evolution                  | exploit/explore、並列化、継承                                          | uncertaintyや「何を学んだか」を持たない                         | 強いbaseline                       |
| MAP-Elites / QD                  | high-performance solutionを多様性付きで保持                            | descriptor設計が悪ければ「多様なだけ」                          | **非常に重要**                     |
| Novelty Search                   | deceptive objectiveから脱出可能                                        | noveltyと有用な情報は異なる                                     | 補助的                             |
| Curiosity / intrinsic motivation | prediction error等で未知へ向かう                                       | stochastic/noisyな領域を「面白い」と誤認しうる                  | 補助的                             |
| Bayesian Optimization            | posterior uncertaintyを使い効率的にobjective search                    | 通常はobjectiveそのものを既知と仮定                             | HPO等に有効                        |
| Active Learning                  | informative observationを選択                                          | 通常は「どのlabelを得るか」の問題で、Kaggle研究行動全般より狭い | 一部適用                           |
| Bayesian Experimental Design     | 仮説/parameterについてExpected Information Gainで実験を選べる          | outcome model構築が必要、EIG計算が高価                          | **最も直接的**                     |
| Scientific falsification         | 競合仮説を反証可能な予測へ落とせる                                     | utility optimizationは別途必要                                  | **強く推奨**                       |
| Active Inference                 | generative model、belief、uncertainty、epistemic/pragmatic valueを統一 | Kaggle研究全体のgenerative modelを作る必要があり過剰            | 概念源として有用、実装必須ではない |

Bayesian Optimizationはposteriorを利用して次の評価点を効率的に選ぶため、hyperparameter optimizationには非常に適しています。Snoekらの古典的研究もGP posteriorによる効率的な実験選択を示しています。citeturn27search0 ただしBOが通常問うのは「未知objective surface上でどこを評価するか」であって、**「そもそもrandom CVをobjectiveとして信頼してよいか」ではありません。**

Curiosity-driven explorationはprediction errorをintrinsic rewardとして未知状態を探索します。citeturn29search2 しかし「予測できないもの」と「Kaggleで知るべきもの」は一致しません。random noiseの多いfeatureもcuriousです。

BEDはより適しています。Expected Information Gainは、experiment outcomeによって未知parameter/hypothesisについてposteriorがどれほど変化するかを直接評価します。citeturn28search1turn28search8

Active Inferenceはさらにpragmatic valueとepistemic valueを統一的に扱えますが、Kaggleではその統一が**必須ではありません**。citeturn28search0turn28search6

### Active Inferenceを厳密実装しない方がよい理由

Active Inferenceとして真面目に実装するなら、

- hidden research state
- observation model
- state transition model
- policy
- preferred outcome distribution
- uncertainty/precision
- expected future observations

を含むgenerative modelを構築し、policyのExpected Free Energyを推定する必要があります。Active Inferenceそのものは、この種のgenerative-model-based probabilistic inferenceを中心に置く理論です。citeturn28search6turn28search2

しかしKaggle research processでは、

`adversarial validationを実施 → AUC=0.85`

`UID feature experiment → CV +0.002`

`time split → model orderが逆転`

のようなexperiment outcome distributionを正確に予測するgenerative modelを持っていません。

**間違ったgenerative modelから精密なExpected Free Energyを計算すると、「精密に間違う」だけです。**

BEDにも同じmodel-misspecification問題はありますが、少なくとも「どの仮説について、どの実験結果を予測しているのか」が局所的・監査可能です。現代BEDのレビューでも実用上の計算コストが中心課題とされています。citeturn28search1turn28search3

したがって私なら、

> **Active-Inference-inspired, Bayesian-Experimental-Design-implemented**

とします。

「Preferred states」「belief state」「epistemic value」という考え方は借りる。しかしfree-energy machineryは実装しません。

## Kaggle Winning Research Stateの具体的定義

### Preferred Stateは一点ではなく分布にする

最も危険なのは、Winner corpusから

> winnerはadversarial validationをする  
> winnerはpseudo-labelingする  
> winnerはensembleする  
> winnerはexternal dataを使う

のようなチェックリストを作ることです。

MercariやDSTLの反例が示すように、特定solution patternはcompetition依存です。citeturn8search2turn14academia24

Preferred Research Stateは、

> **「何を使っているか」ではなく「重要な問いについてどの程度根拠ある理解を持っているか」**

で定義すべきです。

以下が提案する最小research-state vectorです。

| State                                  | 定義                                                              | 観測・定量化                                                                                 | Uncertainty / update                    | Private LBとの想定関係                                |
| -------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------- | ----------------------------------------------------- |
| **Validation Fidelity**                | Local validationが実際のgeneralization regimeをどれほど再現するか | 複数pseudo-backtestでmodel rankingのSpearman/Kendall、split間score variance、rank reversal率 | bootstrap posterior。新backtestごと更新 | 最重要。高ければCV improvementがPrivateへ伝播しやすい |
| **DGP Understanding**                  | row/labelがどう生成されたかという競合仮説の理解                   | time/entity/group/duplication等の事前登録hypothesisと予測実験                                | hypothesis posterior                    | hidden structureに合うfeature/validationを選べる      |
| **Distribution Shift Understanding**   | train/validation/test差の原因と影響を把握                         | adversarial classifier AUC、MMD/KS等＋feature/slice別shift、shift-conditioned error          | bootstrap + hypothesis posterior        | shift-aware CV/model選択へ直結                        |
| **Entity & Temporal Integrity**        | 同一entity、time causality、duplicate/overlapを正しく扱えているか | Group/Time CV差、duplicate graph、within/out-of-entity error                                 | testごと更新                            | leakage防止とtrue generalization推定                  |
| **Data / Label Quality Understanding** | label noise、measurement noise、leakage、synthetic rows等の理解   | duplicate disagreement、label residual、anomaly slice、target predictability checks          | Beta/Bayesian error-rate estimates      | fake signalへの過学習防止                             |
| **Error Understanding**                | 「どこでなぜ失敗するか」を説明できる程度                          | subgroup metric dispersion、residual clustering、sliceによるerror variance説明率             | resampling uncertainty                  | targeted feature/model/ensembleへつながる             |
| **Hypothesis Coverage**                | 重要なalternative explanationが探索されているか                   | taxonomy cell occupancy、semantic-cluster数、effective hypothesis count                      | noveltyとposteriorを分離                | blind spotを減らす                                    |
| **Hypothesis Calibration**             | belief confidenceと実験結果が整合するか                           | Brier/log score、予測区間coverage                                                            | sequential calibration                  | confident-but-wrong研究を抑止                         |
| **Falsification Coverage**             | 高確率仮説が反証可能な実験を受けた割合                            | posterior-weighted fraction of hypotheses with discriminating test                           | test結果ごと更新                        | confirmation bias低減                                 |
| **Representation / Model Coverage**    | 有意味に異なるsolution regionsを探索した程度                      | MAP-Elites occupancy、family descriptors                                                     | archive update                          | local optimum回避                                     |
| **Solution / Error Diversity**         | 予測誤差が独立な強いsolutionを保持できているか                    | OOF residual correlation、prediction disagreement、covariance effective rank                 | OOF追加ごと更新                         | ensemble gainに直接関係                               |
| **Robustness**                         | seed/split/perturbationに対する安定性                             | score SD、worst-case split、rank stability                                                   | bootstrap                               | Public→Private shake-up低減                           |
| **Performance Belief**                 | hidden performanceの現在推定                                      | validated model scoreをvalidation-fidelityで補正したposterior                                | 全実験で更新                            | 最終目的。ただし単一CV値にしない                      |

重要なのは、**Distribution Shift Understandingのpreferred valueは「shift=0」ではない**ことです。

大きなshiftが存在していても、

> 「このfeature群にはtime driftがあり、Privateではこの方向へ動き、モデルrankingへの影響はこの程度」

と高いconfidenceで理解できているなら研究状態は良い。

同様にHypothesis Coverageも「entropyが最大なら良い」ではありません。十分探索した結果、ある仮説にposterior 0.9で集中するのは良い状態です。

したがってPreferred Research Stateは固定vector `s*` より、

\[
p(s\_\text{good}\mid \text{competition context})
\]

という**context-conditioned distribution**として扱うべきです。

Winner corpusから学習する場合も、leave-one-competition-outだけでなく**leave-one-domain-out**でpriorを学習し、「tabular fraud winnersの習慣」を別のCV competitionへ押しつけない設計が必要です。

### Belief Stateは仮説レジストリに落とす

抽象的なLLM memoryではなく、各仮説を機械可読形式にします。

例:

```text
H_17
Claim:
    Random CV is optimistic because the test set represents future time periods.

Prior:
    P(H_17) = 0.55

Predictions:
    If H_17:
        chronological backtests will be worse than random CV,
        and model rankings will change.
    If not H_17:
        chronological and random model rankings should be similar.

Potential falsifier:
    multiple rolling backtests with stable rank correlation > 0.95

Evidence:
    E_12, E_18, ...

Posterior:
    P(H_17 | evidence) = 0.81

Downstream implications:
    use time CV
    reduce weight on frequency features unstable across time
```

最近のscientific-agent研究でも、明示的なfalsification experimentやhypothesis/evidence cycleを持たせる方向が研究されていますが、これらはまだ新しい研究であり、Kaggleへの効果が確立しているわけではありません。citeturn2search3turn2search27

### Preferred State overfittingを防ぐ

Preferred Stateへの過学習は、このアイデア最大級のリスクです。

対策としては、

**Winner solutionを行動recipeへ変換しないこと。**

「pseudo-labelingしたか」ではなく、

`unlabeled test distributionについて重要な不確実性を検証したか`

と抽象化します。

さらに、

`preferred-state prior strength`

自体を小さくし、current competition evidenceが簡単にpriorを上書きできるようにします。

最も重要なのは、**winnerだけから学習しないこと**です。同一competitionのTop 1、Top 3–10、さらに「Public上位→Private失速」「有名だが失敗したsolution」をnegative/control例として含めるべきです。PlanetやQuora系のshake-upは、Public performanceをresearch-state qualityと同一視できないことを示しています。citeturn15search13turn12search24

## Information Gainと複数エージェントをどう実装するか

### Information Gainの基本式

experiment \(e\) がresearch hypothesis \(H\) について与えるExpected Information Gainを、

\[
\mathrm{EIG}(e)
=
\mathbb{E}_{y\sim p(y\mid e,D)}
\left[
D_{\mathrm{KL}}
\left(
p(H\mid D,e,y)
\Vert
p(H\mid D)
\right)
\right]
\]

と置けます。

これは

\[
I(H;Y_e\mid D)
\]

というmutual informationです。Bayesian Experimental Designの標準的な考え方です。citeturn28search1turn28search8

ここで重要なのは、**HをNN weightにしない**ことです。

Kaggle研究では例えば、

\[
H=
\{
H*{\text{time-shift}},
H*{\text{entity-shift}},
H*{\text{label-noise}},
H*{\text{duplicate-leak}},
H\_{\text{candidate-recall}},
...
\}
\]

です。

### LLMの「なんとなく情報価値が高い」を排除する

実験を提案するとき、agentに必ず次を事前登録させます。

```text
Experiment e

Competing hypotheses:
    H1, H2, H3

Observable:
    y

Predicted outcome distribution:
    p(y | H1, e)
    p(y | H2, e)
    p(y | H3, e)

Measurement noise:
    ...

Cost:
    GPU minutes / tokens / wall time

Decision affected:
    which validation?
    which feature family?
    which models?
```

例えばtime split experimentなら、

```text
H1: random CV is optimistic due to temporal drift
prediction:
    rank correlation(random, rolling-time) ~ low

H0: temporal drift is negligible
prediction:
    rank correlation(random, rolling-time) ~ high
```

という形です。

LLMは仮説と予測を提案できますが、posterior updateは可能な限り**実際のmetric・統計量から機械的に行う**べきです。

### Realized Information Gainだけを報酬にしてはいけない

実験後、

\[
IG*\text{realized}
=
KL(p*{t+1}(H)\|p_t(H))
\]

を計算することはできます。

しかしこれをfitnessにすると、

> ノイズを見てposterior 0.5 → 0.99へ誤って自信を持つ

agentも「大量informationを得た」と評価されます。

したがってInformation Gainには少なくとも、

- belief calibration
- experiment reproducibility
- held-out diagnostic predictive log score

を組み合わせます。

### EIGより実用的なのはExpected Value of Information

Kaggleで本当に欲しいのは「beliefを大きく動かす情報」ではなく、

> **後続の研究行動を良くする情報**

です。

したがって可能ならExpected Value of Sample Informationに近い、

\[
EVSI(e)
=
\mathbb{E}\_{y}
\left[
\max_a
\mathbb{E}[U(a)\mid D,e,y]
\right]

- \max_a
  \mathbb{E}[U(a)\mid D]
  \]

を使う方がよい。

たとえば「feature 17とfeature 21の相関構造についてentropyを大きく減らす」が今後のmodel choiceを一切変えないなら、EIGはあってもdecision valueはほぼゼロです。

実用上のexperiment utilityは、

\[
\begin{aligned}
U(e)={}&\alpha \widehat{\Delta \mathrm{Performance}}
+ \beta EVSI(e)
+ \gamma QD(e)
+ \delta \widehat{\Delta Robustness} \\
&- \eta Cost(e)
- \rho Risk(e)
\end{aligned}
\]

程度で十分です。

ここでもFree Energyは必要ありません。

### 測定可能なInformation Gain proxy

完全なBayesian modelを作れない場合には、次の順で使うのが現実的です。

| 方法                                                       |     客観性 | 実装難度 |  推奨 |
| ---------------------------------------------------------- | ---------: | -------: | ----: |
| competing hypotheses間のBayes factor / likelihood ratio    |       高い |       中 |     ◎ |
| posterior entropy reduction                                |       高い |       中 |     ◎ |
| validation-world entropy reduction                         |       高い |       中 | **◎** |
| model/world ensembleのpredictive Jensen-Shannon divergence |     中〜高 |   低〜中 |     ○ |
| pseudo-private backtestでのCV→future rank予測改善          | 非常に高い |       中 | **◎** |
| unexplained residual reduction                             |       高い |       低 |     ○ |
| downstream experiment policyの変化                         |     中〜高 |       中 |     ○ |
| LLM self-score「この実験は有益」                           |       低い |       低 |     × |

とりわけ**Validation Information Gain**は最初に実装すべきです。

候補validation worldを、

\[
W=\{
W*\text{random},
W*\text{time},
W*\text{group},
W*\text{time+group},
...
\}
\]

とし、「どのvalidation regimeがfuture-like backtestを最も説明するか」のposteriorを維持します。

これならActive Inferenceのgenerative model全体を作らず、Kaggleで最も重要なlatent uncertaintyだけを明示化できます。

### エージェントの役割分担

全Agentを「もっとCVを上げろ」にすると、名前だけmulti-agentで実態はparallel hill climbingになります。

推奨構成は以下です。

| Agent                                  | 主目的                                                 | 成功指標                                  |
| -------------------------------------- | ------------------------------------------------------ | ----------------------------------------- |
| **Validation Scientist**               | random/time/group/rolling/OOFのどれを信頼するか検証    | validation fidelity、rank stability       |
| **DGP / Shift Scientist**              | entity、time、duplicates、train/test shiftを推定       | structural hypothesis resolution          |
| **Explorer**                           | 独立したsolution/hypothesis family生成                 | QD occupancy、hypothesis novelty          |
| **Falsifier**                          | 現在最有力の仮説を壊す                                 | posterior-weighted falsification coverage |
| **Feature / Representation Scientist** | feature、aggregation、target transform、representation | incremental performance + coverage        |
| **Model Scientist**                    | architecture/loss/training                             | performance frontier                      |
| **Error / Ensemble Scientist**         | subgroup、residual、error correlation、blend           | residual effective rank、ensemble gain    |
| **Meta Researcher**                    | budget配分、belief update、research-state gap管理      | final utility / experiment efficiency     |

重要なのは**Falsifierをsolution agentと独立させること**です。

自分が発見したUIDを自分で反証するagentはconfirmation biasを持ちやすい。Falsifierには、

> 「現在populationが最も信じている仮説を、最小computeで否定できる実験を探せ」

という別objectiveを持たせます。

AIDE/AIRA系研究でもmemory scopeやoperator designがagent trajectoryへ大きく影響し、mode collapseやdebug loopを避けるためにscoped memoryが重要とされています。citeturn24view0turn26view0

したがって全Agentに同じ巨大shared memoryを常時見せるより、

- shared empirical facts
- private working hypotheses
- explicit hypothesis registry

を分離する方がよいでしょう。

これが**solution diversity**と**epistemic diversity**の違いです。

Solution diversity:

> LightGBM、Transformer、CNNがある。

Epistemic diversity:

> Agent Aはtime shiftを主因と考える。  
> Agent Bはentity shiftを主因と考える。  
> Agent Cはlabel mechanismを疑う。

後者がなければ、3種類のmodelが全て間違ったrandom CVを最適化することがありえます。

## 検証に適した過去KaggleとIEEE-CISの評価

### IEEE-CIS Fraud Detectionは非常に良い候補

**[判断] System B vs Cの最初のproof-of-mechanismとして、IEEE-CIS Fraud Detectionは最有力候補です。**

理由は「強いXGBoost featureが知られているから」ではありません。

このcompetitionには少なくとも、

**時間構造**

1st solutionは最初の数か月でtrainし、期間を空けて後続期間をvalidationする時系列的実験を行っています。citeturn18search0

**潜在entity**

winner discussionではclient/cardに相当するUIDを再構成することがfraud detection、seen/unseen client validation、post-processingへつながると説明されています。citeturn5search4turn5search12

**train/test shift**

複数参加者がadversarial validationを利用し、feature削減やpseudo train/public/private analysisを行っています。citeturn18search1turn18search2turn18search3turn18search5

つまり、

> 「KPIを上げるexperiment」

と

> 「validation/DGPについて理解を深めるexperiment」

を比較しやすい。

System Cが本当に意味を持つなら、かなり早い段階で

- random CVへの疑念
- temporal generalization
- entity identity
- seen/unseen entity差
- distribution shift

へresearch budgetを配るはずです。

### ただしIEEE-CISだけで結論を出してはいけない

最大の理由は**contamination**です。

IEEE-CISの「UID」「Vesta」「time split」のようなsolutionは非常に有名で、2026年時点の強いLLMが高レベル戦略をpretrainingから知っている可能性があります。

MLE-bench自身もtraining contaminationを重要問題として扱い、winner discussionへのmodel familiarityやcompetition description obfuscationを検証しました。GPT-4oについてはfamiliarityとperformanceの系統的関係やobfuscationによる有意な低下は確認されませんでしたが、これは「すべてのモデル・すべてのstrategy-level memorizationを排除した」という意味ではありません。citeturn24view0

さらにMLE-benchは、多くのcompetitionで元のhidden test setを使えないため、公開trainを新たにtrain/testへ再分割しています。通常は元trainの一部を新testとし、original private leaderboardとhuman performanceを比較しています。citeturn24view0turn22search6

これは本研究ではかなり重要な問題です。

**validation researchを評価したいのに、benchmark作成時の再splitによってoriginal competitionのtime/entity shiftを消してしまったら、最も重要なepistemic challenge自体がなくなります。**

したがってMLE-benchをそのまま使用するのではなく、元competitionのDGP構造をできるだけ保った**research benchmark variant**を作るべきです。

### 推奨benchmark portfolio

| Competition                        | Epistemic challenge                                    | 計算負荷 | Critical discoveryの明確さ | 総合                    |
| ---------------------------------- | ------------------------------------------------------ | -------: | -------------------------: | ----------------------- |
| **IEEE-CIS Fraud Detection**       | time, entity, shift, adversarial validation            |       中 |                   非常に高 | **第一候補**            |
| **Rossmann Store Sales**           | future holdout, store/time structure                   |   低〜中 |                   非常に高 | **低コストpilotに最良** |
| **Santander Customer Transaction** | synthetic/fake test structure、transductive statistics |   低〜中 |                   非常に高 | 強いstress test         |
| **Airbus Ship Detection**          | overlap、CV reliability、problem decomposition         |   中〜高 |                         高 | CV modality追加に良い   |
| **Riiid Answer Correctness**       | online temporal protocol、lag、sequence/entity         |       高 |                         高 | 強いが再現が難しい      |
| **H&M Recommendation**             | candidate generation、time、ranking                    |       高 |                         高 | recommendation代表      |
| **M5 Forecasting**                 | hierarchy、metric、future horizon                      |       高 |                         高 | validation研究に優秀    |
| **Jigsaw Unintended Bias**         | subgroup metric/error understanding                    |       中 |                         高 | error-state検証に良い   |

IEEE-CISとSantanderだけでは、「Kaggle magicを見つけるagent」を作ってしまう危険があります。Santanderでもfake rowsとfrequency structureが上位戦略を大きく変えたため、非常に有用な反面、competition-specific trickへ過適応しやすい。citeturn19search0turn19search1turn19search4

最初の研究なら、

> **Rossmann → IEEE-CIS → Airbus → Riiid/H&M**

の順がよいと考えます。

Rossmannは比較的安く、しかもwinner自身がvalidation reliabilityをcritical insightと述べているため、Epistemic Layerの最小反証に向きます。citeturn7search5

一方、**「この仮説を最も強く一発で反証するcompetition」を1つ選ぶならIEEE-CIS**です。

## System A/B/Cを反証可能に比較する実験

### 既存の自律Kaggle benchmarkを土台にする

MLE-benchは75 Kaggle competition、local grader、leaderboard normalization、固定GPU/runtime環境を備えており、autonomous ML engineering benchmarkとして非常に良い出発点です。citeturn24view0turn23view2

AIDEはML engineeringをcode optimization/tree searchとして扱い、MLE-bench等で強い性能を示しています。citeturn25search0turn25search2 AutoKaggleもmulti-agent workflowをKaggle tasksへ適用していますが、主眼はdata-science pipelineの自動化・debug・unit testingであり、本研究の「仮説posteriorとepistemic experiment selection」とは焦点が異なります。citeturn22search4turn22search8

つまりこの研究はゼロから「Kaggle agent」を作るより、

> **AIDE/AIRA型の強いsearch systemへEpistemic Layerを載せ、そのincremental valueだけを測る**

べきです。

### 比較するシステム

#### System A — KPI Hill Climbing

状態:

```text
best_solution
best_local_cv
experiment_history
```

selection:

\[
e\_{t+1}
=
\arg\max_e
E[\Delta CV(e)]
\]

CVが上がったbranchを保持し、下がったものを原則淘汰します。

#### System B — Evolutionary Quality-Diversity

System Aに加え、

```text
population
solution descriptors
archive
mutation
crossover
novelty / QD
```

を持ちます。

fitness:

\[
U_B(e)
=
\alpha\widehat{\Delta CV}
+ \gamma QDContribution
- \eta Cost
\]

model/feature/representation/split familyのdiversityを維持します。

PBT、MAP-Elites、AIRA-style evolutionary searchに近い強いbaselineです。citeturn29search0turn29search1turn25academia31

#### System C — Epistemic Evolutionary Multi-Agent

System Bにのみ、

```text
hypothesis registry
belief posterior
validation-world posterior
research-state uncertainty
expected information gain / value of information
falsifier
belief update
```

を追加します。

\[
U_C(e)
=
\alpha\widehat{\Delta CV}
+ \beta EVSI
+ \gamma QDContribution
+ \delta RobustnessGain
- \eta Cost
\]

とします。

### System B+を必ず追加する

これは非常に重要です。

System B+:

> QD descriptorにvalidation type、shift hypothesis、entity hypothesis等を入れる。ただし明示的posterior、EIG、belief updateは持たない。

これにより、

> Cが勝った理由は「Bayesian/epistemic reasoning」だったのか  
> 単に「もっと多様な探索軸を追加した」だけなのか

を分離できます。

B+ ≈ Cなら、

> **Epistemic Valueの厳密計算は不要で、QD descriptor設計だけで十分**

という研究上かなり価値のある否定結果になります。

### Winner informationは実行時に見せない

各competitionについて、実験開始前に独立annotatorがTop 1〜10 solution write-upを読み、

```text
Critical Discovery CD_1
claim
evidence required
minimum rediscovery criterion
importance
```

を作ります。

IEEE-CISなら例えば、

```text
CD1:
Temporal holdout is materially more reliable than random split.

CD2:
Rows can be grouped into useful client/card-like entities.

CD3:
Seen-client and unseen-client generalization differ.

CD4:
Train/test feature distributions contain meaningful shift.

CD5:
Entity/time aggregations materially change predictive structure.
```

とします。citeturn18search0turn5search12turn18search5

**Agentにはこのリストもwinner write-upも見せません。**

評価時のみ、

- 発見したか
- 実験で検証したか
- 実際にdecisionへ反映したか

を採点します。

単にLLMが「distribution shiftがあるかもしれない」と書いただけではrediscovery扱いにしません。

### 公平化するbudget

主実験では以下を同一にします。

| Resource                        | A/B/B+/Cで統一       |
| ------------------------------- | -------------------- |
| base LLM                        | 完全同一version      |
| LLM input/output token          | 総量同一             |
| GPU-hours                       | 同一                 |
| CPU/RAM                         | 同一                 |
| wall-clock                      | 同一                 |
| executable experiment budget    | compute-weighted同一 |
| scored public queries           | 同一                 |
| final submission                | 1つ                  |
| initial competition information | 同一                 |
| internet / external info        | 同一                 |
| starting baseline/code library  | 同一                 |

ここでは「experiment数」と「GPU-hours」を同時に完全一致させるのは適切でない場合があります。

Cが、

```text
5分のadversarial validation
```

を行う一方、Bが

```text
3時間のTransformer training
```

を行うなら1 experiment=1 experimentではないからです。

したがって**primary comparisonはcompute/token/wall-clock matched**、secondary comparisonとしてexperiment-count matchedを行うのが妥当です。

### Public LBをresearch signalとして限定する

competition中は例えば固定回数だけPublic-like score queryを許可し、Private scoreは一切見せません。

終了後、全candidate solutionをhidden evaluatorで評価します。

これによって、

\[
corr(CV, Private)
\]

を**agentにPrivateをリークせず**計算できます。

各runについて、

\[
\rho\_\text{CV-private}
=
Spearman(
\{CV_i\},
\{Private_i\}
)
\]

を算出します。

これはSystem Cが本当に「validation confidence」を改善したかを測る非常に良い指標です。

### Primary endpoint

最重要はあくまで、

> **locked final solutionのPrivate score / percentile rank**

です。

Critical discovery数やbelief calibrationが改善してもPrivate performanceが変わらないなら、Kaggle攻略システムとしてのEpistemic Layerの価値は確認できません。

Primary:

\[
\Delta\_{CB}
=
PrivatePerformance_C

- PrivatePerformance_B
  \]

Secondary:

- final Public score/rank
- Local CV
- CV→Private candidate rank correlation
- critical discovery rediscovery rate
- time-to-critical-discovery
- hypothesis diversity
- solution diversity
- OOF error diversity
- falsification coverage
- experiment efficiency
- GPU cost
- token cost
- failure/invalid-submission rate

MLE-benchの初期研究ではagentがvalid submission作成やcompute/time managementそのものに失敗することも多く、system-level reliabilityも必ず別metricとして残すべきです。citeturn24view0

### Statistical design

1 competitionで1回ずつ実行して比較するのはほぼ無意味です。MLE-bench自身も複数seedを使ってagent varianceを測定しており、その後のdiversity研究では10〜20 seed規模まで拡張しています。citeturn24view0turn26view0

提案は、competition × seedをblockとしてpaired comparisonし、

\[
Performance
\sim
System

- Competition
- System\times Competition
- RandomSeed
  \]

のhierarchical modelまたはmixed-effects analysisを使うことです。

最初は各arm 10〜12 seeds程度でpilotし、そのobserved varianceから本実験のpowerを決める方が、根拠なく固定seed数を決めるより妥当です。

### Cが勝ったと判定する条件

事前登録するべき条件は厳しくします。

**C成功:**

- C > BでPrivate performanceに実質的改善がある。
- 改善が1 competitionだけでなく複数domainで再現。
- 同budget下で改善。
- critical-discoveryまたはCV→Private calibration改善がPrivate improvementを媒介している。

**C失敗:**

- C ≈ B。
- Cは「たくさん仮説を書いた」がPrivateは改善しない。
- Cはcritical discoveryを増やすがbudget overheadで最終performanceを落とす。
- B+ ≈ C。
- EIGが高いexperimentを選んでも、その後のdecisionやPrivate performanceへ寄与しない。

この場合は明確に、

> **Active-Inference-inspired Epistemic Layerを追加する実用的価値は確認できない。Evolution/QDで十分。**

と結論すべきです。

### Component ablationも必須

C全体が勝っても、何が効いたか分からなければActive Inference説は支持されません。

最低限、

```text
C – Preferred State prior
C – explicit uncertainty
C – EIG/EVSI
C – Falsifier
C – belief update
C – epistemic agent roles
```

を比較します。

例えば

`C – EIG ≈ C`

ならInformation Gain maximization自体は不要。

`C – Falsifier << C`

なら、Active Inferenceより単純なscientific falsificationが本体だった可能性があります。

## 最終判断と研究アイデアの失敗条件

### WinnerからWinning Research Stateをモデル化できるか

**はい。ただし「winning recipe」ではなく「research readiness / epistemic health」の状態としてなら可能です。**

38 competitionの上位解法では、validation fidelity、DGP/entity/time understanding、distribution shift、error decomposition、representation hypothesis、solution/error diversityが繰り返し現れます。IEEE-CIS、Rossmann、Santander、Airbus、Riiid、H&Mなどは特に明確です。citeturn18search0turn7search5turn19search1turn10search1turn21search11turn17search15

一方、Mercari、DSTL、Bengali.AIなどは「複数family」「複雑ensemble」を必須条件にすることを否定します。citeturn8search2turn14academia24turn15search8

したがってPreferred Stateは、

> 「Xをやったか」

ではなく、

> 「Xに関する重要な不確実性を認識し、必要なら判別できるか」

で定義すべきです。

### KPI改善と独立したEpistemic Valueは導入する価値があるか

**研究仮説としてはYes。実証済みとしてはNoです。**

上位者がvalidation experiment、adversarial validation、entity discovery、fake-row analysis、error slice analysisのようなinformation-seeking behaviorを行っている証拠は多い。citeturn18search1turn19search1turn10search1turn12search28

しかしwrite-upだけでは、

\[
P(\text{win}\mid \text{epistemic experiments})
\]

の因果効果は推定できません。

ここをA/B/C retrospective benchmarkで検証する価値があります。

### Evolution + Quality Diversityだけでは不十分か

**現時点では「不十分」と断言できません。むしろSystem Bが十分という仮説を最も強いnull hypothesisに置くべきです。**

MLE-benchでは複数attemptだけでも大幅な性能改善があり、search policy/operator設計やideation diversityを改善するだけでも性能が上がっています。citeturn24view0turn25academia31turn26view0

これはSystem Bにかなり強い実証的追い風です。

ただし、model/feature diversityだけでは、

> **population全員が同じ誤ったvalidation worldを信じる**

問題を解決しません。

したがって最も興味深い比較は、

> **solution-space QD vs epistemic-space QD vs explicit Bayesian epistemic layer**

です。

### Active Inferenceを採用する必然性はあるか

**ありません。**

Active Inferenceの、

- belief state
- generative model
- preferred outcome
- uncertainty
- epistemic/pragmatic value
- active experiment
- belief update

という概念対応は本研究に非常に有用です。citeturn28search6turn28search0

しかしKaggle experiment selectionについてはBEDがより直接的で、Expected Information Gainをそのまま使えます。citeturn28search1turn28search8

したがって、

> **Active Inferenceを研究の言語・着想として使う。  
> 実装はBayesian Experimental Design + QD + falsificationで行う。**

のが最も合理的です。

Expected Free Energyを厳密実装すること自体には、現段階で独立した実用メリットを見いだせません。

### 実装するなら最小構成は何か

私は最初から大規模multi-agent cognitive architectureを作りません。

最小の**C-lite**は、

```text
1. Strong Evolution/QD search
2. Multiple candidate validation worlds
3. Explicit hypothesis registry
4. Probability/confidence on important hypotheses
5. Pre-registered discriminating predictions for experiments
6. EIG or EVSI-based diagnostic experiment selection
7. Independent falsifier
8. OOF residual/error diversity archive
9. Meta-controller allocating compute between exploit/explore/epistemic
```

です。

つまり現在のEvolutionary Multi-Agentに、

> **「何が分かっていないか」を機械可読にする小さなlayer**

を追加します。

それでBに勝てなければ、Full Active Inferenceへ進む理由はほぼありません。

### 最も効率よく反証できる過去competitionは何か

**低コストpilotならRossmann。強い本番反証ならIEEE-CIS Fraud Detectionです。**

RossmannはWinner自身がreliable holdoutを主要洞察として挙げているため、Cがvalidation researchへbudgetを使う価値を安く確認できます。citeturn7search5

IEEE-CISではvalidation、time shift、entity、seen/unseen client、adversarial validationという複数のepistemic issueが同時に存在し、BとCの差を出しやすい。citeturn18search0turn5search12turn18search5

ただし最終主張には最低でも異なる3〜4 modalitiesを使うべきです。

### A/B/C比較の本質

この研究で見るべきなのは、

> Cは「賢そうな研究ノート」を作れるか

ではありません。

見るべき因果chainは、

\[
Epistemic\ experiment
\rightarrow
better\ belief
\rightarrow
better\ validation/model\ decision
\rightarrow
higher\ Private\ performance
\]

です。

このchainの最後まで到達しなければ失敗です。

特に、

\[
\text{Discovery Rate}\_C >
\text{Discovery Rate}\_B
\]

でも

\[
\text{Private}\_C
\le
\text{Private}\_B
\]

なら、Kaggle攻略という目的に対してCは支持されません。

### 最大の弱点・失敗条件

最大の弱点は**Winner corpusを使うことそのもの**です。

第一に、**survivorship/hindsight bias**があります。Winnerは最終的に重要だった実験を語り、無数の無意味なexperimentを書きません。そのため「Winnerがvalidationを研究した」からといって、「validation研究をrewardすれば勝率が上がる」とは限りません。

第二に、**meta-overfitting**があります。

50 competitionのwinnerからPreferred Stateを作ると、agentは

> Kaggleでよくある物語を当てる

能力を身につけるかもしれません。

しかし新competitionの本当のDGPを理解しているわけではない。

これはSantanderのmagicやIEEE-CIS UIDのような有名patternで特に危険です。citeturn19search0turn5search12

第三に、**LLM contamination**があります。MLE-benchもこれを明示的な評価問題として扱っています。citeturn24view0

したがってhistorical benchmarkでは、

- competition名を削除
- column名をhash/rename
- prose descriptionを意味保持したままobfuscate
- winner-specific vocabularyを除去
- web access禁止
- winner solutionをprompt/memoryから完全排除

したvariantも必ず実行します。

さらにPreferred State学習は、

> leave-one-competition-out

だけでなく、

> **leave-one-domain-out**

で行うべきです。

第四に、**Information Gain Goodhart**があります。

Agentが

> 「私はH1かH2か分からない」

と自分でuncertaintyを作り、

> 「実験でH1だと確信した」

としてentropyを大きく減らせば、形式上IGを稼げます。

したがってLLM belief movement自体をrewardしてはいけません。

必要なのは、

> **calibrated predictive belief**

です。

実験前に予測distributionを固定し、実際の結果に対するlog score/Brier scoreを測るべきです。

第五に、**Private leaderboardさえ絶対的ground truthではありません。** M5のようにevaluation setupそのものの安定性が問題になるcompetitionも存在します。citeturn14academia25

最終的にはPrivate LBだけでなく、

- multiple pseudo-future backtests
- robustness
- final private performance

を併用する必要があります。

第六に、そして最も単純な失敗条件は、

> **Epistemic Layerのoverheadが大きすぎる**

ことです。

System Cが20%のexperimentをvalidationやfalsificationに使っている間に、System Bが20個多くhigh-quality solutionを試せるなら、Bが勝つ可能性は十分あります。

これは失敗ではなく非常に重要な結果です。

### 最終的な研究判断

現時点の証拠から、私は次の研究agendaを最も合理的だと判断します。

**Active Inferenceそのものを実装する研究は優先しません。**

代わりに、

\[
\boxed{
\text{Evolution/QD}

- \text{Explicit Hypotheses}
- \text{Validation Uncertainty}
- \text{Information Value}
- \text{Falsification}
- \text{Belief Update}
  }
  \]

という最小構成を作ります。

この構成はActive Inferenceの重要な直観を保持しつつ、BED、QD、scientific falsificationというより直接的で検証可能な理論に分解できます。Active Inferenceはepistemic/pragmatic valueを同一policy selection内で扱う有力な概念的出発点ですが、Kaggleにおけるその価値は**Expected Free Energyという形式ではなく、「utility improvementとは別にbelief improvementを行動価値として扱う」という部分**にあります。citeturn28search0turn28search6turn28search1

そして、この研究の最も重要な実験はSystem Aを倒すことではありません。現代の自律ML research agentではsearch/diversityだけでも既に大きな改善が確認されているため、citeturn24view0turn25academia31turn26view0 本当に意味があるのは、

\[
\boxed{
C > \text{strong Evolutionary/QD B}
}
\]

を示せるかどうかです。

それが示せなければ、結論は明確です。

> **「Kaggleで勝つための未知の勝ち筋」を発見するのに、明示的なActive-Inference-inspired Epistemic Layerは必要なかった。強いEvolutionary/Quality-Diversity searchで十分だった。**

逆にCが同一budget下で、

- validation fidelityを早く改善し、
- critical discoveryを高率で再発見し、
- CV→Private correlationを高め、
- その結果として最終Private performanceでBを再現性を持って上回る

なら初めて、

> **Kaggle自動研究では「solutionを探索するpopulation」に加えて、「どの世界理解が正しいかを探索するpopulation」が必要である**

という中心仮説に実証的根拠が生まれます。

これが、この研究アイデアに対して最も厳しく、かつ最も情報量の多い検証方法です。
