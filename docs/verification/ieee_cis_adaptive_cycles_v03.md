# IEEE-CIS v0.3 adaptive multi-agent Cycle 2--4 verification

## Scope and conclusion

This record extends the first no-role v0.3 run by three adaptive exploration cycles per agent.
Cycle 3 was not designed until each agent received its own Cycle 2 evidence, and Cycle 4 was not
designed until it received its own Cycle 3 evidence.  No agent received another agent's proposal,
score, posterior, candidate, or global best.

All nine Heavy experiments completed sequentially and produced valid OOF and full-test candidate
artifacts.  The agents generated nine distinct semantic signatures and no semantic duplicate, but
the nine-candidate residual covariance effective rank was only `1.107745`.  More cycles therefore
increased the number of investigated explanations without creating comparable prediction-error
diversity or satisfying the IEEE-CIS acceptance contract.

No leaderboard, Hidden/Private label, winner code, or winner write-up was queried.  This is a local
forward-validation and control-plane result, not evidence of primary-endpoint improvement.

## Isolation and adaptive protocol

The three generic branches continued from the same IEEE-CIS base
`ac3b46975e5da64570fb79d6e1141bc5c7525d0f`:

| Agent | Cycle 2 commit | Cycle 3 commit | Cycle 4 commit |
| --- | --- | --- | --- |
| island 01 | `d255b803fe40b0d91927eecef95138eeab743275` | `7ac3042cb76ce395cbe51ba596a8f217e8ca3d3f` | `22108ff80d9bbe6e35620006a23fd55ac33e269e` |
| island 02 | `30934412508604424398c92e134e8aeffc9637f2` | `a6d9816d0c89ecc71a4236986041b775407eb489` | `452b4bf5e232668029cbfd6f52175bb54e88ba46` |
| island 03 | `ee8359440ffc4a4cc1db3635b2ec859a8bbd76a3` | `8859a6a0792e1fd2058f38210eabc1d09d0068ca` | `83434291ab64a636c3257239c2e2905ae9a5a8d7` |

Island 01 also made the infrastructure-only manifest fix
`cd13aab9a4445353f4f951d1c3107bad0627bba4`.  It changed no hypothesis, feature, model, or decision.
The Controller rejected the incomplete structural-alternative schema before execution, so this
attempt consumed no Heavy compute and produced no belief update.

After execution, formatting-only commits `fb73b29df24bcfd081db5e0ada3a0e0095addbe3`,
`e20fc602e7388e83f09ed493e1f04d1d19cd4af4`, and
`283b1c29af7494f829aae400a453961dfeeebc52` made the three final branch heads pass the same format
gate without changing runtime behavior or recorded candidate commits.

Every Heavy run used the common override of 80,000 train rows, 80 estimators, and two threads.
Agent code development and lightweight tests could run concurrently; candidate execution could
not.  Every probe for another Heavy reservation while one was running was rejected.

## Agent-local decision traces

The AUC values below are each agent's own forward folds.  They are used only for within-agent paired
decisions and must not be interpreted as a cross-agent ranking.

| Agent / Cycle | Self-selected experiment | Local result and bound decision |
| --- | --- | --- |
| 01 / 2 | nested amount-microstructure ablation | candidate `0.872216`; control `0.868257`; delta `+0.003960`, positive 3/3: retain encoding, continue discrimination |
| 01 / 3 | five ProductCD/time/amount-matched residue nulls | real-null `+0.000929`, positive 2/3, but real did not exceed null 95% point: no structure support |
| 01 / 4 | aggregate-missingness nested ablation | candidate `0.872216`; control `0.868867`; delta `+0.003349`, positive 3/3: retain encoding-only candidate |
| 02 / 2 | fold-safe nominal code and token frequency | `0.878204`, paired Cycle 1 gain `+0.005366`: retain Cycle 2 |
| 02 / 3 | frequency-only ablation | `0.877061`, Cycle 2 delta `-0.001143`, positive 1/3: reject and return to Cycle 2 |
| 02 / 4 | Cycle 2 parent plus D-anchor consensus | `0.875308`, Cycle 2 delta `-0.002896`: reject and retain Cycle 2 |
| 03 / 2 | reliability-shrunk context statistics | `0.886104`, Cycle 1 gain `+0.003235`, positive 3/3: retain Cycle 2 |
| 03 / 3 | median/IQR residual and context-tail features | `0.883267`, Cycle 2 delta `-0.002837`, worst `-0.012130`: reject |
| 03 / 4 | Cycle 2 parent plus row missingness summaries | `0.883688`, Cycle 2 delta `-0.002416`, positive 0/3: reject |

