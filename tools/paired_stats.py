"""Paired significance for ΔF1 vs. the broad_search base: bootstrap 95% CI,
paired sign-flip permutation p, Holm correction over the three comparisons.
Reads a grades jsonl (task_id / arm / f1). No retrieval.

Usage: python tools/paired_stats.py results/grades.jsonl
"""
import json, sys
import numpy as np
from collections import defaultdict

KEY_ID, KEY_ARM, KEY_F1 = "task_id", "arm", "f1"
BASE = "octen-broad-search"                      # Octen broad_search
LABEL = {"octen-broad-search": "Octen broad_search", "parallel-turbo-agent": "Parallel-turbo",
         "exa-instant-agent": "Exa-instant", "tavily-ultrafast-agent": "Tavily-ultrafast"}
N_BOOT, N_PERM, SEED = 10000, 10000, 20260810


def load(path):
    per = defaultdict(dict)
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        per[r[KEY_ID]][r[KEY_ARM]] = float(r[KEY_F1])
    return per


def paired(per, a, b):
    ids = sorted(q for q, d in per.items() if a in d and b in d)
    return np.array([per[q][a] for q in ids]), np.array([per[q][b] for q in ids])


def analyze(x, y, rng):
    d = x - y
    n = len(d); obs = d.mean()
    boot = d[rng.integers(0, n, size=(N_BOOT, n))].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    signs = rng.choice([-1.0, 1.0], size=(N_PERM, n))
    null = (signs * d).mean(axis=1)
    p = (np.sum(np.abs(null) >= abs(obs)) + 1) / (N_PERM + 1)
    return n, obs, lo, hi, p


def holm(pvals):
    order = np.argsort(pvals); adj = np.empty(len(pvals)); prev = 0.0
    for rank, i in enumerate(order):
        prev = adj[i] = max(prev, min(1.0, (len(pvals) - rank) * pvals[i]))
    return adj


def main():
    per = load(sys.argv[1]); rng = np.random.default_rng(SEED)
    arms = sorted(a for a in {k for d in per.values() for k in d} if a != BASE)
    rows, ps = [], []
    for arm in arms:
        x, y = paired(per, BASE, arm)
        rows.append((arm, *analyze(x, y, rng))); ps.append(rows[-1][5])
    adj = holm(np.array(ps))
    print(f"\n### {sys.argv[1]}")
    print("| Comparison | n | ΔF1 | 95% CI | p | p (Holm) | verdict |")
    print("|---|---|---|---|---|---|---|")
    for (arm, n, obs, lo, hi, p), pa in zip(rows, adj):
        v = "**sig**" if pa < 0.05 else "n.s."
        print(f"| vs. {LABEL.get(arm, arm)} | {n} | {obs:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {p:.4f} | {pa:.4f} | {v} |")


if __name__ == "__main__":
    main()
