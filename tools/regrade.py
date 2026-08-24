"""Offline re-grade: score stored run traces against a specified gold file.
No retrieval is re-run — reads answer_entities from grades and recomputes
Entity-F1 against the given gold. Emits a grades jsonl + prints per-arm means.

Usage:
  python tools/regrade.py --grades results/grades_expanded.jsonl \
      --gold data/tasks.jsonl --out results/grades_regraded.jsonl
"""
import argparse, json, statistics as st
from collections import defaultdict
from widesearch_bench.normalize import entity_match
from widesearch_bench.schema import load_tasks


def f1(pred, gold):
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    tp = sum(1 for g in gold if any(entity_match(p, g) for p in pred))
    P = tp / len(pred) if pred else 0.0
    R = tp / len(gold) if gold else 0.0
    F = 2 * P * R / (P + R) if (P + R) else 0.0
    return F, P, R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grades", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    tasks = {t.id: t for t in load_tasks(a.gold)}
    per = defaultdict(list)
    out = []
    for line in open(a.grades):
        if not line.strip():
            continue
        r = json.loads(line)
        tid = r["task_id"]
        if tid not in tasks:
            continue
        F, P, R = f1(r["detail"].get("answer_entities", []), tasks[tid].gold_entities)
        r = dict(r); r["f1"], r["precision"], r["recall"] = round(F, 6), round(P, 6), round(R, 6)
        out.append(r); per[r["arm"]].append(F)
    with open(a.out, "w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"regraded {len(out)} rows vs {a.gold} -> {a.out}")
    for arm in sorted(per):
        print(f"  {arm:26} meanF1={st.mean(per[arm]):.4f}  n={len(per[arm])}")


if __name__ == "__main__":
    main()