The final agent-local selections were island 01 Cycle 4, island 02 Cycle 2, and island 03 Cycle 2.
Island 01 Cycle 2--4 produced identical final predictions: its later experiments isolated feature or
null effects but did not create a new predictive candidate direction.

## Structure maturation result

Island 01's amount-process hypothesis remained the only structural hypothesis.  Cycle 2 confirmed
encoding utility.  Cycle 3 then tested a confounder-preserving null rather than tuning the same
model, but only five null repetitions were run and the real gain did not exceed their 95% point.
The required 20-null Gate and the remaining independent implication, replication, and adoption
requirements were not met.

The correct terminal interpretation is therefore
`USEFUL_ENCODING_UNVALIDATED_STRUCTURE`.  It is not a validated payment process, payment rail, UID,
or behavioral client proxy; its Validation Debt remains open and it is not shareable as confirmed
structure.  Cycle 4 deliberately returned to an encoding-only ablation instead of preserving the
unvalidated story.

## Reliability, diversity, and final selection

| Measure | Result |
| --- | ---: |
| Candidate experiments | 9 |
| Completed / valid Artifact Contract | 9 / 9 |
| OOF artifacts | 9 / 9 |
| Full 506,691-row test predictions | 9 / 9 |
| Resource failures | 0 |
| Sum of candidate wall time | `225.692 s` |
| Semantic clusters | 9 |
| Semantic duplicate rate | `0` |
| Mean / maximum semantic similarity | `0.213580` / `0.527778` |
| Collective collapse | false in Cycles 2--4 |
| Nine-candidate OOF effective rank | `1.107745` |

QD occupancy stopped increasing in Cycles 3 and 4, but this was only one collapse symptom and did
not meet the two-condition/two-cycle rule.  On the 6,628 common honest OOF rows, selected-candidate
residual correlations were `0.975244` to `0.987667` and effective rank was `1.084152`.

The cross-fitted three-way blend had a positive MSE gain of `0.00003639`, but its common OOF AUC
`0.866356` was below island 01's `0.869652`.  Since IEEE-CIS uses AUC as the primary metric, the
meta-selector rejected the blend for final lock and selected island 01 Cycle 4.  The locked file has
506,691 rows and SHA-256
`a54764932987eeb58e42bce611bcd0096dc37198b87e636513bfe406fbaa4ee2`.  It was not submitted.

The common OOF comparison is a second-level intersection of agent-local honest folds, not a full
common first-level cross-fit.

## Acceptance boundary

The run now has nine valid OOF candidates, an evaluated ensemble, and a locked output.  Overall
`IEEERunAcceptance.passed` remains **false** because it still has:

- zero validated behavioral client proxies;
- zero fold-safe UID aggregate candidates;
- no Known/New client slice;
- only one listed model family, LightGBM.

Increasing cycles produced action-changing ablations and a failed structural null test, which is
real research progress.  It did not by itself reach the remaining top-pipeline capabilities or
Hidden/Private performance evidence.

## Reproduction and audit hashes

Each Cycle was run after its three proposals were committed:

```bash
for cycle in 2 3 4; do
  uv run python scripts/run_ieee_cis_multi_island_v03.py \
    --cycle "$cycle" --sample 80000 --estimators 80 --threads 2 \
    --output-name "v03-adaptive-cycle-0${cycle}" \
    --run-root ".runs/ieee-cis-v03-adaptive-cycle-0${cycle}-20260826"
done

uv run python scripts/finalize_ieee_cis_adaptive_cycles_v03.py
```

| File | SHA-256 |
| --- | --- |
| Cycle 2 report | `8f3dd701bbd1605c97f85ed605e2a1cd7e47e95caf592718e09e04161d69bbcc` |
| Cycle 3 report | `7d11c26ca6df772d43cf09714c4a51ddd9215bcc6e348da751a5fbfa24ba7dcb` |
| Cycle 4 report | `8db4aa3c712a4488b38513e0e25bc86d2f144d0e31a011b6649b56bf9a8a6723` |
| Final report | `bcad7f217aa17697d7750ad15d4bbfc800a2db31985799324b85fefab5e74b04` |
| Locked output | `a54764932987eeb58e42bce611bcd0096dc37198b87e636513bfe406fbaa4ee2` |

The superseded first finalization attempt is retained under
`.runs/ieee-cis-v03-adaptive-cycles-final-20260826-superseded-mse-lock/`.  It locked the positive-MSE-
gain blend before enforcing AUC as the primary selection metric; it is audit evidence, not a valid
final selection.
