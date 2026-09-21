"""Paired bootstrap intervals and sign-flip tests for every arm pair.

Holm correction covers all six comparisons. Failed attempts remain zero-F1
observations; costs are not part of this test. Usage: paired_stats.py GRADES
"""
import itertools
import json
import sys
from collections import defaultdict
import numpy as np

N_BOOT, N_PERM, SEED = 10000, 10000, 20260810
LABEL = {'exa-instant-agent': 'Exa-instant', 'octen-broad-search': 'Octen broad_search',
         'parallel-turbo-agent': 'Parallel-turbo', 'tavily-ultrafast-agent': 'Tavily-ultrafast'}


def load(path):
    per = defaultdict(dict)
    for line in open(path, encoding='utf-8'):
        if line.strip():
            row = json.loads(line)
            if row['arm'] in per[row['task_id']]:
                raise ValueError('Expected one repeat per task/arm; aggregate repeats first')
            per[row['task_id']][row['arm']] = float(row['f1'])
    return per


def paired(per, a, b):
    ids = sorted(q for q, d in per.items() if a in d and b in d)
    return np.array([per[q][a] for q in ids]), np.array([per[q][b] for q in ids])


def analyze(x, y, rng):
    d = x - y
    n = len(d)
    obs = d.mean()
    boot = d[rng.integers(0, n, size=(N_BOOT, n))].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    null = (rng.choice([-1.0, 1.0], size=(N_PERM, n)) * d).mean(axis=1)
    p = (np.sum(np.abs(null) >= abs(obs)) + 1) / (N_PERM + 1)
    return n, float(obs), float(lo), float(hi), float(p)


def holm(pvals):
    order = np.argsort(pvals)
    adj = np.empty(len(pvals))
    prev = 0.0
    for rank, i in enumerate(order):
        prev = adj[i] = max(prev, min(1.0, (len(pvals) - rank) * pvals[i]))
    return adj


def comparisons(per):
    arms = sorted({k for d in per.values() for k in d})
    rows = []
    rng = np.random.default_rng(SEED)
    for a, b in itertools.combinations(arms, 2):
        n, delta, lo, hi, p = analyze(*paired(per, a, b), rng)
        rows.append(dict(a=a, b=b, n=n, delta=delta, lo=lo, hi=hi, p=p))
    for row, adjusted in zip(rows, holm([r['p'] for r in rows])):
        row['p_holm'] = float(adjusted)
    return rows


def table(rows):
    lines = ['| A − B | n | ΔF1 | 95% bootstrap CI | permutation p | Holm p |',
             '|---|---:|---:|---|---:|---:|']
    for r in rows:
        lines.append(f"| {LABEL[r['a']]} − {LABEL[r['b']]} | {r['n']} | {r['delta']:+.4f} | "
                     f"[{r['lo']:+.4f}, {r['hi']:+.4f}] | {r['p']:.4f} | {r['p_holm']:.4f} |")
    return '\n'.join(lines)


if __name__ == '__main__':
    print(table(comparisons(load(sys.argv[1]))))
