"""Reader prompts and evidence rendering.

The prompt text below is used by the recorded evaluation runs. Evidence
snippets and the question are appended to the user message."""
from __future__ import annotations

import json
import os
from typing import Any

from .llm import LLM
from .octen_client import SearchHit
from .schema import Task, TaskType

_COMMON_RULES = """\
STRICT GROUNDING RULES:
- Use ONLY the evidence snippets provided. Do NOT use prior knowledge.
- Evidence may be spread across snippets. If the question asks for items meeting
  several conditions, you may combine snippets to establish that an item meets
  them all -- that is reading the evidence, not guessing.
- Include an item when the evidence supports it on balance. Leaving out a
  correct item is penalised exactly as much as including a wrong one, so do not
  withhold an item merely because the support is partial. Returning nothing when
  the evidence points somewhere is the worst outcome.
- Still omit anything the evidence does not point to at all, and never fall back
  on prior knowledge.
- When several members of a family qualify, name each one separately rather than
  the family.
- Return ONLY JSON in the exact schema specified. No prose, no fences."""

READER_T1 = f"""\
You answer an enumeration question from web search evidence.
{_COMMON_RULES}
Schema: {{"entities": ["name1", "name2", ...]}}"""

READER_T2 = f"""\
You fill a comparison matrix from web search evidence.
{_COMMON_RULES}
- Attribute names in the schema encode the required unit; convert values to
  that unit, output the number/string only.
- Leave a cell as "" when the snippets don't support it.
Schema: {{"matrix": {{"<entity>": {{"<attr>": "<value>", ...}}, ...}}}}"""

READER_T4 = f"""\
You answer a single factual question from web search evidence.
{_COMMON_RULES}
Schema: {{"answer": "<short answer>"}}"""


def _interleave_by_subquery(hits: list[SearchHit]) -> list[SearchHit]:
    """Round-robin across sub-query groups (first-appearance order, in-group
    order preserved) so that when the evidence window truncates, every
    sub-query loses its tail evenly instead of trailing groups vanishing
    whole. Hits without sub-query labels form a single group — order unchanged."""
    order: list[Any] = []
    groups: dict[Any, list[SearchHit]] = {}
    for h in hits:
        if h.sub_query not in groups:
            order.append(h.sub_query)
            groups[h.sub_query] = []
        groups[h.sub_query].append(h)
    if len(groups) <= 1:
        return list(hits)
    out: list[SearchHit] = []
    for rank in range(max(len(g) for g in groups.values())):
        for k in order:
            if rank < len(groups[k]):
                out.append(groups[k][rank])
    return out


def _render_snippets(hits: list[SearchHit], max_chars: int | None = None) -> str:
    """Render snippets in order, optionally limited by max_chars or
    WIDESEARCH_READER_MAX_CHARS. The default has no text-length cap."""
    if max_chars is None:
        env = os.environ.get("WIDESEARCH_READER_MAX_CHARS", "").strip()
        max_chars = int(env) if env else 0          # 0 -> no limit
    parts, used = [], 0
    for i, h in enumerate(hits):
        block = f"[{i}] {h.url}\n{h.title}\n{h.snippet}\n"
        if max_chars and used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def read_answer(llm: LLM, task: Task, hits: list[SearchHit]) -> tuple[dict[str, Any], str]:
    """Returns (parsed answer dict, evidence text used) — evidence text feeds
    the hallucination check in grading."""
    evidence = _render_snippets(_interleave_by_subquery(hits))
    if task.type == TaskType.T1_ENUM:
        system = READER_T1
    elif task.type == TaskType.T2_MATRIX:
        system = READER_T2
        # give the reader the required row/column skeleton (attrs encode units)
        skeleton = {e: {a: "" for a in attrs} for e, attrs in task.gold_matrix.items()}
        evidence = f"REQUIRED MATRIX SKELETON:\n{json.dumps(skeleton, ensure_ascii=False)}\n\nEVIDENCE:\n{evidence}"
    elif task.type == TaskType.T4_CONTROL:
        system = READER_T4
    else:
        raise ValueError(f"T3 reader is unsupported; got {task.id}")

    user = f"EVIDENCE SNIPPETS:\n{evidence}\n\nQUESTION:\n{task.question}"
    parsed = llm.complete_json(system, user, max_tokens=2000)
    return parsed, evidence
