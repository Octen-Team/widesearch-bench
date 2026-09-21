"""Offline re-grade: score stored run traces against a specified gold file.

No retrieval is re-run — this reads `detail.answer_entities` out of a grades
file and re-scores it, so you can check the published numbers, or score the same
runs against a different gold (pooled vs strict).

Scoring goes through the same `match_sets` greedy 1:1 matching the live harness
uses in `grading.grade_t1`, and `detail.missed` / `detail.extra` are recomputed
from that same match, so every row's detail agrees with the score beside it.

Usage:
  python tools/regrade.py --grades results/grades.jsonl \\
      --gold data/tasks.jsonl --out /tmp/regraded.jsonl
"""
import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from widesearch_bench.normalize import match_sets
from widesearch_bench.schema import load_tasks


def score(preds, golds):
    """Return unrounded scores and diagnostics using the live match policy."""
    mg, mp = match_sets(preds, golds)
    precision = len(mp) / len(preds) if preds else 0.0
    recall = len(mg) / len(golds) if golds else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    missed = [g.canonical for i, g in enumerate(golds) if i not in mg]
    extra = [p for i, p in enumerate(preds) if i not in mp]
    return f1, precision, recall, missed, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grades", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    tasks = {t.id: t for t in load_tasks(a.gold)}
    per = defaultdict(list)
    out = []
    for line in open(a.grades, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        task = tasks.get(r["task_id"])
        if task is None:
            continue
        preds = [p for p in r["detail"].get("answer_entities", []) if p and p.strip()]
        if r['detail'].get('error'):
            preds = []
        f1, p, rc, missed, extra = score(preds, task.gold_entities)
        r = dict(r)
        r["f1"], r["precision"], r["recall"] = round(f1, 6), round(p, 6), round(rc, 6)
        r["detail"] = {**r["detail"], "missed": missed, "extra": extra}
        out.append(r)
        per[r["arm"]].append(f1)

    with open(a.out, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"regraded {len(out)} rows vs {a.gold} -> {a.out}")
    for arm in sorted(per):
        print(f"  {arm:26} meanF1={st.mean(per[arm]):.4f}  n={len(per[arm])}")


if __name__ == "__main__":
    main()
