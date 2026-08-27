# v0.3.6 Blindness Contract

Primary real-agent runでは、Agentは割り当てられた`agent_views/<agent-id>`と自分の`agent_outputs/<agent-id>`だけを研究判断に使用する。

Agent-visible:

- Opaque Pack/Context ID
- 匿名化・Agent別Permutation済みSchema
- Label付きResearch rows
- LabelなしSealed rows
- Metric、Prompt、Artifact Contract

Controller-only:

- Family、Polarity、Generator Seed
- Canonical/Visible列対応
- Sealed Label
- Intervention Truth
- Oracle Prediction/Reference Probe

Truth ManifestはFernet暗号化し、鍵はAgent tree外へ置く。IDはSecret-keyed HMAC、Generator/Sampling/Null/Model Seedは分離する。Agent-visible treeにFamily/Polarity/Truth token、`.enc`、`.key`がないことを実行前に監査する。

共有Host上ではOS mount namespaceによる強制隔離ではなく、Agentへの明示的Path PolicyとContent/Path auditを用いる。この制約は最終Reportに残し、Kernel-level isolationと同等とは主張しない。

Primaryに含めるRunはHuman hypothesis/code/operator/candidate assistanceを0とする。Generic Artifact Validator Messageだけを許可する。
