"""Entity normalization & matching for mechanical grading (zero-LLM).

Normalization pipeline (order matters):
1. Unicode NFKC        — full-width/half-width folding (ＡＰＩ -> API), ligatures
2. casefold            — aggressive lowercasing
3. punctuation strip   — hyphens/dots/commas/quotes/brackets folded to space
4. whitespace collapse — incl. removing spaces entirely for CJK-vs-Latin mixing
5. corporate suffix strip (inc, ltd, corp, and CJK equivalents ...) — optional, on by default

Matching: a predicted string matches a GoldEntity if its normalized form equals
the normalized form of ANY alias (canonical included), including presentation
variants described below. Arbitrary substring containment is not identity.
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
    # Programming-language and product-name symbols distinguish identities.
    s = s.replace("+", " plus ").replace("#", " sharp ")
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

    primary   = full string and string with parenthetical descriptions removed,
                preserving identity qualifiers that follow the parentheses.
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
    head = _PAREN.sub(" ", raw).strip()
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
    # An appositive head alone can be a family name (e.g. a prize),
    # so do not manufacture an alias by discarding its category.
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
    # Answers may append explanatory prose. Strip it only on the prediction
    # side; stripping gold would turn category-specific awards into a family.
    parts = _DASH.split(pred, maxsplit=1)
    head = parts[0].strip()
    # Strip a prose explanation, not a short model/category qualifier.
    descriptive = len(parts) > 1 and bool(re.search(
        r"\b(reached|launched|operated|governed|inaugural|founded|introduced|released|"
        r"began|withdrawn|shut down|first orbital success)\b|"
        r"已获|获批|获准|获得|正式推出|开始运营|成立于|发射于",
        parts[1], re.I))
    if len(parts) > 1 and re.match(r"^(pro|max|air|plus|extreme|ultra|tv)\b", parts[1].strip(), re.I):
        descriptive = False
    if descriptive:
        a, b = _subforms(head)
        p_prim |= a
        p_sec |= b
    if not (p_prim or p_sec):
        return False
    g_prim: set[str] = set()
    g_sec: set[str] = set()
    for form in gold.all_forms():
        a, b = _subforms(form)
        g_prim |= a
        g_sec |= b
    # A parenthetical gloss or appositive tail DESCRIBES an entity, it does not
    # name one: "Showtime (standalone app)" and "Freevee (standalone app)" share
    # a description, not an identity. So a secondary form may be matched against
    # a PRIMARY form on the other side -- that is how "Sierra Space" reaches
    # gold "Sierra Nevada Corporation / Sierra Space (...)" -- but never against
    # another secondary. Branch (c) already had this restriction.
    pairs = [(p, g) for p in p_prim for g in (g_prim | g_sec)]
    pairs += [(p, g) for p in (p_sec - p_prim) for g in g_prim]

    # (a) exact normalized / tight (CJK) equality
    for p, g in pairs:
        if p == g or _tight(p) == _tight(g):
            return True
    # (b) order-insensitive token-multiset equality (>=2 tokens)
    for p, g in pairs:
        ptoks = tuple(sorted(p.split()))
        if len(ptoks) < 2:
            continue
        if ptoks == tuple(sorted(g.split())):
            return True
    # (c) guarded token-containment — PRIMARY forms only (no descriptions)
    for p in p_prim:
        for g in g_prim:
            if _token_contained(g, p) or _token_contained(p, g):
                return True
    return False


def _token_contained(shorter: str, longer: str) -> bool:
    """Allow only explicit presentation suffixes, never arbitrary containment.

    A substring does not establish entity identity: Node.js Foundation differs
    from JS Foundation, and model suffixes such as Pro/Max/Air are significant.
    Other equivalent surface forms must be recorded as reviewed aliases.
    """
    st, lt = shorter.split(), longer.split()
    if len(st) < 2 or lt[:len(st)] != st:
        return False
    return lt[len(st):] in (["series"], ["model"], ["instruct"])


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
