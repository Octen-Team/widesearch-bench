"""Per-run retrieval diagnostics, isolated across concurrent asyncio tasks."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import time


@dataclass
class RetrievalMetrics:
    requests: int = 0
    queries: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


_current: ContextVar[RetrievalMetrics | None] = ContextVar("retrieval_metrics", default=None)


def record_request() -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.requests += 1


def record_query(query: str) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.queries.append(query)


def record_error(error: Exception) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.errors.append(f"{type(error).__name__}: {error}")


def observe_run(fn):
    @wraps(fn)
    async def wrapped(*args, **kwargs):
        metrics = RetrievalMetrics()
        token = _current.set(metrics)
        start = time.monotonic()
        try:
            run, evidence = await fn(*args, **kwargs)
            run.http_requests = metrics.requests
            run.retrieval_errors = metrics.errors
            if metrics.queries and run.error:
                run.subqueries = metrics.queries
                run.n_queries = len(metrics.queries)
                run.api_calls = len(metrics.queries)
            run.e2e_time_s = round(time.monotonic() - start, 3)
            if run.error:
                # A failure can occur after charged completions: zero is not
                # an estimate of missing usage.
                run.downstream_tokens = None
            return run, evidence
        finally:
            _current.reset(token)
    return wrapped
