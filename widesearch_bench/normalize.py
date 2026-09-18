"""Entity normalization & matching for mechanical grading (zero-LLM).

Normalization pipeline (order matters):
1. Unicode NFKC        — full-width/half-width folding (ＡＰＩ -> API), ligatures
2. casefold            — aggressive lowercasing
3. punctuation strip   — hyphens/dots/commas/quotes/brackets folded to space
4. whitespace collapse — incl. removing spaces entirely for CJK-vs-Latin mixing
5. corporate suffix strip (inc, ltd, corp, and CJK equivalents ...) — optional, on by default

Matching: a predicted string matches a GoldEntity if its normalized form equals
the normalized form of ANY alias (canonical included), or if one strictly
contains the other at token level with length ratio >= 0.6 (handles
"OpenAI GPT-4o" vs "GPT-4o" without letting "AI" match "OpenAI").
"""
from __future__ import annotations

import re
import unicodedata

from .schema import GoldEntity

_PUNCT = re.compile(r"[\-\u2010-\u2015_.,;:!?'\"()\[\]{}<>/\\|@#$%^&*+=~`®™©]")
_WS = re.compile(r"\s+")
_SUFFIXES = (
    "incorporated", "corporation", "company", "limited", "holdings",
    "inc", "corp", "ltd", "llc", "plc", "co", "ag", "sa", "gmbh",
    "有限公司", "股份有限公司", "集团", "公司",
)


def normalize(s: str, strip_suffix: bool = True) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.casefold()
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    if strip_suffix:
        toks = s.split(" ")
        while toks and toks[-1] in _SUFFIXES:
            toks.pop()
        s = " ".join(toks)
        for suf in _SUFFIXES:  # CJK suffixes are not space-delimited
            if len(suf.encode()) > 4 and s.endswith(suf) and len(s) > len(suf):
                s = s[: -len(suf)]
    return s.strip()


def _tight(s: str) -> str:
    """Space-free form for CJK/Latin mixed comparison."""
    return s.replace(" ", "")


# Split an entity string into high-precision sub-forms so grading is robust to
# descriptive parentheticals and appositive suffixes without loosening into
# fuzzy substring matches. E.g.
#   "OpenTofu (Terraform fork) — governed by the LF"
#     -> {"OpenTofu (Terraform fork) — governed by the LF", "OpenTofu",
#         "Terraform fork"}
#   "Luxturna (voretigene neparvovec)" -> {full, "Luxturna", "voretigene neparvovec"}
# so a brand/generic order flip ("voretigene neparvovec (Luxturna)") matches.
_PAREN = re.compile(r"[\(（]([^\)）]*)[\)）]")
_DASH = re.compile(r"\s[‐-―\-]\s|\s[—–]|[—–]")


def _subforms(s: str) -> tuple[set[str], set[str]]:
    """Return (primary, secondary) normalized sub-forms.

    primary   = full string, head-before-paren, head-before-appositive-dash.
                These may participate in loose token-containment.
    secondary = parenthetical contents AND the tail after an appositive dash
                (often a brand/generic alt, a per-market label, or the entity
                itself in a "Country — Scheme" listing). These match ONLY by
                exact / token-multiset equality — never loose containment — so
                a description like "Terraform fork" can't loose-match the gold
                "Terraform", while "Saudi Arabia — mada" still matches "mada".
    """
    raw = s.strip()
    prim: set[str] = set()
    sec: set[str] = set()
    if not raw:
        return prim, sec
    prim.add(raw)
    head = re.split(r"[\(（]", raw, maxsplit=1)[0].strip()
    prim.add(head)
    # "A / B" lists two names for the same entity (a rename, a JV partner, a
    # network/brand pair). Each side is a primary form in its own right —
    # without this the corporate-suffix stripper only fires on the trailing
    # name, so "Sierra Nevada Corporation" never lines up with the gold
    # "Sierra Nevada Corporation / Sierra Space".
    for part in re.split(r"\s+/\s+", head):
        if part.strip():
            prim.add(part.strip())
    dash_parts = _DASH.split(raw, maxsplit=1)
    prim.add(dash_parts[0].strip())
    if len(dash_parts) > 1:                 # tail after "X — Y": Y is a candidate entity
        sec.add(dash_parts[1].strip())
    for m in _PAREN.findall(raw):
        if m.strip():
            sec.add(m.strip())
    prim = {normalize(x) for x in prim if x}
    prim = {x for x in prim if x}
    sec = {normalize(x) for x in sec if x}
    sec = {x for x in sec if x}
    return prim, sec


