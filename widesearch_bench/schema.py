"""Dataset & result schema for WideSearch-Bench.

Task JSONL format (one task per line):
type T1 (enumeration) / T2 (matrix) / T3 (survey) / T4 (single-fact control).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TaskType(str, Enum):
    T1_ENUM = "T1"
    T2_MATRIX = "T2"
    T3_SURVEY = "T3"
    T4_CONTROL = "T4"


class SetSize(str, Enum):
    S = "S"   # <=5 gold entities
    M = "M"   # 6-15
    L = "L"   # 16-50


@dataclass
class GoldEntity:
    """One gold answer entity with its alias table (normalized matching)."""
    canonical: str
    aliases: list[str] = field(default_factory=list)

    def all_forms(self) -> list[str]:
        return [self.canonical, *self.aliases]


@dataclass
class Task:
    id: str
    type: TaskType
    question: str
    # --- gold, by type ---
    gold_entities: list[GoldEntity] = field(default_factory=list)      # T1
    gold_matrix: dict[str, dict[str, str]] = field(default_factory=dict)  # T2: entity -> {attr: value}
    gold_points: list[str] = field(default_factory=list)               # T3 must_include key points
    gold_answer: Optional[str] = None                                  # T4
    # --- provenance & controls ---
    as_of: str = ""                    # gold annotation date, ISO
    volatility: str = "static"         # static | dynamic
    set_size: Optional[SetSize] = None
    term_drift: str = "low"            # low | mid | high
    language: str = "en"               # en | zh | mixed
    min_gold_domains: int = 4          # minimum distinct source-domain metadata entries
    gold_source_domains: list[str] = field(default_factory=list)
    time_scope: Optional[str] = None   # e.g. "2025": push published-time filter to retrieval (all arms)
    notes: str = ""

    def validate(self) -> list[str]:
        errs = []
        if self.type == TaskType.T1_ENUM and not self.gold_entities:
            errs.append(f"{self.id}: T1 without gold_entities")
        if self.type == TaskType.T2_MATRIX and not self.gold_matrix:
            errs.append(f"{self.id}: T2 without gold_matrix")
        if self.type == TaskType.T3_SURVEY and not self.gold_points:
            errs.append(f"{self.id}: T3 without gold_points")
        if self.type == TaskType.T4_CONTROL and not self.gold_answer:
            errs.append(f"{self.id}: T4 without gold_answer")
        if self.type in (TaskType.T1_ENUM, TaskType.T2_MATRIX):
            if len(set(self.gold_source_domains)) < self.min_gold_domains:
                errs.append(
                    f"{self.id}: gold spans {len(set(self.gold_source_domains))} domains "
                    f"< min {self.min_gold_domains} (source-domain metadata threshold)")
        if not self.as_of:
            errs.append(f"{self.id}: missing as_of timestamp")
        if self.time_scope is not None and not re.fullmatch(r"\d{4}", self.time_scope):
            errs.append(f"{self.id}: time_scope must be a 4-digit year, got {self.time_scope!r}")
        return errs


@dataclass
class ArmRun:
    """One (task, arm, repeat) execution record."""
    task_id: str
    arm: str                       # octen-search | octen-broad-search | octen-fanout
    repeat: int
    answer_entities: list[str] = field(default_factory=list)   # reader's extracted entities (T1)
    answer_matrix: dict[str, dict[str, str]] = field(default_factory=dict)  # T2
    answer_text: str = ""          # T3/T4 raw answer
    retrieved_urls: list[str] = field(default_factory=list)
    subqueries: list[str] = field(default_factory=list)
    api_calls: int = 0           # logical retrieval invocations, not verified billing units
    http_requests: int = 0       # requests actually issued, retries included
    n_queries: int = 0           # observed subqueries or issued agent search actions
    latency_s: float = 0.0
    search_time_s: float = 0.0   # time spent in search calls (retrieval only)
    e2e_time_s: float = 0.0      # end-to-end: search + reader/agent reasoning
    retrieval_errors: list[str] = field(default_factory=list)
    downstream_tokens: int | None = 0
    error: Optional[str] = None


# ------------------------------------------------------------------ io
def load_tasks(path: str | Path) -> list[Task]:
    tasks = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        d["type"] = TaskType(d["type"])
        if d.get("set_size"):
            d["set_size"] = SetSize(d["set_size"])
        d["gold_entities"] = [GoldEntity(**g) for g in d.get("gold_entities", [])]
        tasks.append(Task(**d))
    return tasks


def dump_runs(runs: list[ArmRun], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in runs:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
