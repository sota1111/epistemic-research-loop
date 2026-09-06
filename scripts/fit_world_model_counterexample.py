#!/usr/bin/env python3
"""決定性と必要性を分けて当てはめ、反例 `−1` を再現できるかを leave-one-domain-out で測る。

規則・決定規則・評価量・判定基準は docs/world_model/coding_rules_v2_counterexample.md に
事前登録済み(当てはめを一度も走らせる前に確定・commit)。**ここでは変更しない。**

一次版(scripts/fit_world_model.py)は変更しない。本スクリプトは同じ corpus・同じ
leave-one-domain-out・同じ seed を使い、モデルの形と決定規則だけを差し替える。
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CODING = ROOT / "docs" / "world_model" / "corpus_coding.json"
OUT = ROOT / "docs" / "world_model" / "world_model_counterexample.json"

K0 = 5  # 一次版と同じ shrinkage 係数(prior strength は low に固定)
BOOTSTRAP = 10000
SEED = 20260906
CTX_KEYS = ("temporal", "entity", "decomposable")
ALARM_BUDGET = 2.0  # 学習側で −1 と予測する数は、真の −1 数の 2 倍まで
FLOOR = 1e-6  # 対数損失が発散しないための下限


def cell(comp: dict[str, Any]) -> tuple[int, ...]:
    return tuple(comp["ctx"][key] for key in CTX_KEYS)


def _shrink(count: float, total: float, prior: float) -> float:
    return (count + K0 * prior) / (total + K0)


def fit_two_part(train: list[dict[str, Any]], states: list[str]) -> dict[str, Any]:
    """状態ごとに (決定性, 向き) を当てはめる。同じラベルの読み替えであり、再符号化ではない。"""
    model: dict[str, Any] = {}
    for state in states:
        labels = [comp["labels"].get(state, 0) for comp in train]
        mentioned = [label for label in labels if label != 0]
        # 全体側の事前は Laplace 加算 1(2 クラス)。
        global_mentioned = (len(mentioned) + 1) / (len(labels) + 2)
        global_minus = (sum(1 for label in mentioned if label == -1) + 1) / (len(mentioned) + 2)
        cells: dict[tuple[int, ...], dict[str, float]] = {}
        grouped: dict[tuple[int, ...], list[int]] = {}
        for comp in train:
            grouped.setdefault(cell(comp), []).append(comp["labels"].get(state, 0))
        for key, values in grouped.items():
            said = [value for value in values if value != 0]
            cells[key] = {
                "p_mentioned": _shrink(len(said), len(values), global_mentioned),
                # 向きは「言及されたセル」だけを分母にする。0 の多数は向きについて何も言わない。
                "p_minus": _shrink(sum(1 for value in said if value == -1), len(said), global_minus),
            }
        model[state] = {
            "global": {"p_mentioned": global_mentioned, "p_minus": global_minus},
            "cells": cells,
        }
    return model


def distribution(model: dict[str, Any], state: str, key: tuple[int, ...]) -> dict[int, float]:
    parameters = model[state]["cells"].get(key, model[state]["global"])
    mentioned = parameters["p_mentioned"]
    minus = parameters["p_minus"]
    return {1: mentioned * (1 - minus), -1: mentioned * minus, 0: 1 - mentioned}


def calibrate_threshold(model: dict[str, Any], train: list[dict[str, Any]], states: list[str]) -> float:
    """学習側だけで τ を決める。真の −1 数の ALARM_BUDGET 倍を超えない最小の τ。"""
    truth_minus = sum(1 for comp in train for state in states if comp["labels"].get(state, 0) == -1)
    if truth_minus == 0:
        return math.inf
    scores = sorted(
        (distribution(model, state, cell(comp))[-1] for comp in train for state in states),
        reverse=True,
    )
    budget = int(ALARM_BUDGET * truth_minus)
    if budget >= len(scores):
        return 0.0
    # 上位 budget 件までを許す最小の閾値。同点は全部通るので、実際の発火数は budget を
    # 上回りうる —— そのときは同点の塊ごと落ちるところまで閾値を上げる。
    threshold = scores[budget]
    while threshold < math.inf and sum(1 for value in scores if value >= threshold) > budget:
        higher = [value for value in scores if value > threshold]
        if not higher:
            return math.inf
        threshold = min(higher)
    return threshold


def predict(model: dict[str, Any], state: str, key: tuple[int, ...], threshold: float) -> int:
    probabilities = distribution(model, state, key)
    if probabilities[-1] >= threshold:
        return -1
    if probabilities[1] >= 0.5:
        return 1
    return 0


def fit_primary(train: list[dict[str, Any]], states: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """一次版(coding_rules.md §5)の 3 値条件付き分布。比較対象として同じ fold で当てはめる。"""
    global_prior: dict[str, dict[int, float]] = {}
    conditional: dict[str, dict[tuple[int, ...], dict[int, float]]] = {}
    for state in states:
        values = [comp["labels"].get(state, 0) for comp in train]
        counts = Counter(values)
        prior = {value: (counts.get(value, 0) + 1) / (len(values) + 3) for value in (-1, 0, 1)}
        global_prior[state] = prior
        grouped: dict[tuple[int, ...], list[int]] = {}
        for comp in train:
            grouped.setdefault(cell(comp), []).append(comp["labels"].get(state, 0))
        conditional[state] = {
            key: {value: (Counter(group).get(value, 0) + K0 * prior[value]) / (len(group) + K0) for value in (-1, 0, 1)}
            for key, group in grouped.items()
        }
    return global_prior, conditional


def _log_loss(probabilities: dict[int, float], truth: int) -> float:
    total = sum(probabilities.values())
    return -math.log(max(probabilities[truth] / total, FLOOR))


def main() -> None:
    data = json.loads(CODING.read_text())
    comps: list[dict[str, Any]] = data["competitions"]
    states: list[str] = data["_states"]
    domains = sorted({comp["domain"] for comp in comps})

    rows: list[dict[str, Any]] = []
    thresholds: dict[str, float] = {}
    for domain in domains:
        train = [comp for comp in comps if comp["domain"] != domain]
        held = [comp for comp in comps if comp["domain"] == domain]
        two_part = fit_two_part(train, states)
        threshold = calibrate_threshold(two_part, train, states)
        thresholds[domain] = threshold
        prior, conditional = fit_primary(train, states)
        checklist = {state: max(prior[state], key=lambda value: prior[state][value]) for state in states}
        for comp in held:
            key = cell(comp)
            truth = {state: comp["labels"].get(state, 0) for state in states}
            primary = {}
            for state in states:
                distribution_primary = conditional[state].get(key, prior[state])
                primary[state] = max(distribution_primary, key=lambda value: distribution_primary[value])
            rows.append(
                {
                    "name": comp["name"],
                    "domain": domain,
                    "truth": truth,
                    "checklist": checklist,
                    "primary": primary,
                    "two_part": {state: predict(two_part, state, key, threshold) for state in states},
                    "loss_checklist": sum(_log_loss(prior[state], truth[state]) for state in states),
                    "loss_primary": sum(
                        _log_loss(conditional[state].get(key, prior[state]), truth[state]) for state in states
                    ),
                    "loss_two_part": sum(
                        _log_loss(distribution(two_part, state, key), truth[state]) for state in states
                    ),
                }
            )

    count = len(rows)
    cells_total = count * len(states)

    def accuracy(name: str) -> float:
        return sum(sum(row[name][state] == row["truth"][state] for state in states) for row in rows) / cells_total

    def recall(name: str, value: int) -> tuple[int, int]:
        hit = sum(
            sum(1 for state in states if row["truth"][state] == value and row[name][state] == value) for row in rows
        )
        total = sum(sum(1 for state in states if row["truth"][state] == value) for row in rows)
        return hit, total

    def fired(name: str, value: int) -> int:
        return sum(sum(1 for state in states if row[name][state] == value) for row in rows)

    def mean_loss(name: str) -> float:
        return sum(row[name] for row in rows) / cells_total

    rng = random.Random(SEED)
    accuracy_diffs: list[float] = []
    loss_diffs: list[float] = []
    for _ in range(BOOTSTRAP):
        sample = [rows[rng.randrange(count)] for _ in range(count)]
        cells_sample = len(sample) * len(states)
        accuracy_diffs.append(
            sum(
                sum(row["two_part"][state] == row["truth"][state] for state in states)
                - sum(row["primary"][state] == row["truth"][state] for state in states)
                for row in sample
            )
            / cells_sample
        )
        loss_diffs.append(sum(row["loss_two_part"] - row["loss_primary"] for row in sample) / cells_sample)
    accuracy_diffs.sort()
    loss_diffs.sort()
    accuracy_ci = (accuracy_diffs[int(0.025 * BOOTSTRAP)], accuracy_diffs[int(0.975 * BOOTSTRAP)])
    loss_ci = (loss_diffs[int(0.025 * BOOTSTRAP)], loss_diffs[int(0.975 * BOOTSTRAP)])

    minus_hit, minus_total = recall("two_part", -1)
    minus_fired = fired("two_part", -1)
    plus_hit, plus_total = recall("two_part", 1)

    # 事前登録した判定(coding_rules_v2_counterexample.md §4)。
    reproduces = minus_hit >= 1
    accuracy_ok = accuracy_ci[0] >= -0.01
    adopted = reproduces and accuracy_ok

    accuracy_gap = accuracy("two_part") - accuracy("primary")
    loss_gap = mean_loss("loss_two_part") - mean_loss("loss_primary")
    print(f"leave-one-domain-out  n={count} コンペ x {len(states)} 状態 = {cells_total} セル")
    print(f"  チェックリスト        一致率 {accuracy('checklist'):.4f}  平均対数損失 {mean_loss('loss_checklist'):.4f}")
    print(f"  context 条件付け(一次) 一致率 {accuracy('primary'):.4f}  平均対数損失 {mean_loss('loss_primary'):.4f}")
    print(f"  2 部モデル(本追補)    一致率 {accuracy('two_part'):.4f}  平均対数損失 {mean_loss('loss_two_part'):.4f}")
    print(f"  一致率の差 (2 部 − 一次) {accuracy_gap:+.4f}  95% 区間 [{accuracy_ci[0]:+.4f}, {accuracy_ci[1]:+.4f}]")
    print(f"  対数損失の差 (2 部 − 一次) {loss_gap:+.4f}  95% 区間 [{loss_ci[0]:+.4f}, {loss_ci[1]:+.4f}]")
    print()
    print(f"  反例 −1 の再現   {minus_hit}/{minus_total}   (−1 と予測したセル {minus_fired} 件)")
    print(f"  決定的 +1 の再現 {plus_hit}/{plus_total}")
    primary_minus, primary_plus = recall("primary", -1)[0], recall("primary", 1)[0]
    print(f"  一次版の −1 再現 {primary_minus}/{minus_total}   +1 再現 {primary_plus}/{plus_total}")
    print("  τ(domain ごと、学習側だけで決定): " + ", ".join(f"{k}={v:.4f}" for k, v in thresholds.items()))
    print()
    print(f"  判定 (a) 反例を 1 件以上再現:            {'満たす' if reproduces else '**満たさない**'}")
    print(f"  判定 (b) 一致率の区間下限 >= -0.01:      {'満たす' if accuracy_ok else '**満たさない**'}")
    print(f"  => 点予測形式として{'採用' if adopted else '**不採用**(分布形式で反例を保つ)'}")

    full = fit_two_part(comps, states)
    full_threshold = calibrate_threshold(full, comps, states)
    OUT.write_text(
        json.dumps(
            {
                "_rules": "docs/world_model/coding_rules_v2_counterexample.md",
                "_primary": "docs/world_model/world_model.json (coding_rules.md, unchanged)",
                "_coder_note": (
                    "single coder; inter-coder agreement UNMEASURED. Do not wire into Preferred State defaults."
                ),
                "_context_keys": list(CTX_KEYS),
                "_shrinkage_k0": K0,
                "_decision_rule": {
                    "predict_minus_when": "P(-1) >= tau",
                    "tau_full_corpus": full_threshold,
                    "tau_per_held_out_domain": thresholds,
                    "alarm_budget_multiple": ALARM_BUDGET,
                },
                "validation": {
                    "protocol": "leave-one-domain-out",
                    "n_competitions": count,
                    "checklist_accuracy": round(accuracy("checklist"), 4),
                    "primary_accuracy": round(accuracy("primary"), 4),
                    "two_part_accuracy": round(accuracy("two_part"), 4),
                    "accuracy_difference_vs_primary": round(accuracy_gap, 4),
                    "accuracy_ci95": [round(value, 4) for value in accuracy_ci],
                    "mean_log_loss": {
                        "checklist": round(mean_loss("loss_checklist"), 4),
                        "primary": round(mean_loss("loss_primary"), 4),
                        "two_part": round(mean_loss("loss_two_part"), 4),
                    },
                    "log_loss_difference_vs_primary": round(loss_gap, 4),
                    "log_loss_ci95": [round(value, 4) for value in loss_ci],
                    "counterexample_recall": [minus_hit, minus_total],
                    "counterexample_predictions": minus_fired,
                    "decisive_recall": [plus_hit, plus_total],
                    "primary_counterexample_recall": [primary_minus, minus_total],
                    "primary_decisive_recall": [primary_plus, plus_total],
                    "criterion_a_reproduces_counterexample": reproduces,
                    "criterion_b_accuracy_within_tolerance": accuracy_ok,
                    "adopted_as_point_predictor": adopted,
                },
                # 判定がどちらでも、出力は分布として P(-1) を持つ。点予測が −1 を出せなくても
                # 「この状態は逆に働きうる」が読む側に見える(追補 §4)。
                "unobserved_states": [
                    state for state in states if all(comp["labels"].get(state, 0) == 0 for comp in comps)
                ],
                "states": {
                    state: {
                        # 観測数を並べて置く。観測 0 の状態にも縮約は数値を返すので、
                        # それが証拠ではなく事前分布であることが読む側に見えていないといけない。
                        "observed": {
                            "decisive": sum(1 for comp in comps if comp["labels"].get(state, 0) == 1),
                            "counterexample": sum(1 for comp in comps if comp["labels"].get(state, 0) == -1),
                            "competitions": len(comps),
                        },
                        "global": {
                            "p_mentioned": round(full[state]["global"]["p_mentioned"], 4),
                            "p_minus": round(full[state]["global"]["p_minus"], 4),
                        },
                        "cells": {
                            ",".join(map(str, key)): {
                                "p_mentioned": round(values["p_mentioned"], 4),
                                "p_minus": round(values["p_minus"], 4),
                                "p_counterexample": round(values["p_mentioned"] * values["p_minus"], 4),
                            }
                            for key, values in sorted(full[state]["cells"].items())
                        },
                    }
                    for state in states
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
