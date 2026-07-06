import difflib
import logging
import re

from bot.services import database

logger = logging.getLogger(__name__)

# =========================================================================
# Knowledge base — aliases for branches, doc types, and stopwords
# =========================================================================

BRANCH_ALIASES: list[tuple[str, str]] = [
    ("information technology", "IT"),
    ("computer science engineering", "CSE"),
    ("computer science", "CSE"),
    ("computer engineering", "CSE"),
    ("electronics and telecommunication", "ENTC"),
    ("electronics and telecom", "ENTC"),
    ("electrical engineering", "EEP"),
    ("mechanical engineering", "MECH"),
    ("civil engineering", "CIVIL"),
    ("computer applications", "MCA"),
    ("mech", "MECH"),
    ("mechanical", "MECH"),
    ("entc", "ENTC"),
    ("e&tc", "ENTC"),
    ("electronics", "ENTC"),
    ("eep", "EEP"),
    ("electrical", "EEP"),
    ("ee", "EEP"),
    ("cse", "CSE"),
    ("cs", "CSE"),
    ("computer", "CSE"),
    ("it", "IT"),
    ("ece", "ENTC"),
    ("civil", "CIVIL"),
    ("ce", "CIVIL"),
    ("mca", "MCA"),
    ("mtech", "MTECH"),
    ("m.tech", "MTECH"),
    ("m tech", "MTECH"),
]
BRANCH_ALIASES.sort(key=lambda x: -len(x[0].split()))

DOC_TYPE_ALIASES: list[tuple[str, str]] = [
    ("class test 1", "class_test_1"),
    ("unit test 1", "class_test_1"),
    ("class test 2", "class_test_2"),
    ("unit test 2", "class_test_2"),
    ("end semester", "end_sem"),
    ("question paper", "end_sem"),
    ("previous year", "end_sem"),
    ("paper bundle", "bundle"),
    ("study material", "notes"),
    ("ct1", "class_test_1"),
    ("ct-1", "class_test_1"),
    ("ct2", "class_test_2"),
    ("ct-2", "class_test_2"),
    ("end sem", "end_sem"),
    ("pyq", "end_sem"),
    ("pqy", "end_sem"),
    ("bundle", "bundle"),
    ("notes", "notes"),
    ("note", "notes"),
]
DOC_TYPE_ALIASES.sort(key=lambda x: -len(x[0].split()))

SEM_WORDS = {"sem", "semester", "sem.", "sems"}

STOPWORDS: set[str] = {
    "a", "an", "the", "i", "me", "my", "we", "our", "you", "your",
    "got", "get", "have", "has", "any", "some", "all", "please", "pls",
    "need", "want", "give", "show", "find", "looking", "search",
    "for", "of", "in", "to", "from", "with", "is", "are", "can", "do",
    "paper", "papers", "document", "documents", "material", "materials",
    "question", "questions", "branch", "subject", "sub", "stuff",
    "old", "past", "previous", "latest", "new",
    "ka", "ke", "ki", "hai", "hain", "kya", "ko",  # Hinglish stopwords
    "on", "at", "it", "be", "no", "not", "or", "and", "but", "if",
    "so", "as", "by", "this", "that", "what", "which",
}

# =========================================================================
# Tier 1 — Enhanced regex patterns
# =========================================================================

RE_ORIGINAL = re.compile(
    r"^(?P<subject>.+?)\s+sem\s*(?P<sem>\d)\s*(?P<year>\d{4})?$",
    re.IGNORECASE,
)

RE_SEM_FIRST = re.compile(
    r"sem(?:ester)?\s*(?P<sem>\d)\s+(?P<subject>.+?)(?:\s+(?P<year>\d{4}))?$",
    re.IGNORECASE,
)

RE_IMPLICIT_SEM = re.compile(
    r"^(?P<subject>[a-zA-Z&]+)\s+(?P<sem>\d)\s*(?P<year>\d{4})?$",
    re.IGNORECASE,
)

RE_WITH_TYPE = re.compile(
    r"(?P<doc_type>.+?)\s+(?P<subject>.+?)\s+sem\s*(?P<sem>\d)\s*(?P<year>\d{4})?$",
    re.IGNORECASE,
)

RE_ORDINAL = re.compile(
    r"(?P<sem>\d)(?:st|nd|rd|th)?\s+sem(?:ester)?\s*(?P<subject>.+?)(?:\s+(?P<year>\d{4}))?$",
    re.IGNORECASE,
)

TIER1_PATTERNS = [RE_ORIGINAL, RE_SEM_FIRST, RE_IMPLICIT_SEM, RE_WITH_TYPE, RE_ORDINAL]

# =========================================================================
# Helpers
# =========================================================================

ALL_CANONICAL_BRANCHES = {c for _, c in BRANCH_ALIASES}
ALL_BRANCH_STRINGS = [a for a, _ in BRANCH_ALIASES] + sorted(ALL_CANONICAL_BRANCHES)


def _normalize_subject(raw: str) -> str | None:
    cleaned = raw.strip().upper().rstrip(",")
    if cleaned in ALL_CANONICAL_BRANCHES:
        return cleaned
    for alias, canonical in BRANCH_ALIASES:
        if alias == cleaned.lower():
            return canonical
    return None


def _normalize_doc_type(raw: str) -> str | None:
    cleaned = raw.strip().lower().rstrip(",")
    for alias, canonical in DOC_TYPE_ALIASES:
        if alias == cleaned:
            return canonical
    return None


