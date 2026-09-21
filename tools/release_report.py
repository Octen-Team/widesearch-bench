"""Rebuild the complete release from stored answers and current gold; no network.

Run from the repository root: python tools/release_report.py
Use --check to detect stale generated files without writing to them.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from tools.regrade import score
from tools.paired_stats import LABEL, SEED, comparisons, table
from widesearch_bench.schema import load_tasks


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def rescore(rows, tasks):
    result = copy.deepcopy(rows)
    for row in result:
        detail = row['detail']
        preds = [p for p in detail['answer_entities'] if p and p.strip()]
        if detail.get('error'):
            preds = []
        f, p, r, missed, extra = score(preds, tasks[row['task_id']].gold_entities)
        row.update(f1=round(f, 6), precision=round(p, 6), recall=round(r, 6))
        detail.update(missed=missed, extra=extra)
    return result


def summarize(rows):
    summary = {}
    for arm in sorted({r['arm'] for r in rows}):
        ar = sorted((r for r in rows if r['arm'] == arm), key=lambda r: r['task_id'])
        ok = [r for r in ar if not r['detail'].get('error') and not r['detail'].get('retrieval_errors')]
        x = np.array([r['f1'] for r in ar])
        rng = np.random.default_rng(SEED)
        ci = np.percentile(x[rng.integers(0, len(x), size=(10000, len(x)))].mean(axis=1), [2.5, 97.5])
        entry = {k: statistics.mean(r[k] for r in ar) for k in ('f1', 'precision', 'recall')}
        entry.update(n=len(ar), successes=len(ok), failures=len(ar)-len(ok), ci=list(ci))
        for key in ['api_calls', 'downstream_tokens', 'e2e_time_s', 'http_requests']:
            values = [r['detail'].get(key) if key == 'e2e_time_s' else r.get(key) for r in ok]
            known = [v for v in values if v is not None]
            entry[key] = statistics.mean(known) if known else None
            entry[key + '_n'] = len(known)
        summary[arm] = entry
    return summary


def build():
    raw = jsonl(ROOT / 'results/grades.jsonl')
    gold = {t.id:t for t in load_tasks(ROOT / 'data/tasks.jsonl')}
    strict = {t.id:t for t in load_tasks(ROOT / 'data/tasks_strict.jsonl')}
    expected = {(tid, arm) for tid in gold for arm in LABEL}
    actual = [(r['task_id'], r['arm']) for r in raw]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('Release must contain exactly one row per task and configured arm')
    rows = rescore(raw, gold)
    strict_rows = rescore(raw, strict)
    per = {tid: {r['arm']:r['f1'] for r in rows if r['task_id']==tid} for tid in gold}
    per_strict = {tid: {r['arm']:r['f1'] for r in strict_rows if r['task_id']==tid} for tid in gold}
    stats, strict_stats = summarize(rows), summarize(strict_rows)
    paired, paired_strict = comparisons(per), comparisons(per_strict)
    failures = [r for r in rows if r['detail'].get('error')]
    output = {}
    def emit(path, content): output[path] = content.rstrip() + '\n'
    emit('results/grades.jsonl', '\n'.join(json.dumps(r,ensure_ascii=False) for r in rows))
    summary = dict(arms=stats, strict_arms=strict_stats, comparisons=paired,
                   strict_comparisons=paired_strict, quality_policy='all attempts; errors score zero',
                   cost_policy='successful attempts only; denominator stored for each metric',
                   tasks=len(gold), pooled_entities=sum(len(t.gold_entities) for t in gold.values()),
                   strict_entities=sum(len(t.gold_entities) for t in strict.values()),
                   errors=len(failures),
                   missing_http_attempt_counts=sum(r.get('http_requests') is None for r in rows),
                   missing_query_traces=sum(r['detail'].get('subqueries') is None for r in rows),
                   recorded_tokens=sum(r['downstream_tokens'] or 0 for r in rows))
    emit('results/summary.json', json.dumps(summary,ensure_ascii=False,indent=2))
    lines = ['| Configuration | Pooled F1 | Strict F1 | Precision | Recall | E2E s | Recorded LLM tokens |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for arm,s in stats.items():
        lines.append(f"| {LABEL[arm]} | {s['f1']:.4f} | {strict_stats[arm]['f1']:.4f} | {s['precision']:.4f} | {s['recall']:.4f} | {s['e2e_time_s']:.2f} | {s['downstream_tokens']:,.0f} |")
    best = max(stats, key=lambda a: stats[a]['f1'])
    if (best == max(strict_stats, key=lambda a: strict_stats[a]['f1'])
            and best == min(stats, key=lambda a: stats[a]['e2e_time_s'])
            and best == min(stats, key=lambda a: stats[a]['downstream_tokens'])):
        lines += ['', f"On this dataset, {LABEL[best]} has the highest mean Entity-F1 against both reference sets and the lowest recorded mean latency and downstream-token usage."]
    lines += ['', f'F1 averages all {len(gold)} tasks; latency and token means use completed runs. Precision and recall use pooled references.']
    block='\n'.join(lines)
    emit('results/RESULTS.md', '# Results\n\n'+block+'\n\n[All pairwise comparisons](PAIRED_STATS.md) · [Configuration and measurements](../data/PROVENANCE.md)')
    emit('results/PAIRED_STATS.md','# Paired Entity-F1 comparisons\n\nBootstrap 95% intervals and two-sided sign-flip permutation tests; 10,000 samples, seed '+str(SEED)+'. Holm correction covers all six arm pairs separately within each gold variant. No significant difference does not establish equivalence.\n\n## Pooled gold\n\n'+table(paired)+'\n\n## Strict gold\n\n'+table(paired_strict))
    cases=[]
    for tid,t in sorted(gold.items()):
        cases.append(dict(task_id=tid,question=t.question,
                          gold_entities=[dict(canonical=g.canonical,aliases=g.aliases) for g in t.gold_entities],
                          gold_count=len(t.gold_entities),reader_model='openai:gpt-5-mini',
                          arms={r['arm']:dict(predicted_entities=r['detail']['answer_entities'],
                              f1=r['f1'],precision=r['precision'],recall=r['recall'],
                              missed=r['detail']['missed'],extra=r['detail']['extra'],
                              error=r['detail'].get('error'),subqueries=r['detail'].get('subqueries'),
                              http_requests=r.get('http_requests'),n_real_queries=r['detail']['n_queries'],
                              e2e_time_s=r['detail']['e2e_time_s'],downstream_tokens=r['downstream_tokens'])
                                for r in sorted(rows,key=lambda r:r['arm']) if r['task_id']==tid}))
    emit('results/cases.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    for filename, replacement in [('README.md',block),('data/DATASHEET.md',
            f"- Questions: {len(gold)}\n- Pooled entities: {summary['pooled_entities']}; strict entities: {summary['strict_entities']}\n- Pooled set sizes: mean {statistics.mean(len(t.gold_entities) for t in gold.values()):.1f}, median {statistics.median(len(t.gold_entities) for t in gold.values()):g}, range {min(len(t.gold_entities) for t in gold.values())}–{max(len(t.gold_entities) for t in gold.values())}")]:
        content=(ROOT/filename).read_text()
        content=re.sub(r'<!-- BEGIN GENERATED -->.*?<!-- END GENERATED -->','<!-- BEGIN GENERATED -->\n'+replacement+'\n<!-- END GENERATED -->',content,flags=re.S)
        emit(filename,content)
    decisions=json.loads((ROOT/'data/identity_decisions.json').read_text())
    dlines=['# Reviewed entity identities','',decisions['scope'],'', 'The machine-readable decisions are in `data/identity_decisions.json`. Scoring similarity does not authorize new identity merges.', '', '| Task | Action | Canonical | Source surface forms |','|---|---|---|---|']
    for d in decisions['decisions']:
        forms = d.get('members', []) + d.get('aliases', [])
        if d.get('remove_aliases'):
            forms += ['Removed ambiguous alias: ' + a for a in d['remove_aliases']]
        dlines.append(f"| {d['task_id']} | {d['action']} | {d.get('canonical','—')} | {' · '.join(forms)} |")
    emit('data/aliases/gold_aliases.jsonl', '\n'.join(json.dumps(
        dict(task_id=t.id, canonical=g.canonical, aliases=g.aliases), ensure_ascii=False)
        for t in gold.values() for g in t.gold_entities))
    emit('results/GOLD_DEDUP.md','\n'.join(dlines))
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args=parser.parse_args()
    stale=[]
    for name,content in build().items():
        path=ROOT/name
        if not path.exists() or path.read_text()!=content:
            stale.append(name)
            if not args.check:path.write_text(content,encoding='utf-8')
    if args.check and stale:raise SystemExit('Stale generated artifacts: '+', '.join(stale))
    print('Release artifacts verified' if args.check else 'Rebuilt: '+', '.join(stale))


if __name__=='__main__': main()
