# v0.4.4-b クロスコンペ統合分析 — 全特徴量 sol reasoning-effort screening

**目的:** [10列制約インシデント記録](v044_ten_column_constraint_incident.md)を受けた
v0.4.4 の本体実験。IEEE-CIS(`v044-suite-a01`)・Santander(`v044-suite-b01`)双方で、
10列制約を撤廃した全特徴量設計(IEEE-CIS 106列・Santander 200列)+ ローカル疑似採点
ループを使い、v0.4.3-fと同じ8構成(sol・reasoning_effort×prompt_arm)の screening
ラウンドを実施した。詳細は[IEEE-CIS側](v044_full_feature_diversity_ieee_cis.md)・
[Santander側](v044_full_feature_diversity_santander.md)を参照。

## サマリ:10列制約下と全特徴量下の比較

| 指標 | 10列制約下(v0.4.3-f、全4ラウンド) | 全特徴量下(v0.4.4-b、screening) |
| --- | --- | --- |
| IEEE-CIS baseline超え成功率 | 不安定(0〜4/4のセルが混在、非単調) | **8/8構成全て成功** |
| Santander baseline超え成功率 | 不安定(0〜4/4のセルが混在、非単調) | **8/8構成全て成功** |
| IEEE-CIS AUC範囲 | 概ね0.5〜0.75 | **0.80〜0.84** |
| Santander AUC範囲 | 概ね0.5〜0.75 | **0.86〜0.89** |
| IEEE-CIS layer1一致 | 0/90+ run(全ラウンド累計) | **4/8 run(adversarial validation)** |
| Santander layer1一致(既存クラス) | 18中12件(67%、特徴独立性モデリング) | 8中5件(同クラス、水準は同程度) |
| reasoning effortとの関係 | 非単調・不安定 | ほぼ単調(特にSantander)・安定 |

## 発見(1、最重要):10列制約は「発見の質」だけでなく「実行の安定性」も損なっていた

v0.4.3-fで観測された「reasoning effortが非単調」「medium effortが谷になる」
「FSPR汚染が散発する」といった不安定なパターンの多くは、**列制約という根本的な
ボトルネックが引き起こしていた副次的な不安定性だった可能性が高い**。全特徴量下では
8構成×2コンペ=16 run全てが安定して baseline を上回り、reasoning effort との関係も
Santander側でほぼ単調になった。これは10列制約インシデントの影響が、当初想定していた
「発見できる技術クラスの範囲」だけでなく、実験全体の再現性・解釈可能性にも及んで
いたことを示す。

## 発見(2、コンペ間の非対称性——重要な反証):列数を増やす効果はコンペ依存

IEEE-CIS では、列数を増やしたことで **技術クラス#5(adversarial validation)への
到達が明確に「解放」**された——0件から4/8件へ。一方 Santander では、列数を増やした
ことで**生の性能は劇的に向上したが**(0.6台→0.89)、この競技の実際の公開解法が
使う核心技術(頻度/出現回数エンコーディング・real/synthetic行判定)には、200列全てを
見せても**一度も到達しなかった**。

**解釈:** 「列制約を外せば上位解法に近づく」という単純な仮説は、部分的にしか
支持されない。IEEE-CIS の場合は列不足そのものが発見を妨げていたが、Santander の
場合は列数以外の要因(仮説生成の方向性、あるいはこの競技特有の着眼点の難しさ)が
残っている。**今後の改善は「さらに列を増やす」ではなく、「なぜ特定の着眼点に
至らないのか」という別の問いに向かうべき**——例えば Santander の場合、値の
出現回数という発想自体が、匿名化された連続値特徴からは連想されにくいのかもしれない。

## 発見(3、コンペを跨いで再現した頑健なパターン):adversarial validation は
reasoning effortではなく prompt_arm(P3)に紐づく

**両コンペ・8/8 run で完全に同じパターン**が確認された:adversarial validation
(train/confirmation/transfer の分布シフトを判別器で検定する手法)は、**P3config
(自己批判・attack your own best approach)の run にのみ出現し(IEEE-CIS 4/4・
Santander 4/4)、P1configには一度も出現しなかった(0/8)**——reasoning effortの
高低とは無関係。これはコンペ2件・8 run という独立した繰り返しで完全に一致しており、
単なる偶然とは考えにくい。**「自己批判を促すプロンプト設計」が、特定の具体的な
検証技法(この場合はadversarial validation)を安定して誘発する**、という新しい
知見——今後の効果的な技術発見には、reasoning effort よりもプロンプト設計(自己批判
スキャフォールド)の方が強いレバーである可能性を示唆する。

## 発見(4):新しい技術クラス候補——正確重複行の既知ラベル照合(IEEE-CIS)

