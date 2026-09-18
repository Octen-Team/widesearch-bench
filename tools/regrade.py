"""Offline re-grade: score stored run traces against a specified gold file.

No retrieval is re-run — this reads `detail.answer_entities` out of a grades
file and re-scores it, so you can check the published numbers, or score the same
runs against a different gold (pooled vs strict).

Scoring goes through the same `match_sets` greedy 1:1 matching the live harness
uses in `grading.grade_t1`. An earlier version of this script counted gold
entities that had any matching prediction, which let one prediction be credited
against several gold entities; it disagreed with the harness on 21% of rows and
scored every arm 0.05-0.07 too high. `detail.missed` / `detail.extra` are
recomputed from the same match, so each row's detail agrees with its own score.

Usage:
  python tools/regrade.py --grades results/2026-08/grades_expanded.jsonl \\
      --gold data/2026-08/tasks.jsonl --out /tmp/regraded.jsonl
"""
import argparse
import json
import statistics as st
from collections import defaultdict

from widesearch_bench.normalize import match_sets
from widesearch_bench.schema import load_tasks


def score(preds, golds):
    """Return (f1, precision, recall, missed, extra) exactly as grade_t1 would."""
    if not preds and not golds:
        return 1.0, 1.0, 1.0, [], []
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
