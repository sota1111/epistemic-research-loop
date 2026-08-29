# v0.4.0 Track A Side-probe — Cycle-budget Ablation (4 → 8)

## 結論

opus×P1・sol×P1×xhigh の `max_cycles_per_pack` を 4→8 に上げた 12 run(各 6 replicate、
cycle=4 baseline は既存 study を再利用)の結果、**事前登録した「capacity 仮説」は支持されず、
むしろ reasoning effort とは逆方向の効果が観測された:**

- **発見イベント数はほぼ変化しない。** opus:16/8replicate(cycle4)→ 11/6replicate(cycle8)=
  replicate 正規化後ほぼ同水準(2.0→1.83)。sol:7/6(cycle4)→ 8/6(cycle8)、僅かに増加も
  誤差範囲。**「cycle を増やせば発見が増える」という予測は支持されなかった。**
- **多様性指標(semantic_family_count)は両モデルとも明確に低下した。**
  opus:3.75(cycle4)→ **2.67**(cycle8)。sol:1.67(cycle4)→ **1.17**(cycle8)。
  これは reasoning effort ablation の結果(effort を上げるほど多様性も上がる)と**逆方向**——
  **cycle 数を増やすことは「広く探索する」ではなく「同じ仮説を深く詰める」方向に働く**らしい。
  evidentiary capacity という一つの概念でまとめられていた 2 つのレバー(reasoning effort・
  cycle 予算)が、実際には質的に異なる効果を持つことが分かった。
- **sol の false promotion が 1(cycle4 baseline)→ 4(cycle8)に悪化。** ただし 4 件全てが
  単一 suite(`e05`)に集中しており、gen1 の terra/g03・sol ablation の high/b05・Stage1 の
  sol×P3 と同型の**単発の暴走**。系統的な劣化と断定はできないが、cycle 予算を増やす場合は
  false promotion を注視すべきという警告材料にはなる。
- **`persistent_delayed_history` は opus×P1×cycle8 で 1/6 replicate 発見**(`persistent_clear`
  も別 replicate で発見)——Stage 2 の cycle=4 での発見率(1/6)と**同水準**。cycle を増やしても
  発見率が明確に底上げされたとは言えない。

## 実行記録

- 2 構成(opus×P1×cycle8・sol×P1×xhigh×cycle8)× 6 replicate = 12 run。新 Suite
  (`v040-cyc8-e01..e06`、master seed 20260929101)。cycle=4 baseline は再実行せず、
  既存 study(gen1 C3 + Stage1 L-opus-P1 の pooled 8 replicate、sol ablation S-xhigh の
  6 replicate)を読み込んで比較。
- **運用上のトラブル 2 件:**
  1. suite build スクリプトと `_CONFIG_REGISTRY` 登録を preregister 後に実行し忘れ、
     バッチが即座に全滅する事象が 2 回連続発生(scaffold-ladder Stage 2 に続き 2 度目)。
     再発防止のため `run_v040_agent.py` に registry 完全性の回帰テストを追加した。
  2. バッチの親プロセスが実行中に原因不明で終了(OOM の痕跡なし、メモリ使用量は正常範囲)。
     子プロセス 1 件(`e01/agent-01-s17`)は孤立したまま生存・完走。残り 1 件
     (`e06/agent-02-s17`)は個別に再実行して補完。データの欠落・重複はない。
- 盲検監査:view 12・transcript 21 とも findings 0。12 run 全て Lock 通過(契約 repair 不要)。

## 判定と v0.4.1 への含意

- **cycle 予算は evidentiary capacity レバーとして reasoning effort の代替にならない。**
  effort は「発見・多様性ともに増加」、cycle 予算は「発見横ばい・多様性低下・sol では
  false promotion 悪化のリスク」——**方向性が逆**。v0.4.1 では cycle=4 を既定のまま維持し、
  cycle=8 を積極的な推奨レバーとしない。
- **persistent_delayed_history は「evidentiary capacity を上げれば必ず解ける」壁ではない。**
  cycle を倍にしても発見率は変わらなかった。低確率事象という性質(replicate を重ねることで
  確率的に観測される)の方が実態に近い。
- **cycle 予算を増やすと「深さ」に振れ、多様性が犠牲になる**——これは新しい知見であり、
  「探索の広さ」と「1 つの仮説の掘り下げ」はトレードオフ関係にある可能性を示す。将来的に
  両方を独立に伸ばしたい場合は、cycle 予算を増やすと同時に multi-lineage を強制する scaffold
  的介入が必要かもしれない(未検証、v0.4.1 以降の課題)。

## 正本

- [Preregistration](../v040_cycle_budget_ablation_preregistration.json)
- [Selection Table](../v040_cycle8_selection.json) / [Diagnostics](../v040_cycle8_diagnostics.json)
- [累積発見台帳](../v040_discovery_ledger.md)(要更新)
