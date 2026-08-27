# v0.3.4 System B Policy — Strong QD

System BはPerformance Archive、Semantic/Implementation Descriptor、OOF Error Archive、Candidate Population、
Mutation Historyを持つ。AgentはLocal Performance、Semantic Novelty、Representation/Model Coverage、
Robustness、OOF Error Diversity、Archive Contributionで次Experimentを選ぶ。

明示的Hypothesis Registry、Posterior、Competing Explanation、Predictive Slice Preregistration、EVSI、
Structure Maturation、Falsifier、Validation Debt、Belief Updateは使用しない。CostとResourceはUtility、
Selection、Acceptanceへ入れない。AgentはGenericで、固定Nicheや特定Feature/Model指示を受けない。

全CycleでBase Artifact、Parent/Challenger Lock、Global Validation Constraintを満たす。Final Selectionは
全Arm共通のstrict-forward cross-fitとsealed selectorで行う。
