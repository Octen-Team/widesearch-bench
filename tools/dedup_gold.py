"""Merge gold entities that the matcher already treats as the same entity.

Pooling can add a second surface form of an entity that is already in the gold
("BlackSuit" and "BlackSuit (aka Royal)"). Entity-F1 then counts one answer
twice: naming five distinct correct entities scores 0.9091 on a six-slot gold,
while naming four of them plus a duplicate scores 1.0. That rewards restating
an answer over finding another one.

Each group of mutually-matching gold entities collapses to one entity. The
LONGEST surface form becomes the canonical (it never promotes a truncation such
as "Seattle" over "Seattle Kraken"); every other form is kept as an alias, so
nothing a run could previously match becomes unmatchable.

    python tools/dedup_gold.py data/tasks.jsonl --report results/GOLD_DEDUP.md

Pass --check to fail without writing when duplicates remain (for CI).
"""
import argparse
import json

from widesearch_bench.normalize import match_sets
from widesearch_bench.schema import GoldEntity


def group(golds: list[dict]) -> list[list[int]]:
    """Indices of gold entities, grouped by mutual matcher equality."""
    groups: list[list[int]] = []
    for i, g in enumerate(golds):
        for grp in groups:
            rep = golds[grp[0]]
            ge = GoldEntity(canonical=rep["canonical"], aliases=rep.get("aliases") or [])
            if match_sets([g["canonical"]], [ge])[0]:
                grp.append(i)
                break
        else:
            groups.append([i])
    return groups


def merge(golds: list[dict], grp: list[int]) -> dict:
    members = [golds[i] for i in grp]
    keep = max(members, key=lambda g: len(g["canonical"]))
    aliases = list(keep.get("aliases") or [])
    for m in members:
        for form in [m["canonical"], *(m.get("aliases") or [])]:
            if form != keep["canonical"] and form not in aliases:
                aliases.append(form)
    return {**keep, "aliases": aliases}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks")
    ap.add_argument("--report")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if duplicates exist; write nothing")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.tasks, encoding="utf-8") if l.strip()]
    lines, removed, touched = [], 0, 0
    for r in rows:
        golds = r["gold_entities"]
        groups = group(golds)
        if len(groups) == len(golds):
            continue
        touched += 1
        for grp in groups:
            if len(grp) > 1:
                removed += len(grp) - 1
                kept = max((golds[i] for i in grp), key=lambda g: len(g["canonical"]))
                folded = [golds[i]["canonical"] for i in grp
                          if golds[i]["canonical"] != kept["canonical"]]
                lines.append(f"| {r['id']} | {kept['canonical']} | {' · '.join(folded)} |")
        r["gold_entities"] = [merge(golds, grp) for grp in groups]

    if a.check:
        print(f"{removed} duplicate gold entities across {touched} tasks")
        raise SystemExit(1 if removed else 0)

    with open(a.tasks, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = sum(len(r["gold_entities"]) for r in rows)
    print(f"{a.tasks}: merged {removed} duplicates across {touched} tasks "
          f"-> {total} gold entities")

    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write("# Gold de-duplication\n\n"
                    "Gold entities the matcher treats as the same entity, merged to one.\n"
                    "The kept form is the longest surface form; the folded forms are\n"
                    "retained as aliases, so nothing becomes unmatchable.\n\n"
                    f"**{removed} duplicates merged across {touched} tasks.**\n\n"
                    "| Task | Kept as canonical | Folded in as aliases |\n|---|---|---|\n")
            f.write("\n".join(lines) + "\n")
        print(f"report -> {a.report}")


if __name__ == "__main__":
    main()
