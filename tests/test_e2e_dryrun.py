"""End-to-end dry run: mock retrieval + mock reader through the full
runner -> grading -> stats -> report pipeline. Zero network.

Simulates the expected signal: octen-broad-search/octen-fanout retrieve wider (more gold covered),
octen-search narrower — then checks the report machinery surfaces exactly that.
"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from widesearch_bench.octen_client import SearchHit
from widesearch_bench.schema import ArmRun, GoldEntity, Task, TaskType
from widesearch_bench.grading import grade
from widesearch_bench.runner import build_report

# --- build a small synthetic task set: 6 T1 tasks, gold set size 8 each ---
def make_task(i):
    golds = [GoldEntity(f"Vendor{i}_{j}", [f"vendor{i}-{j}.com essentials"]) for j in range(8)]
    return Task(id=f"t1-syn-{i}", type=TaskType.T1_ENUM, question=f"synthetic wide q{i}",
                gold_entities=golds, as_of="2026-07-21", set_size="M",
                term_drift=("high" if i % 2 else "low"), min_gold_domains=0)

tasks = [make_task(i) for i in range(6)]

# --- simulate arm behavior: octen-search finds 3/8 gold, octen-broad-search finds 6/8, octen-fanout finds 7/8 ---
COVERAGE = {"octen-search": 3, "octen-broad-search": 6, "octen-fanout": 7}
CALLS    = {"octen-search": 1, "octen-broad-search": 1, "octen-fanout": 8}
LAT      = {"octen-search": 0.8, "octen-broad-search": 1.6, "octen-fanout": 3.5}

grades = []
for task in tasks:
    for arm, k in COVERAGE.items():
        for rep in range(3):
            found = [g.canonical for g in task.gold_entities[:k]]
            # octen-search additionally hallucinates one entity not in evidence
            preds = found + (["Phantom Systems"] if arm == "octen-search" else [])
            urls = [f"https://site{j}.example/{task.id}" for j in range(k)]
            run = ArmRun(task_id=task.id, arm=arm, repeat=rep,
                         answer_entities=preds, retrieved_urls=urls,
                         api_calls=CALLS[arm], latency_s=LAT[arm],
                         downstream_tokens=3000 + 500 * k)
            evidence = " ".join(found)   # phantom absent from evidence
            grades.append(grade(task, run, evidence))

report = build_report(tasks, grades, ["octen-search", "octen-broad-search", "octen-fanout"])
print(json.dumps(report["arms"], indent=2))
print()
for c in report["comparisons"]:
    sig = "SIGNIFICANT" if c["significant"] else "n.s."
    print(f"{c['arm_b']} vs {c['arm_a']}: dF1={c['mean_delta']:+.4f} "
          f"CI[{c['ci_low']}, {c['ci_high']}] win={c['win_rate_b']:.0%} ({sig})")

# --- assertions: the machinery must surface the designed signal ---
a = report["arms"]
assert a["octen-broad-search"]["f1_mean"] > a["octen-search"]["f1_mean"], "octen-broad-search should beat octen-search on F1"
assert a["octen-fanout"]["f1_mean"] > a["octen-broad-search"]["f1_mean"], "octen-fanout ceiling above octen-broad-search"
assert a["octen-broad-search"]["f1_per_call"] > a["octen-fanout"]["f1_per_call"], "octen-broad-search wins efficiency (headline!)"
assert a["octen-search"]["hallucinated_rate_mean"] > 0 and a["octen-broad-search"]["hallucinated_rate_mean"] == 0
assert all(c["significant"] for c in report["comparisons"])
assert "high" in report["strata"]["octen-broad-search"]["f1_by_term_drift"]
print("\nDRY RUN PASS: pipeline runner->grading->stats->report intact")
