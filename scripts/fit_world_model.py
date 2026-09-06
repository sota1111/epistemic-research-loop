#!/usr/bin/env python3
"""38 コンペ corpus から Preferred State の決定性事前分布を当てはめ、
leave-one-domain-out で「context 条件付け」対「context 無視のチェックリスト」を比較する。

規則・判定基準は docs/world_model/coding_rules.md に事前登録済み。**ここでは変更しない。**
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODING = ROOT / "docs" / "world_model" / "corpus_coding.json"
OUT = ROOT / "docs" / "world_model" / "world_model.json"

K0 = 5  # 事前登録した shrinkage 係数(prior strength を low に固定するため)
BOOTSTRAP = 10000
SEED = 20260906
CTX_KEYS = ("temporal", "entity", "decomposable")


def cell(comp) -> tuple[int, ...]:
    return tuple(comp["ctx"][k] for k in CTX_KEYS)


def dist(values, prior, k0=K0):
    """{-1,0,1} 上の分布。prior へ向けて k0 で縮約する。"""
    c = Counter(values)
    n = len(values)
    return {v: (c.get(v, 0) + k0 * prior[v]) / (n + k0) for v in (-1, 0, 1)}


def fit(train, states):
    global_prior, conditional = {}, {}
    for s in states:
        vals = [c["labels"].get(s, 0) for c in train]
        cc = Counter(vals)
        gp = {v: (cc.get(v, 0) + 1) / (len(vals) + 3) for v in (-1, 0, 1)}  # Laplace
        global_prior[s] = gp
        by_cell: dict[tuple[int, ...], list[int]] = {}
        for c in train:
            by_cell.setdefault(cell(c), []).append(c["labels"].get(s, 0))
        conditional[s] = {k: dist(v, gp) for k, v in by_cell.items()}
    return global_prior, conditional


def predict_checklist(global_prior, states):
    """context を無視した多数決 = winner チェックリスト。"""
    return {s: max(global_prior[s], key=global_prior[s].get) for s in states}


def predict_context(global_prior, conditional, states, comp):
    out = {}
    for s in states:
        d = conditional[s].get(cell(comp), global_prior[s])
        out[s] = max(d, key=d.get)
    return out


def main() -> None:
    data = json.loads(CODING.read_text())
    comps, states = data["competitions"], data["_states"]
    domains = sorted({c["domain"] for c in comps})

    per_comp = []  # (name, domain, checklist 一致数, context 一致数, 状態数)
    for dom in domains:
        train = [c for c in comps if c["domain"] != dom]
        test = [c for c in comps if c["domain"] == dom]
        gp, cond = fit(train, states)
        chk = predict_checklist(gp, states)
        for c in test:
            truth = {s: c["labels"].get(s, 0) for s in states}
            ctx = predict_context(gp, cond, states, c)
            per_comp.append(
                (
                    c["name"],
                    dom,
                    sum(chk[s] == truth[s] for s in states),
                    sum(ctx[s] == truth[s] for s in states),
                    len(states),
                )
            )

    n = len(per_comp)
    acc_chk = sum(r[2] for r in per_comp) / (n * len(states))
    acc_ctx = sum(r[3] for r in per_comp) / (n * len(states))

    rng = random.Random(SEED)
    diffs = []
    for _ in range(BOOTSTRAP):
        sample = [per_comp[rng.randrange(n)] for _ in range(n)]
        diffs.append((sum(r[3] for r in sample) - sum(r[2] for r in sample)) / (len(sample) * len(states)))
    diffs.sort()
    lo, hi = diffs[int(0.025 * BOOTSTRAP)], diffs[int(0.975 * BOOTSTRAP)]

    separable = lo > 0 or hi < 0
    verdict = (
        "context 条件付けが優る"
        if lo > 0
        else "チェックリストが優る"
        if hi < 0
        else "**差は検出できなかった**(区間が 0 をまたぐ)"
    )

    print(f"leave-one-domain-out  n={n} コンペ x {len(states)} 状態")
    print(f"  チェックリスト(context 無視)  一致率 {acc_chk:.4f}")
    print(f"  context 条件付け              一致率 {acc_ctx:.4f}")
    print(f"  差 {acc_ctx - acc_chk:+.4f}   95% 区間 [{lo:+.4f}, {hi:+.4f}]")
    print(f"  判定: {verdict}")
    print()
    print("domain 別(context 条件付けの一致率):")
    for dom in domains:
        rows = [r for r in per_comp if r[1] == dom]
        a = sum(r[3] for r in rows) / (len(rows) * len(states))
        b = sum(r[2] for r in rows) / (len(rows) * len(states))
        print(f"  {dom:12s} n={len(rows):2d}  context {a:.3f}  チェックリスト {b:.3f}  差 {a - b:+.3f}")

    gp_all, cond_all = fit(comps, states)
    OUT.write_text(
        json.dumps(
            {
                "_rules": "docs/world_model/coding_rules.md",
                "_coder_note": "single coder; inter-coder agreement UNMEASURED. Do not wire into Preferred State defaults.",
                "_context_keys": list(CTX_KEYS),
                "_shrinkage_k0": K0,
                "validation": {
                    "protocol": "leave-one-domain-out",
                    "n_competitions": n,
                    "checklist_accuracy": round(acc_chk, 4),
                    "context_accuracy": round(acc_ctx, 4),
                    "difference": round(acc_ctx - acc_chk, 4),
                    "ci95": [round(lo, 4), round(hi, 4)],
                    "separable": separable,
                    "verdict": verdict,
                },
                "unobservable_states": [s for s in states if all(c["labels"].get(s, 0) == 0 for c in comps)],
                "global_prior": {s: {str(k): round(v, 4) for k, v in gp_all[s].items()} for s in states},
                "conditional": {
                    s: {
                        ",".join(map(str, k)): {str(a): round(b, 4) for a, b in v.items()}
                        for k, v in cond_all[s].items()
                    }
                    for s in states
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"\n-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