IEEE-CIS の 4/8 run で、confirmation/transfer領域の特徴ベクトルが research 領域の
行と完全一致する場合、既知ラベルで予測を補正するという手法が独立に発見された
(詳細:[IEEE-CIS側](v044_full_feature_diversity_ieee_cis.md)発見3)。UID復元
(layer1#1)そのものではないが構造的に近く、taxonomy拡張候補として記録する
——Santander側では観測されなかった(200列全て匿名の連続値であり、完全一致行が
IEEE-CISほど意味を持たない構造のため、と考えられる)。

## 追記(Round 2完了):adversarial validation はクロスコンペで完全確定した

`F4-xhigh-P1`(最良performer)・`F4-xhigh-P3`(adversarial validation候補)に
両コンペ・新規3 seedずつを追加した確認ラウンドが完了した。

**最終結果:**

1. **性能面:** IEEE-CIS・Santanderともに、両セルの新規6 run(計12 run/コンペ)
   全てが新しい独立行サンプルの reference baseline を上回った——合計24/24 run が
   確認ラウンドで成功。
2. **adversarial validation:** **IEEE-CIS 7/7 P3・0/7 P1、Santander 7/7 P3・
   0/7 P1——両コンペ合計 14/14 P3-arm run が示し、P1-arm run(14件)は1件も
   示さなかった。** screening のみの結果(8/8)から、v0.4.3-fの教訓(単一ラウンドの
   noveltyは信頼できない)に従って追加確認を行い、**完全にコンペ非依存・
   prompt_arm決定論的なパターンとして正式に確定した。**
3. **Santanderの実際の公開技術(頻度エンコーディング・real/synthetic行判定)は、
   確認ラウンドの6 runでも一度も出現しなかった**——「列数を増やすだけでは
   Santander固有の着眼点には到達しない」という発見2の結論も、確認ラウンドを
   経て維持された。

## 追記(Round 3完了):population拡大は「収束済みセルの精緻化」と「未到達技術の
発見」を区別する

`F4-xhigh-P3` に両コンペ新規4 seedずつ(このセル単体で各コンペ n=8)を追加した
population拡大ラウンドが完了した。

**最終結果:**

1. **IEEE-CIS:population拡大は新しい技術クラスを生まなかった。** 全4新規runが
   既存toolkit(adversarial validation・重複行照合等)の精緻化に留まった——
   v0.4.3-fの10列制約下では同じ操作が新規未分類パターンを生んだこととの対比が
   重要:**「populationを増やせば多様性が増える」のではなく、「まだ収束していない
   セルでのみpopulation拡大が多様性を増やす」**——既に強いアプローチに収束した
   セルでは、population拡大は精緻化しかもたらさない。
2. **Santander:population拡大は決定的な否定的結果をもたらした。** このセル単体
   n=8・Santander全体22 runを経ても、頻度エンコーディング・real/synthetic行判定
   という実際の公開技術には一度も到達しなかった——**列数不足でも population
   不足でもなく、仮説生成の方向性そのものの問題**であることが、2つの独立した
   「増やす」レバー(列数・population)を両方試した上で確定した。
3. **adversarial validation は両コンペ・全ラウンドを通じて完璧に再現し続けた**
   (IEEE-CIS 11/11・Santander 11/11、両方ともP3のみ)——本セッションで最も
   頑健かつ実用的な発見として確定。

**今後の方針:**

1. **「自己批判(P3)スキャフォールドは、reasoning effortよりも技術発見の
   確実な誘発因子である」という知見は、今回のセッションで最も頑健に確認された
   発見として、今後の全ラウンドの標準設計に反映すべきである。**
2. **多様性を求める際、population拡大は「セルが収束しているかどうか」を見極めた
   上で使うべきレバーである**——収束済みセルをさらに拡大しても新規性は生まれず、
   異なるprompt arm・異なる着眼点の導入(P1→P3の切り替えが今回まさにそれだった)
   の方が有効な場合がある。
3. Santanderの「頻度エンコーディング・real/synthetic行判定に到達しない」という
   発見は、列数・population のいずれを増やしても解決しないことが確定した。
   残るアプローチ(例:プロンプトで「値の出現頻度」という観点を明示的に示唆する)は
   既知解法のヒントを与えることになりblindness原則に抵触するため、今回の
   セッションではこれ以上追求しない。

## 正本

- [10列制約インシデント記録](v044_ten_column_constraint_incident.md)
- [IEEE-CIS側](v044_full_feature_diversity_ieee_cis.md) / [Santander側](v044_full_feature_diversity_santander.md)
- [c_lite_v044_policy.md](../c_lite_v044_policy.md)
