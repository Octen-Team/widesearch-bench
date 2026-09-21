"""Unit tests for the mechanical grading core (zero network needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from widesearch_bench.grading import grade_t1, grade_t2, grade_t4
from widesearch_bench.normalize import entity_match, match_sets, normalize
from widesearch_bench.schema import ArmRun, GoldEntity, Task, TaskType
from widesearch_bench.stats import bootstrap_ci, paired_compare


def test_normalize():
    assert normalize("ＡＰＩ") == "api"                      # full-width fold
    assert normalize("Moonshot AI, Inc.") == "moonshot ai"   # punct + suffix
    assert normalize("阿里巴巴集团") == "阿里巴巴"              # CJK suffix
    assert normalize("Brave-Search__API") == "brave search api"


def test_entity_match():
    g = GoldEntity(canonical="Kimi K2", aliases=["moonshotai/Kimi-K2", "Kimi-K2 Instruct"])
    assert entity_match("kimi k2", g)
    assert entity_match("MOONSHOTAI/KIMI-K2", g)
    assert entity_match("Kimi K2 (Moonshot)", g)     # containment, ratio ok
    assert not entity_match("Kimi", g)                # ratio guard blocks
    assert not entity_match("K2", g)
    g2 = GoldEntity(canonical="OpenAI")
    assert not entity_match("AI", g2)                 # short containment blocked


def test_match_sets_greedy():
    golds = [GoldEntity("Exa"), GoldEntity("Tavily"), GoldEntity("Brave Search API", ["Brave"])]
    preds = ["exa.ai" , "Brave", "SerpApi"]
    mg, mp = match_sets(preds, golds)
    # exa.ai vs Exa: containment ratio 3/6=0.5 < 0.6 -> by design NOT matched
    # (alias tables must carry domain forms; this is the data-quality contract)
    assert 2 in mg and 1 in mp          # Brave matched
    assert len(mg) == 1


def test_grade_t1_f1_and_hallucination():
    task = Task(id="x", type=TaskType.T1_ENUM, question="q", as_of="2026-01-01",
                gold_entities=[GoldEntity("Exa", ["exa.ai"]), GoldEntity("Tavily")],
                min_gold_domains=0)
    run = ArmRun(task_id="x", arm="octen-broad-search", repeat=0,
                 answer_entities=["Exa", "Ghost Corp"],
                 retrieved_urls=["https://exa.ai/p", "https://tavily.com/p"])
    g = grade_t1(task, run, evidence_text="Exa is a search API. Tavily too.")
    assert g.recall == 0.5 and g.precision == 0.5
    assert g.hallucinated_rate == 0.5        # "Ghost Corp" absent from evidence
    assert g.source_diversity == 2
    assert g.detail["missed"] == ["Tavily"]


def test_grade_t2():
    task = Task(id="m", type=TaskType.T2_MATRIX, question="q", as_of="2026-01-01",
                gold_matrix={"Exa": {"price_usd": "5", "free_tier": "1000"}},
                min_gold_domains=0)
    run = ArmRun(task_id="m", arm="octen-search", repeat=0,
                 answer_matrix={"exa": {"price_usd": "$5.00", "free_tier": ""}})
    g = grade_t2(task, run)
    assert g.cell_fill == 0.5
    assert g.cell_accuracy == 1.0            # $5.00 ~ 5 numeric within 2%


def test_grade_t4():
    task = Task(id="f", type=TaskType.T4_CONTROL, question="q", as_of="2026-01-01",
                gold_answer="4.08", min_gold_domains=0)
    run = ArmRun(task_id="f", arm="octen-search", repeat=0,
                 answer_text="New Zealand's criminality score was 4.08 in 2023.")
    assert grade_t4(task, run).accuracy == 1.0


def test_stats_paired():
    a = {f"t{i}": 0.5 for i in range(20)}
    b = {f"t{i}": 0.7 for i in range(20)}
    c = paired_compare(a, b, "f1", "octen-search", "octen-broad-search")
    assert c.mean_delta == 0.2 and c.significant and c.win_rate_b == 1.0
    lo, hi = bootstrap_ci([1.0, 1.0, 1.0])
    assert lo == hi == 1.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("all tests passed")


def test_shared_parenthetical_gloss_is_not_identity():
    """A gloss describes an entity; two entities sharing one are still distinct."""
    from widesearch_bench.normalize import entity_match
    from widesearch_bench.schema import GoldEntity

    gold = GoldEntity(canonical="Freevee (standalone app) — shut down August 2025",
                      aliases=[])
    assert not entity_match("Showtime (standalone app)", gold)
    # but a gloss may still reach a PRIMARY form on the other side
    sierra = GoldEntity(canonical="Sierra Nevada Corporation / Sierra Space (Dream Chaser)",
                        aliases=[])
    assert entity_match("Sierra Space", sierra)
