"""Per-task paired bootstrap comparisons and stratified means.

Repeated observations are averaged per task before comparison."""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass


@dataclass
class PairedComparison:
    metric: str
    arm_a: str
    arm_b: str
    n_tasks: int
    mean_a: float
    mean_b: float
    mean_delta: float            # b - a, positive = arm_b better
    ci_low: float                # bootstrap 95% CI of the delta
    ci_high: float
    win_rate_b: float            # fraction of tasks where b > a
    significant: bool            # CI excludes 0


def bootstrap_ci(values: list[float], iters: int = 10000,
                 alpha: float = 0.05, seed: int = 42) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = sorted(
        statistics.fmean(rng.choices(values, k=n)) for _ in range(iters)
    )
    lo = means[int((alpha / 2) * iters)]
    hi = means[int((1 - alpha / 2) * iters) - 1]
    return (round(lo, 4), round(hi, 4))


def paired_compare(
    per_task_a: dict[str, float],
    per_task_b: dict[str, float],
    metric: str, arm_a: str, arm_b: str,
) -> PairedComparison:
    """Inputs: task_id -> metric value (already averaged over repeats)."""
    common = sorted(set(per_task_a) & set(per_task_b))
    deltas = [per_task_b[t] - per_task_a[t] for t in common]
    a_vals = [per_task_a[t] for t in common]
    b_vals = [per_task_b[t] for t in common]
    lo, hi = bootstrap_ci(deltas)
    wins = sum(1 for d in deltas if d > 0)
    return PairedComparison(
        metric=metric, arm_a=arm_a, arm_b=arm_b, n_tasks=len(common),
        mean_a=round(statistics.fmean(a_vals), 4) if a_vals else 0.0,
        mean_b=round(statistics.fmean(b_vals), 4) if b_vals else 0.0,
        mean_delta=round(statistics.fmean(deltas), 4) if deltas else 0.0,
        ci_low=lo, ci_high=hi,
        win_rate_b=round(wins / len(deltas), 4) if deltas else 0.0,
        significant=(lo > 0 or hi < 0),
    )


def stratify(per_task: dict[str, float], labels: dict[str, str]) -> dict[str, float]:
    """task_id -> value, task_id -> stratum label  =>  stratum -> mean value."""
    buckets: dict[str, list[float]] = {}
    for t, v in per_task.items():
        buckets.setdefault(labels.get(t, "unlabeled"), []).append(v)
    return {k: round(statistics.fmean(vs), 4) for k, vs in sorted(buckets.items())}
