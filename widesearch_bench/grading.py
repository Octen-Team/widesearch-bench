"""Mechanical grading (zero-LLM) for T1/T2/T4 + shared cost/diversity metrics.

T3 (survey) grading would be LLM-judged and is out of scope here; this
module covers the 60%+ of tasks that must grade deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .normalize import entity_match, match_sets, normalize
from .schema import ArmRun, Task, TaskType


@dataclass
class Grade:
    task_id: str
    arm: str
    repeat: int
    # quality
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    cell_fill: float = 0.0        # T2: fraction of gold cells answered
    cell_accuracy: float = 0.0    # T2: correct / answered
    accuracy: float = 0.0         # T4
    hallucinated_rate: float = 0.0  # preds not matching gold AND not present in retrieved evidence
    source_diversity: int = 0     # distinct domains among retrieved urls that contributed matches
    # cost passthrough
    api_calls: int = 0
    http_requests: int | None = None
    latency_s: float = 0.0
    downstream_tokens: int | None = 0
    detail: dict = field(default_factory=dict)


def _domains(urls: list[str]) -> set[str]:
    out = set()
    for u in urls:
        try:
            d = urlparse(u).netloc.lower().removeprefix("www.")
            if d:
                out.add(d)
        except Exception:
            continue
    return out


def grade_t1(task: Task, run: ArmRun, evidence_text: str = "") -> Grade:
    preds = [p for p in run.answer_entities if p and p.strip()]
    golds = task.gold_entities
    mg, mp = match_sets(preds, golds)

    recall = len(mg) / len(golds) if golds else 0.0
    precision = len(mp) / len(preds) if preds else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    # hallucination: unmatched preds whose normalized form never appears in evidence
    ev_norm = normalize(evidence_text, strip_suffix=False) if evidence_text else ""
    halluc = 0
    for pi, p in enumerate(preds):
        if pi in mp:
            continue
        if not ev_norm or normalize(p, strip_suffix=False) not in ev_norm:
            halluc += 1
    halluc_rate = halluc / len(preds) if preds else 0.0

    missed = [golds[i].canonical for i in range(len(golds)) if i not in mg]
    extra = [preds[i] for i in range(len(preds)) if i not in mp]
    return Grade(
        task_id=task.id, arm=run.arm, repeat=run.repeat,
        precision=round(precision, 4), recall=round(recall, 4), f1=round(f1, 4),
        hallucinated_rate=round(halluc_rate, 4),
        source_diversity=len(_domains(run.retrieved_urls)),
        api_calls=run.api_calls, latency_s=run.latency_s,
        downstream_tokens=run.downstream_tokens,
        detail={"missed": missed, "extra": extra},
    )


def grade_t2(task: Task, run: ArmRun) -> Grade:
    gold = task.gold_matrix
    pred = run.answer_matrix or {}
    total_cells = sum(len(attrs) for attrs in gold.values())
    answered = correct = 0
    misses: list[str] = []

    # map predicted entity keys onto gold entity keys via normalization
    pred_keys = {normalize(k): k for k in pred}
    for gent, attrs in gold.items():
        pkey = pred_keys.get(normalize(gent))
        for attr, gval in attrs.items():
            pval = (pred.get(pkey, {}) or {}).get(attr, "") if pkey else ""
            if pval and str(pval).strip():
                answered += 1
                if _value_match(str(pval), str(gval)):
                    correct += 1
                else:
                    misses.append(f"{gent}.{attr}: pred={pval!r} gold={gval!r}")
            else:
                misses.append(f"{gent}.{attr}: <empty>")

    fill = answered / total_cells if total_cells else 0.0
    acc = correct / answered if answered else 0.0
    return Grade(
        task_id=task.id, arm=run.arm, repeat=run.repeat,
        cell_fill=round(fill, 4), cell_accuracy=round(acc, 4),
        f1=round(2 * fill * acc / (fill + acc), 4) if (fill + acc) else 0.0,
        source_diversity=len(_domains(run.retrieved_urls)),
        api_calls=run.api_calls, latency_s=run.latency_s,
        downstream_tokens=run.downstream_tokens,
        detail={"cell_misses": misses[:50]},
    )


def _value_match(pred: str, gold: str) -> bool:
    """Cell-value comparison: normalized string equality, or numeric within 2%.

    Gold values should be annotated in canonical units; numeric tolerance
    absorbs formatting ($3.00 vs 3 USD vs 3.0) but NOT unit errors — annotate
    unit into the attribute name (e.g. 'price_usd_per_mtok') so readers are
    forced onto one unit.
    """
    if normalize(pred, strip_suffix=False) == normalize(gold, strip_suffix=False):
        return True
    pn, gn = _num(pred), _num(gold)
    if pn is not None and gn is not None and gn != 0:
        return abs(pn - gn) / abs(gn) <= 0.02
    return False


def _num(s: str):
    import re
    m = re.search(r"-?\d+(?:[.,]\d+)?", s.replace(",", ""))
    try:
        return float(m.group()) if m else None
    except ValueError:
        return None


def grade_t4(task: Task, run: ArmRun) -> Grade:
    ok = bool(task.gold_answer) and (
        normalize(task.gold_answer, strip_suffix=False)
        in normalize(run.answer_text, strip_suffix=False)
    )
    return Grade(
        task_id=task.id, arm=run.arm, repeat=run.repeat,
        accuracy=1.0 if ok else 0.0,
        source_diversity=len(_domains(run.retrieved_urls)),
        api_calls=run.api_calls, latency_s=run.latency_s,
        downstream_tokens=run.downstream_tokens,
    )


def grade(task: Task, run: ArmRun, evidence_text: str = "") -> Grade:
    if run.error:
        g = Grade(task_id=task.id, arm=run.arm, repeat=run.repeat,
                  api_calls=run.api_calls, latency_s=run.latency_s)
        g.detail["error"] = run.error
    elif task.type == TaskType.T1_ENUM:
        g = grade_t1(task, run, evidence_text)
    elif task.type == TaskType.T2_MATRIX:
        g = grade_t2(task, run)
    elif task.type == TaskType.T4_CONTROL:
        g = grade_t4(task, run)
    else:
        raise ValueError(f"T3 tasks are judge-graded and unsupported; got {task.id}")
    # observability passthrough (scores untouched): the reader's raw entity
    # output makes T1 attribution one-step — empty vs grounded-but-wrong vs
    # matcher miss can be read straight off grades.jsonl.
    g.http_requests = run.http_requests
    g.downstream_tokens = run.downstream_tokens
    g.detail["retrieval_errors"] = list(run.retrieval_errors)
    g.detail["answer_entities"] = list(run.answer_entities)
    g.detail["search_time_s"] = run.search_time_s
    g.detail["e2e_time_s"] = run.e2e_time_s
    g.detail["n_queries"] = run.n_queries
    if run.subqueries:
        g.detail["subqueries"] = run.subqueries
    return g
