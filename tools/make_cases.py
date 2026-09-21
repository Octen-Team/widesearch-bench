"""Rebuild results/cases.jsonl — the per-question view of what every arm answered.

Joins data/tasks.jsonl (question + gold) with results/grades.jsonl
(per-run scores against the pooled gold), so the file always agrees with the
reported numbers. Run from the repository root:

    python tools/make_cases.py

Pass a different grades file to score another run.
"""
import json
import sys

GRADES = sys.argv[1] if len(sys.argv) > 1 else "results/grades.jsonl"
READER_MODEL = "openai:gpt-5-mini"


def jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


tasks = {t["id"]: t for t in jsonl("data/tasks.jsonl")}

graded: dict[str, dict] = {}
for g in jsonl(GRADES):
    graded.setdefault(g["task_id"], {})[g["arm"]] = g

rows = []
for tid in sorted(tasks):
    task = tasks[tid]
    rows.append({
        "task_id": tid,
        "question": task["question"],
        "gold_entities": task["gold_entities"],
        "gold_count": len(task["gold_entities"]),
        "reader_model": READER_MODEL,
        "arms": {
            arm: {
                "predicted_entities": g["detail"].get("answer_entities", []),
                "f1": g["f1"],
                "precision": g["precision"],
                "recall": g["recall"],
                "missed": g["detail"].get("missed", []),
                "extra": g["detail"].get("extra", []),
                "n_real_queries": g["detail"].get("n_queries"),
                "e2e_time_s": g["detail"].get("e2e_time_s"),
                "downstream_tokens": g.get("downstream_tokens"),
            }
            for arm, g in sorted(graded.get(tid, {}).items())
        },
    })

with open("results/cases.jsonl", "w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"results/cases.jsonl: {len(rows)} rows from {GRADES}")