def _scan_entity(text: str, aliases: list[tuple[str, str]]) -> str | None:
    for alias, canonical in aliases:
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        if re.search(pattern, text):
            return canonical
    return None


def _is_likely_semester(text: str, num_str: str) -> bool:
    for sem_word in SEM_WORDS:
        for pattern in [
            rf"{re.escape(sem_word)}\s*{num_str}",
            rf"{num_str}(?:st|nd|rd|th)?\s*{re.escape(sem_word)}",
        ]:
            if re.search(pattern, text):
                return True
    return False


def _fuzzy_match_branch(text: str, cutoff: float = 0.65) -> str | None:
    words = text.split()
    for word in words:
        if len(word) < 4:
            continue
        if word in STOPWORDS or word in SEM_WORDS:
            continue
        if word.isdigit():
            continue
        matches = difflib.get_close_matches(word, ALL_BRANCH_STRINGS, n=1, cutoff=cutoff)
        if matches:
            matched = matches[0]
            for alias, canonical in BRANCH_ALIASES:
                if matched in (alias, canonical):
                    return canonical
            if matched.upper() in ALL_CANONICAL_BRANCHES:
                return matched.upper()
    return None


# =========================================================================
# Tier 1 — Regex extraction
# =========================================================================

def tier1_extract(text: str) -> dict | None:
    for pattern in TIER1_PATTERNS:
        m = pattern.match(text.strip())
        if not m:
            continue

        subject = _normalize_subject(m.group("subject"))
        if not subject:
            continue

        sem = int(m.group("sem")) if m.group("sem") else None
        year = int(m.group("year")) if m.group("year") else None

        doc_type = None
        try:
            raw_type = m.group("doc_type")
            if raw_type:
                doc_type = _normalize_doc_type(raw_type)
        except (IndexError, AttributeError):
            pass

        return {
            "subject": subject,
            "semester": sem,
            "year": year,
            "doc_type": doc_type,
        }

    return None


# =========================================================================
# Tier 2 — Keyword-based extraction
# =========================================================================

def extract_by_keywords(text: str) -> dict | None:
    text_lower = text.lower().strip()

    subject = _scan_entity(text_lower, BRANCH_ALIASES)
    doc_type = _scan_entity(text_lower, DOC_TYPE_ALIASES)

    numbers = re.findall(r"\d+", text)
    semester = None
    year = None

    for num_str in numbers:
        n = int(num_str)
        if 1 <= n <= 8 and _is_likely_semester(text_lower, num_str):
            semester = n

    for num_str in numbers:
        n = int(num_str)
        if 1900 <= n <= 2100 and len(num_str) == 4:
            year = n

    if semester is None:
        for num_str in numbers:
            n = int(num_str)
            if 1 <= n <= 8:
                semester = n
                break

    if subject is None:
        subject = _fuzzy_match_branch(text_lower)

    if not subject:
        return None

    return {
        "subject": subject,
        "semester": semester,
        "year": year,
        "doc_type": doc_type,
    }


# =========================================================================
# Tokenization — for learned pattern matching
# =========================================================================

def tokenize_query(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9&]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# =========================================================================
# Tier 3 — Fuzzy fallback (already inline in keyword extractor)
# =========================================================================

# (handled by _fuzzy_match_branch called from extract_by_keywords)


# =========================================================================
# Tier 4 — Learned pattern matching (async, DB-backed)
# =========================================================================

async def match_learned_pattern(text: str) -> dict | None:
    query_tokens = tokenize_query(text)
    if not query_tokens:
        return None

    try:
        rows = await database.search_learned_patterns(list(query_tokens))
    except Exception as e:
        logger.warning("Failed to query learned patterns: %s", e)
        return None

    best_score = 0.0
    best_row = None
    for row in rows:
        stored_set = set(row["tokens"])
        score = _jaccard(query_tokens, stored_set)
        if score > best_score:
            best_score = score
            best_row = row

    if best_row and best_score >= 0.4:
        return {
            "subject": best_row["subject"],
            "semester": best_row.get("semester"),
            "year": best_row.get("year"),
            "doc_type": best_row.get("doc_type"),
        }

    return None


async def store_learned_pattern(original_query: str, params: dict) -> None:
    tokens = tokenize_query(original_query)
    if not tokens or "subject" not in params:
        return

    try:
        await database.insert_learned_pattern(
            tokens=list(tokens),
            subject=params["subject"],
            source_query=original_query,
            semester=params.get("semester"),
            year=params.get("year"),
            doc_type=params.get("doc_type"),
        )
        logger.info(
            "LEARNED STORED | query=%r | tokens=%r | params=%r",
            original_query, tokens, params,
        )
    except Exception as e:
        logger.warning("Failed to store learned pattern: %s", e)


# =========================================================================
# Unified extraction pipeline (sync static tiers)
# =========================================================================

def extract_search_params_static(text: str) -> dict | None:
    result = tier1_extract(text)
    if result:
        logger.info("NL (tier1 regex) | %r → %r", text, result)
        return result

    result = extract_by_keywords(text)
    if result:
        logger.info("NL (tier2 keywords) | %r → %r", text, result)
        return result

    return None


# =========================================================================
# Full extraction pipeline (including async learned patterns)
# =========================================================================

async def extract_search_params(text: str) -> dict | None:
    result = extract_search_params_static(text)
    if result:
        return result

    result = await match_learned_pattern(text)
    if result:
        logger.info("NL (tier4 learned) | %r → %r", text, result)
        return result

    return None
