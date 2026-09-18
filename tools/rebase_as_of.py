"""Move a task file's snapshot date forward, in the `as_of` field and in the
question text itself.

The text matters as much as the field: the reader only sees the question, so a
question that still says "As of 27 July 2026" is asking for July's answer no
matter what the metadata says.

    python tools/rebase_as_of.py data/2026-09/tasks.jsonl 2026-09-18 [--write]

Questions carrying no date phrase at all are left alone and reported — most are
historical ("which missions deployed a seismometer"), where a snapshot date adds
nothing, but a `dynamic` one in that list needs a human to decide the wording.
"""
import json
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "data/2026-09/tasks.jsonl"
new_date = sys.argv[2] if len(sys.argv) > 2 else "2026-09-18"
write = "--write" in sys.argv

Y, M, D = (int(x) for x in new_date.split("-"))
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
EN_LONG = f"{D} {MONTHS[M]} {Y}"        # 18 September 2026
EN_US = f"{MONTHS[M]} {D}, {Y}"         # September 18, 2026
EN_MONTH = f"{MONTHS[M]} {Y}"           # September 2026
ZH_FULL = f"{Y}年{M}月{D}日"
ISO = new_date

# Ordered: the most specific phrasing must be rewritten before the loosest one,
# otherwise a bare-year rule eats the day and month it was meant to preserve.
RULES = [
    (re.compile(r"截至\s*20\d\d年\d{1,2}月\d{1,2}日"), f"截至{ZH_FULL}"),
    (re.compile(r"截至\s*20\d\d-\d{2}-\d{2}"), f"截至{ISO}"),
    (re.compile(r"截至\s*20\d\d年\d{1,2}月"), f"截至{Y}年{M}月"),
    (re.compile(r"截至\s*20\d\d\s*年?"), f"截至{ZH_FULL}"),
    (re.compile(r"\b([Aa]s of)\s+20\d\d-\d{2}-\d{2}"), rf"\1 {ISO}"),
    (re.compile(r"\b([Aa]s of)\s+\d{1,2}\s+[A-Z][a-z]+\s+20\d\d"), rf"\1 {EN_LONG}"),
    (re.compile(r"\b([Aa]s of)\s+[A-Z][a-z]+\s+\d{1,2},?\s+20\d\d"), rf"\1 {EN_US}"),
    (re.compile(r"\b([Aa]s of)\s+mid-20\d\d"), rf"\1 {EN_MONTH}"),
    (re.compile(r"\b([Aa]s of)\s+[A-Z][a-z]+\s+20\d\d"), rf"\1 {EN_MONTH}"),
    (re.compile(r"\b([Aa]s of)\s+20\d\d\b"), rf"\1 {EN_MONTH}"),
]
HAS_DATE = re.compile(r"[Aa]s of|截至")

rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
rewritten = 0
undated = []
for r in rows:
    q = r["question"]
    new_q = q
    for pat, rep in RULES:
        new_q2 = pat.sub(rep, new_q)
        if new_q2 != new_q:
            new_q = new_q2
            break
    if new_q != q:
        r["question"] = new_q
        rewritten += 1
    elif not HAS_DATE.search(q):
        undated.append(r)
    r["as_of"] = new_date

print(f"{path}: rewrote the date phrase in {rewritten}/{len(rows)} questions; "
      f"as_of set to {new_date} on all of them")
still = [r for r in rows if re.search(r"20\d\d年[78]月|July 20\d\d|27 July|23 July|mid-20\d\d", r["question"])]
print(f"question text still mentioning the old snapshot: {len(still)}")
for r in still[:5]:
    print(f"  {r['id']}: {r['question'][:110]}")

print(f"\nno date phrase at all: {len(undated)}  "
      f"({sum(1 for r in undated if r.get('volatility') == 'dynamic')} of them dynamic — need a human)")
for r in undated:
    if r.get("volatility") == "dynamic":
        print(f"  {r['id']}: {r['question'][:110]}")

if write:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {path}")
else:
    print("\n(dry run — pass --write to apply)")