def entity_match(pred: str, gold: GoldEntity) -> bool:
    p_prim, p_sec = _subforms(pred)
    if not (p_prim or p_sec):
        return False
    g_prim: set[str] = set()
    g_sec: set[str] = set()
    for form in gold.all_forms():
        a, b = _subforms(form)
        g_prim |= a
        g_sec |= b
    p_all, g_all = p_prim | p_sec, g_prim | g_sec

    # (a) exact normalized / tight (CJK) equality, any-form vs any-form
    for p in p_all:
        pt = _tight(p)
        for g in g_all:
            if p == g or pt == _tight(g):
                return True
    # (b) order-insensitive token-multiset equality (>=2 tokens), any vs any
    for p in p_all:
        ptoks = tuple(sorted(p.split()))
        if len(ptoks) < 2:
            continue
        for g in g_all:
            if ptoks == tuple(sorted(g.split())):
                return True
    # (c) guarded token-containment — PRIMARY forms only (no descriptions)
    for p in p_prim:
        for g in g_prim:
            if _token_contained(g, p) or _token_contained(p, g):
                return True
    return False


# After normalization, dots split ("K2.5" -> "k2 5"), so a version suffix is a
# pure digit run or v<digits> token right after the matched span.
_VERSION_TOK = re.compile(r"v?\d+")


def _token_contained(shorter: str, longer: str) -> bool:
    """Token-level containment with guards.

    Match iff the shorter string's tokens appear as a contiguous subsequence
    of the longer's tokens, AND the shorter side is substantive:
    >= 2 tokens, or a single token of >= 5 chars. Plus token-count ratio
    >= 0.5 so a 2-token name can't match a 10-token sentence.
    Blocks: 'ai' vs 'openai' (not token-boundary), 'k2' vs 'kimi k2'
    (1 token, 2 chars). Allows: 'kimi k2' vs 'kimi k2 moonshot'.

    Version-aware guard: a version-style token (digits or v<digits>)
    immediately after the matched span marks a DIFFERENT release
    ('kimi k2 5' i.e. K2.5 must not match 'kimi k2'); such forms only match
    when present verbatim in the alias table (exact equality fires before
    containment in entity_match). Non-version suffixes ('... series',
    '... instruct') still match.
    """
    st, lt = shorter.split(), longer.split()
    if not st or len(st) > len(lt):
        return False
    if len(st) == 1 and len(st[0]) < 5:
        return False
    ratio = len(st) / len(lt)
    # A mid-span match needs the halves to be comparable in length, so a short
    # name can't be pulled out of a long unrelated phrase. An ANCHORED match is
    # different evidence: when the shorter name is exactly how the longer one
    # begins or ends, the longer is almost always the same entity described more
    # fully ("Apollo 11" vs "Apollo 11 Passive Seismic Experiment"). Agent loops
    # answer with those fuller forms far more often than a one-shot reader does,
    # so a flat ratio floor silently penalises verbosity rather than error.
    if ratio < 0.25:
        return False
    for i in range(len(lt) - len(st) + 1):
        if lt[i:i + len(st)] == st:
            anchored = (i == 0 or i + len(st) == len(lt))
            if ratio < 0.5 and not (anchored and len(st) >= 2):
                continue
            nxt = lt[i + len(st)] if i + len(st) < len(lt) else ""
            if nxt and _VERSION_TOK.fullmatch(nxt):
                continue  # version boundary — not the same entity
            return True
    return False


def match_sets(preds: list[str], golds: list[GoldEntity]) -> tuple[set[int], set[int]]:
    """Greedy 1:1 matching. Returns (matched_gold_indices, matched_pred_indices).

    Greedy is sufficient because alias tables make matches near-binary; if a
    pred matches multiple golds (rare, indicates a bad alias table), the first
    unmatched gold wins and the collision is a data-quality bug to fix, not a
    scoring subtlety to optimize.
    """
    mg, mp = set(), set()
    for pi, pred in enumerate(preds):
        for gi, gold in enumerate(golds):
            if gi in mg:
                continue
            if entity_match(pred, gold):
                mg.add(gi)
                mp.add(pi)
                break
    return mg, mp
