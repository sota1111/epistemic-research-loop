# Holdout policy

`strict_blind` permits no research-time query. Paths and scores are evaluator-only, final scores are
AES-GCM encrypted, and all paired runs must finish before unseal. `gated_binary` returns only whether
a preregistered threshold was met, enforces a query budget, and records each query. `open_debug` is
rejected when a gate is created in production mode.

Numeric score requests in gated mode, any strict-blind query, query-budget overflow, credential/API
access by a worker, or publication before unseal is a blocking violation.

The internal sealed holdout and the Kaggle public leaderboard are separate channels with separate
budgets. See [leaderboard policy](leaderboard_policy.md) for the second one.
