"""CLI: run the benchmark, validate a task file, or check the environment.

  widesearch run data/tasks.jsonl --out results/ --repeats 1
  widesearch validate data/tasks.jsonl
  widesearch doctor
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .runner import run_bench
from .schema import load_tasks

DEFAULT_ARMS = "octen-broad-search,exa-instant-agent,tavily-ultrafast-agent,parallel-turbo-agent"


def main() -> None:
    ap = argparse.ArgumentParser(prog="widesearch")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the benchmark over a task file")
    r.add_argument("tasks")
    r.add_argument("--out", default="results")
    r.add_argument("--arms", default=DEFAULT_ARMS,
                   help=f"comma-separated arm ids (default: {DEFAULT_ARMS})")
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--reader-model", default=None)
    r.add_argument("--no-time-pushdown", action="store_true",
                   help="ignore task time_scope; no time filter at retrieval")
    r.add_argument("--dump-raw", action="store_true",
                   help="dump per-run retrieval hits to <out>/raw/*.jsonl")
    r.add_argument("--concurrency", type=int, default=5,
                   help="parallel runs (published results used 5). The agent arms "
                        "require >1; at 1 only the octen-* arms can run, but "
                        "latency_s is then contention-free.")

    v = sub.add_parser("validate", help="check a task file against the schema")
    v.add_argument("tasks")

    sub.add_parser("doctor", help="check env vars and search-API connectivity")

    args = ap.parse_args()

    if args.cmd == "doctor":
        from .doctor import doctor
        sys.exit(doctor())

    if args.cmd == "validate":
        tasks = load_tasks(args.tasks)
        errs = [e for t in tasks for e in t.validate()]
        if errs:
            print("\n".join(errs))
            sys.exit(1)
        n_t1 = sum(1 for t in tasks if t.type.value == "T1")
        print(f"OK: {len(tasks)} tasks valid ({n_t1} T1)")
        return

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    report = asyncio.run(run_bench(
        args.tasks, args.out, arms=arms,
        repeats=args.repeats, reader_model=args.reader_model,
        time_pushdown=not args.no_time_pushdown, dump_raw=args.dump_raw,
        concurrency=args.concurrency))
    print(json.dumps(report["arms"], ensure_ascii=False, indent=2))
    for c in report["comparisons"]:
        sig = "SIGNIFICANT" if c["significant"] else "n.s."
        print(f"{c['arm_b']} vs {c['arm_a']} on {c['metric']}: "
              f"Δ={c['mean_delta']:+.4f} [{c['ci_low']}, {c['ci_high']}] "
              f"win={c['win_rate_b']:.0%} ({sig})")


if __name__ == "__main__":
    main()
