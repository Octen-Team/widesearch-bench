"""Derive the aliases the matcher provably needs, and write them into the task file.

The grader blocks a single-token containment shorter than 5 characters, so a
prediction of "M3" never reaches the gold "Apple M3" even though "M4 Pro" does
reach "Apple M4 Pro". That guard is correct in general — it stops "K2" matching
"Kimi K2" — so the fix belongs in the alias table, not the matcher.

Rule: inside one task, if several gold entities begin with the same leading
token, that token is a shared brand prefix. The remainder is added as an alias,
but only when it is unambiguous *within that task's own gold set* — i.e. it does
not also match a different gold entity of the same task. Cross-task ambiguity is
irrelevant: grading is always per task.

    python tools/derive_aliases.py data/2026-09/tasks.jsonl [--write]

Without --write it only reports. Run it for tasks_strict.jsonl too; the alias
companion table is refreshed by tools/export_aliases.py.
"""
import collections
import json
import re
import sys

# a model code: letters then digits, optionally more alphanumerics (m3, a18, rtx4090)
MODEL_CODE = re.compile(r"[a-z]+\d+[a-z0-9]*")

sys.path.insert(0, ".")
from widesearch_bench.normalize import entity_match, normalize  # noqa: E402
from widesearch_bench.schema import GoldEntity  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else "data/2026-09/tasks.jsonl"
write = "--write" in sys.argv

rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
added = 0
touched = 0
report = []

for task in rows:
    golds = task["gold_entities"]
    if len(golds) < 2:
        continue
    heads = collections.Counter()
    for g in golds:
        toks = normalize(g["canonical"]).split()
        if len(toks) >= 2:
            heads[toks[0]] += 1
    shared = {h for h, n in heads.items() if n >= 2}
    if not shared:
        continue

    task_dirty = False
    for g in golds:
        toks = normalize(g["canonical"]).split()
        if len(toks) < 2 or toks[0] not in shared:
            continue
        cand = " ".join(toks[1:])
        if not cand or len(cand) < 2:
            continue
        # Only a model code survives: the remainder must LEAD with a token that
        # mixes letters and digits ("m3", "a18", "rtx4090"). A bare number
        # ("Apollo 11" -> "11") or a generic type word ("Austin FC" -> "fc",
        # "Node.js" -> "js") identifies nothing on its own and would match
        # unrelated entities across the corpus.
        if not MODEL_CODE.fullmatch(toks[1]):
            continue
        me = GoldEntity(canonical=g["canonical"], aliases=g.get("aliases", []))
        if entity_match(cand, me):
            continue  # matcher already reaches it — no alias needed
        others = [GoldEntity(canonical=o["canonical"], aliases=o.get("aliases", []))
                  for o in golds if o is not g]
        if any(entity_match(cand, o) for o in others):
            continue  # ambiguous inside this task — unsafe
        g.setdefault("aliases", []).append(cand)
        added += 1
        task_dirty = True
        report.append((task["id"], g["canonical"], cand))
    touched += task_dirty

print(f"{path}: {added} aliases derived across {touched} tasks")
for tid, canon, alias in report[:25]:
    print(f"  {tid}  {canon!r} += {alias!r}")
if len(report) > 25:
    print(f"  ... and {len(report) - 25} more")

if write:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {path}")
else:
    print("(dry run — pass --write to apply)")
