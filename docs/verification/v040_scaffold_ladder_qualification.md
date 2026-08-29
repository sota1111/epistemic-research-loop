# v0.4.0 Track A Side-probe — Opus + Sol Scaffold-ladder Screen (Stage 1)

## 結論

opus・sol に P1(baseline)/ P2(仮説列挙強制)/ P3(新規:昇格前の自己批判)を交差させた
24 run(6 構成 × 4 replicate)の結果:

- **P3(自己批判)は opus の仮説多様性を再現性高く約 3 倍に押し上げた。**
  mean semantic_family_count:P1 3.00 / P2 3.00 / **P3 8.75**。この効果は 4 replicate
  すべてで一貫していた(12・6・9・8 家族)——単発の外れ値ではなく、**scaffold 単独の
  再現性ある効果**である。false promotion は 0 のまま(多様性が増えても暴走はしていない)。
- **claude 側で初めて persistent 系(L1/L4)が真に発見された。** opus×P1 が
  `persistent_clear` と `persistent_compositional` を同一 suite(c01)で同時発見、
  opus×P3 が `persistent_noisy_proxy` を発見(c03)。gen1・sol ablation の低 effort 帯を
  通じて claude 側の persistent L1/L2 発見は皆無だったが、ここで初めて割れた。
- **P2 は opus にとって逆効果だった。** 発見イベント P1(9)= P3(9)> **P2(7)**。fable では
  P1→P2 で 2.5 倍の効果があったが、**opus では効果が出ない、むしろ僅かに下がる。scaffold の
  効果はモデル依存であり、汎用的なレバーではない**——事前登録した 3 通りの予測のうち
  「(b) モデル依存」が支持された。
- **sol×P3 で false promotion 7 件が発生したが、全て単一 suite(c04)に集中**しており、
  他の 3 replicate は健全だった(gen1 の terra/g03、sol ablation の high/b05 と同型の
  単発の暴走)。P3 が sol の calibration を系統的に悪化させるとは言えない。

## 実行記録

- 6 構成(opus×{P1,P2,P3}、sol×{P1,P2,P3}、sol は reasoning effort=xhigh 固定)× 4 replicate
  = 24 run。新 Suite(`v040-scaf-c01..c04`、master seed 20260920)。
- 1 run(`v040-scaf-c02/agent-01-s42` = opus×P2)が終端 resolution 自己整合性契約違反
  (falsified 申告なのに 2 Context で自分の null 95th percentile を超える research gain を
  報告)で 3 回の repair 後も失敗。**インフラ障害ではなく正当な契約 reject。** バッチの
  resumable 設計どおり再実行し、2 回目で契約 Pass。
- 盲検監査:view 24・transcript 43 とも findings 0。24 run 全て Lock → SHA 再照合 → 開封。
  評価器は `expected_suite_count=4` を明示指定(v0.3.7/8/9・gen1 は無変更)。
- failure_stage の内訳:evidence 91・matched_negative 6・promotion 21。

## 構成別結果

| 構成 | 発見イベント | 発見 family | False promotion | mean semantic family | mean effective family | mean eecr |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| **L-opus-P1** | **9** | grammar_a/b, **persistent_clear**, **persistent_compositional** | 0 | 3.00 | 2.55 | 0.22 |
| L-opus-P2 | 7 | grammar_a/b | 0 | 3.00 | 2.54 | 0.31 |
| **L-opus-P3** | **9** | grammar_a/b, **persistent_noisy_proxy** | 0 | **8.75** | **4.37** | 0.23 |
| L-sol-P1 | 3 | grammar_a/b | 0 | 1.00 | 1.00 | 0.25 |
| L-sol-P2 | 4 | grammar_a/b | 0 | 1.75 | 1.75 | 0.38 |
| L-sol-P3 | 5 | grammar_a/b, persistent_clear | 7(1 suite 集中) | 1.25 | 1.19 | 0.29 |

## persistent 発見の詳細(単発か再現性ありか)

| 構成 | family | 発見した suite | 他 3 replicate |
| --- | --- | --- | --- |
| L-opus-P1 | persistent_clear + persistent_compositional | c01(同時発見) | c02 falsified、c03 inconclusive、c04 過大申告(discovered=False) |
| L-opus-P3 | persistent_noisy_proxy | c03 | c01/c02/c04 は falsified/inconclusive |
| L-sol-P3 | persistent_clear | (ablation 側の別 suite。本 screen 内では計上のみ) | — |

**persistent 系の発見は依然として単発(4 replicate 中 1 つ)に留まる。** ただし sol
ablation(high/xhigh)と本 screen(opus×P1/P3)を合わせると、**低 effort・P2 以外の条件で
複数の異なる経路から persistent 系が割れ始めている**——単一の魔法の設定があるのではなく、
「evidentiary capacity に余裕がある条件(高 effort、または P1/P3 のような素朴〜自己批判的な
scaffold)」で確率的に発見されやすくなっている、と読むのが妥当。

## 判定

- **事前登録した 3 通りの予測のうち「(b) scaffold 効果はモデル依存」が支持された。**
  P2 は fable を助けたが opus は助けなかった。P3 は opus の多様性を大きく押し上げたが、
  sol では diversity 面の効果は乏しく(1.00→1.25 と小さい)、false promotion リスクだけが
  目立った。**scaffold は万能の代替レバーではなく、モデルごとに効く組み合わせが違う。**
- **P3(自己批判)は opus にとって最も有望な単一変更。** 発見イベント数は P1 と同点最高、
  多様性指標は圧倒的に最高、false promotion は 0。次段階での重点候補。
- **次の作業(Stage 2 として起動):** opus×P1・opus×P3・sol×xhigh(既に判明済み最良 effort)を
  policy §3.2 の推奨 replicate(6)で新 Suite に対して再現確認する。特に (a) opus×P3 の
  多様性ブーストが 6 replicate でも再現するか、(b) sol×P3 の false promotion が単発か
  繰り返すか、(c) persistent 系発見が偶然か構造的傾向かを見る。

## 正本

- [Preregistration](../v040_scaffold_ladder_preregistration.json)
- [Selection Table](../v040_scaffold_ladder_selection.json) /
  [Diagnostics](../v040_scaffold_ladder_diagnostics.json)
- [新規プロンプト P3](../../prompts/generic_research_agent/v040_p3.md)
- [v0.4.0 方針](../c_lite_v040_policy.md)
