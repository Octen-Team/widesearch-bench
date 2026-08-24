import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from widesearch_bench.octen_client import OctenClient

P = OctenClient._parse_hits

def test_flat_results():
    hits = P({"results": [{"url": "https://a.com", "title": "A", "snippet": "s"}]})
    assert len(hits) == 1 and hits[0].snippet == "s"

def test_data_results_highlight_str():
    hits = P({"data": {"results": [{"url": "https://a.com", "highlight": "h"}]}})
    assert hits[0].snippet == "h"

def test_grouped_subquery():
    data = {"data": {"groups": [
        {"sub_query": "q1", "results": [{"url": "https://a.com", "snippet": "x"}]},
        {"sub_query": "q2", "results": [{"url": "https://b.com", "snippet": "y"}]}]}}
    hits = P(data)
    assert {h.sub_query for h in hits} == {"q1", "q2"}

def test_highlight_as_list_of_objects():
    hits = P({"results": [{"url": "https://a.com",
                           "highlight": [{"text": "p1"}, {"text": "p2"}]}]})
    assert hits[0].snippet == "p1 p2"

def test_alt_grouping_key_and_dedup():
    data = {"queries": [
        {"query": "sub-a", "items": [{"url": "https://a.com", "summary": "s"}]},
        {"query": "sub-a", "items": [{"url": "https://a.com", "summary": "s"}]}]}
    hits = P(data)
    assert len(hits) == 1 and hits[0].sub_query == "sub-a"

def test_no_false_positive_on_metadata():
    hits = P({"request_id": "x", "latency_ms": 5, "data": {"results": []}})
    assert hits == []

if __name__ == "__main__":
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            f(); print(f"PASS {n}")
    print("adaptive parser tests passed")
