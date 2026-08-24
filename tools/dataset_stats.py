"""Dataset statistics for the released task set.
Computes from data/tasks.jsonl: count, language mix, gold-set size
distribution, recency (as_of), set_size labels, and a coarse keyword-based
domain bucketing (approximate — there is no domain field in the schema).
"""
import json, re, statistics as st
from collections import Counter

ROWS = [json.loads(l) for l in open("data/tasks.jsonl") if l.strip()]
n = len(ROWS)


def lang(q):
    return "zh" if re.search(r"[一-鿿]", q) else "en"


DOMAINS = {
    "AI/ML & compute": ["llm", "model", "open-weight", "open weight", "gpu", "moe", "语言模型", "大模型", "ai ", "推理"],
    "Space & aerospace": ["orbit", "rocket", "launch", "satellite", "space", "x-ray", "航天", "火箭", "卫星", "探测"],
    "Biomed & pharma": ["fda", "ema", "therap", "gene", "drug", "vaccine", "sirna", "药", "疗法", "获批", "血友病"],
    "Fintech & payments": ["card", "clearing", "payment", "bank", "license", "牌照", "支付", "清算", "卡"],
    "Cloud & infra": ["cloud", "data center", "data centre", "region", "hyperscal", "云", "数据中心", "可用区"],
    "Sports & leagues": ["league", "franchise", "expansion", "nba", "nfl", "nhl", "mls", "wnba", "联盟", "球队", "扩军"],
    "Open source & foundations": ["open-source", "open source", "foundation", "linux foundation", "开源", "基金会"],
    "Security & cyber": ["cve", "ransomware", "malware", "cisa", "advisory", "漏洞", "勒索", "恶意软件"],
    "Media & streaming": ["stream", "app", "channel", "tv", "流媒体", "应用", "直播"],
}


def domain(q):
    ql = q.lower()
    for d, kws in DOMAINS.items():
        if any(k in ql for k in kws):
            return d
    return "Other/uncategorized"


golds = [len(t.get("gold_entities", [])) for t in ROWS]
langs = Counter(lang(t["question"]) for t in ROWS)
doms = Counter(domain(t["question"]) for t in ROWS)
asof = Counter(str(t.get("as_of")) for t in ROWS)
setsz = Counter(t.get("set_size") for t in ROWS)


def hist(vals):
    b = Counter("2-3" if v <= 3 else "4-6" if v <= 6 else "7-12" if v <= 12 else "13+" for v in vals)
    return dict(sorted(b.items(), key=lambda kv: ["2-3", "4-6", "7-12", "13+"].index(kv[0])))


out = []
out.append("# WideSearch-Bench — Dataset statistics (data/tasks.jsonl)\n")
out.append(f"- **Questions:** {n}")
out.append(f"- **Language:** " + ", ".join(f"{k} {v} ({v*100//n}%)" for k, v in langs.most_common()))
out.append(f"- **Gold-set size:** mean {st.mean(golds):.1f} · median {int(st.median(golds))} · min {min(golds)} · max {max(golds)}")
out.append(f"  - distribution: {hist(golds)}")
out.append(f"- **set_size labels:** {dict(setsz)}")
out.append(f"- **as_of (snapshot dates):** {dict(sorted(asof.items()))}")
out.append("\n## Domain distribution (approximate — keyword-bucketed, no schema field)\n")
for d, c in doms.most_common():
    out.append(f"- {d}: {c} ({c*100//n}%)")
open("data/DATASET_STATS.md", "w").write("\n".join(out) + "\n")
print("\n".join(out))
