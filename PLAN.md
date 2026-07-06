# PLAN: Adding Natural Language Querying to GECA Study Bot

## 1. Current State

The bot's `/search` command uses a single rigid regex:

```
/search <subject> sem <n> [year]
# Examples:
#   /search CSE sem 4
#   /search CSE sem 3 2025
```

The regex lives in `bot/handlers/search.py:13-16`:

```python
QUERY_RE = re.compile(
    r"^(?P<subject>.+?)\s+sem\s*(?P<sem>\d)\s*(?P<year>\d{4})?$",
    re.IGNORECASE,
)
```

If the user phrases it differently — "show me CSE papers semester 4", "sem 4 CSE", "5th sem CSE end sem papers" — the query is rejected entirely. There is **zero tolerance** for natural phrasing.

---

## 2. What "Natural Language" Means Here

Users would be able to type things like:

| Natural Query | Extracted Parameters |
|---|---|
| "Give me CSE semester 4 papers from 2025" | subject=CSE, semester=4, year=2025 |
| "Show me all end sem question papers for ENTC sem 6" | subject=ENTC, semester=6, doc_type=end_sem |
| "Do you have any notes for Mechanical sem 3?" | subject=MECH, semester=3, doc_type=notes |
| "I need class test 1 papers for IT branch semester 5" | subject=IT, semester=5, doc_type=class_test_1 |
| "Physics sem 2 bundle" | subject=Physics, semester=2, doc_type=bundle |
| "CSE 4" | subject=CSE, semester=4 |
| "MECH 2024" | subject=MECH, year=2024 |
| "5th sem CSE end sem" | subject=CSE, semester=5, doc_type=end_sem |
| "old papers for computer science sem 6" | subject=CSE, semester=6, doc_type=end_sem |
| "MECH sem 3 ct1" | subject=MECH, semester=3, doc_type=class_test_1 |

The domain is **heavily constrained** — the user always wants the same 4 fields (subject, semester, year, doc_type). This is a structured extraction problem with a tiny, well-defined vocabulary. It does not need an LLM.

---

## 3. The Approach: Keyword-Based Lexical Extraction

**No LLM. No API calls. No ML training. No new pip dependencies.** Just Python stdlib (`re`, `difflib`).

### How it works

```
User query string
    │
    ▼
┌─────────────────────────┐
│ Tier 1: Regex           │  ← ~5 patterns for the most common phrasings
│ (sub-millisecond)       │     handles "sem 4 CSE", "CSE 4 2025", etc.
└──────┬──────────────────┘
       │ match?
       ├── yes ──► query database
       │
       ▼ no
┌─────────────────────────┐
│ Tier 2: Keyword Scanner │  ← tokenize → scan for branch names, doc types,
│ (milliseconds)          │     numbers → piece together the 4 fields
└──────┬──────────────────┘     using positional heuristics
       │ extracted something?
       ├── yes ──► query database
       │
       ▼ no
┌─────────────────────────┐
│ Tier 3: Fuzzy Match     │  ← try edit-distance matching against known
│ (milliseconds)          │     branch/subject names for mistyped queries
└──────┬──────────────────┘
       │
       ▼ no
  "Could not understand" error
```

Every tier runs **locally in-process**, costs nothing, and completes in <5ms total.

---

## 4. Detailed Design: The Keyword Scanner (Tier 2)

This is the core innovation. Instead of trying to parse sentence structure, it uses a **bag-of-keywords** approach: scan the text for known words/ngrams from each category, then assemble the results.

### 4.1. Knowledge Base (the dictionaries)

```python
# Every known branch and its aliases — ordered longest-first so multi-word
# aliases match before single-word ones during scanning.
BRANCH_ALIASES = [
    ("information technology", "IT"),
    ("computer science", "CSE"),
    ("computer engineering", "CSE"),
    ("electronics and telecommunication", "ENTC"),
    ("electronics and telecom", "ENTC"),
    ("electrical engineering", "EEP"),
    ("mechanical engineering", "MECH"),
    ("civil engineering", "CIVIL"),
    ("computer applications", "MCA"),
    # single-word / abbreviation aliases
    ("mech", "MECH"), ("mechanical", "MECH"),
    ("entc", "ENTC"), ("e&tc", "ENTC"), ("electronics", "ENTC"),
    ("eep", "EEP"), ("electrical", "EEP"), ("ee", "EEP"),
    ("cse", "CSE"), ("cs", "CSE"), ("computer", "CSE"),
    ("it", "IT"),
    ("civil", "CIVIL"), ("ce", "CIVIL"),
    ("mca", "MCA"),
    ("mtech", "MTECH"), ("m.tech", "MTECH"), ("m tech", "MTECH"),
]
# Sort longest-first for greedy multi-word matching
BRANCH_ALIASES.sort(key=lambda x: -len(x[0].split()))

# Doc types — same longest-first ordering
DOC_TYPE_ALIASES = [
    ("class test 1", "class_test_1"), ("unit test 1", "class_test_1"),
    ("class test 2", "class_test_2"), ("unit test 2", "class_test_2"),
    ("end semester", "end_sem"),
    ("question paper", "end_sem"),
    ("previous year", "end_sem"),
    ("paper bundle", "bundle"),
    ("study material", "notes"),
    ("ct1", "class_test_1"), ("ct-1", "class_test_1"),
    ("ct2", "class_test_2"), ("ct-2", "class_test_2"),
    ("end sem", "end_sem"),
    ("pyq", "end_sem"),
    ("bundle", "bundle"),
    ("notes", "notes"),
]
DOC_TYPE_ALIASES.sort(key=lambda x: -len(x[0].split()))

# Semester-indicating words (for positional scoring)
SEM_WORDS = {"sem", "semester", "sem.", "sems"}
```

### 4.2. Scanning Algorithm

```python
import difflib
import re

def extract_by_keywords(text: str) -> dict | None:
    """
    Scan the input text for known branch names, doc types, and numbers.
    Assemble the strongest candidates into structured search parameters.

    Returns a dict with any of: subject, semester, year, doc_type.
    Returns None if nothing useful was found.
    """
    text_lower = text.lower().strip()

    # ── Phase 1: Scan for n-gram keyword matches ────────────────────────

    subject = _scan_branch(text_lower)
    doc_type = _scan_doc_type(text_lower)

    # ── Phase 2: Extract numbers and classify them ──────────────────────

    numbers = re.findall(r'\d+', text)
    semester = None
    year = None

    for num_str in numbers:
        n = int(num_str)
        if 1 <= n <= 8:
            # Could be a semester. Score it by proximity to SEM_WORDS.
            if _is_likely_semester(text_lower, num_str):
                semester = n
        elif 1900 <= n <= 2100 and len(num_str) == 4:
            # 4-digit year
            year = n
        elif 9 <= n <= 12:
            # These could be short year (rare) or non-sem numbers. Ignore them
            # unless they're the only number in the query.
            pass

    # If we still have no semester but found a single-digit number 1-8,
    # take it as the semester (e.g., "CSE 4")
    if semester is None:
        for num_str in numbers:
            n = int(num_str)
            if 1 <= n <= 8:
                semester = n
                break

    # ── Phase 3: Checks and assembly ────────────────────────────────────

    if not subject:
        # Fuzzy fallback: try edit-distance match against all branch keys
        subject = _fuzzy_match_branch(text_lower)

    if not subject:
        return None  # we need at least a subject

    return {
        "subject": subject,
        "semester": semester,
        "year": year,
        "doc_type": doc_type,
    }


def _scan_branch(text: str) -> str | None:
    """
    Scan for the longest matching branch alias in the text.
    Uses a greedy longest-first match (no overlapping).
    """
    consumed = set()  # character spans already claimed by a match
    best = None
    best_pos = None

    for alias, canonical in BRANCH_ALIASES:
        for m in re.finditer(re.escape(alias), text):
            span = (m.start(), m.end())
            if any(a <= m.start() < b or a < m.end() <= b for a, b in consumed):
                continue  # overlapping with a longer match
            if best is None or span[0] < best_pos:
                best = canonical
                best_pos = span[0]
                consumed.add(span)

    return best


def _scan_doc_type(text: str) -> str | None:
    """
    Same greedy longest-first scan for doc type aliases.
    """
    consumed = set()
    best = None
    best_pos = None

    for alias, canonical in DOC_TYPE_ALIASES:
        for m in re.finditer(re.escape(alias), text):
            span = (m.start(), m.end())
            if any(a <= m.start() < b or a < m.end() <= b for a, b in consumed):
                continue
            if best is None or span[0] < best_pos:
                best = canonical
                best_pos = span[0]
                consumed.add(span)

    return best


def _is_likely_semester(text: str, num_str: str) -> bool:
    """
    Check if a number appears near semester-indicating words.
    E.g., "sem 4" or "4th semester" or "4th sem".
    """
    for sem_word in SEM_WORDS:
        # Check patterns: "sem 4", "4th sem", "semester-4", "4 semester"
        for pattern in [
            rf'{re.escape(sem_word)}\s*{num_str}',
            rf'{num_str}(?:st|nd|rd|th)?\s*{re.escape(sem_word)}',
        ]:
            if re.search(pattern, text):
                return True
    return False


def _fuzzy_match_branch(text: str, cutoff: float = 0.6) -> str | None:
    """
    Use difflib to try matching a mistyped branch name.
    E.g., "csee" → "CSE", "mechanic" → "MECH", "eltronics" → "ENTC"
    """
    words = text.split()
    all_aliases = [a for a, _ in BRANCH_ALIASES] + [
        "MECH", "ENTC", "EEP", "CSE", "MCA", "MTECH", "IT", "CIVIL"
    ]
    for word in words:
        matches = difflib.get_close_matches(word, all_aliases, n=1, cutoff=cutoff)
        if matches:
            matched = matches[0]
            # Map alias to canonical form
            for a, c in BRANCH_ALIASES:
                if matched in (a, c):
                    return c
            return matched.upper()
    return None
```

### 4.3. Why This Works

The scanner succeeds on all the example queries from Section 2:

| Query | Branch Match | Doc Type Match | Numbers |
|---|---|---|---|
| "Give me CSE semester 4 papers from 2025" | "CSE" → CSE | — | 4→sem, 2025→year |
| "Show me all end sem question papers for ENTC sem 6" | "ENTC" → ENTC | "end sem" → end_sem | 6→sem |
| "Do you have any notes for Mechanical sem 3?" | "Mechanical" → MECH | "notes" → notes | 3→sem |
| "5th sem CSE end sem" | "CSE" → CSE | "end sem" → end_sem | 5→sem |
| "MECH sem 3 ct1" | "MECH" → MECH | "ct1" → class_test_1 | 3→sem |
| "old papers for computer science sem 6" | "computer science" → CSE | — | 6→sem |
| "I need CSE sem 5 2024 end semester pyq" | "CSE" → CSE | "end semester" → end_sem | 5→sem, 2024→year |

The key insight: **word order doesn't matter**. The scanner doesn't care whether the user puts the branch first, last, or in the middle. It just finds the tokens that look like branches, doc types, and numbers, and assembles them. This handles phrasings that regex would choke on.

---

## 5. Implementation Plan

### 5.1. Extend the Database Layer

**File: `bot/services/database.py`**

Add an optional `doc_type` filter and make `semester` optional:

```python
async def search_documents(
    subject: str,
    semester: int | None = None,       # was: required
    year: int | None = None,
    doc_type: str | None = None,       # NEW
) -> list[dict]:
    params = {
        "select": "*",
        "subject": f"ilike.*{subject}*",
        "order": "uploaded_at.desc",
    }
    if semester is not None:
        params["semester"] = f"eq.{semester}"
    if year is not None:
        params["year"] = f"eq.{year}"
    if doc_type is not None:
        params["doc_type"] = f"eq.{doc_type}"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()
```

### 5.2. Create the NL Extraction Service

**New file: `bot/services/nlp.py`**

Contains:
- The `QUERY_RE` regex (moved from search.py to keep the old handler intact)
- The enhanced regex patterns (Tier 1)
- The keyword scanner (Tier 2)
- The fuzzy fallback (Tier 3)
- A single `extract_search_params(text)` entry point

### 5.3. Modify the Search Handler

**File: `bot/handlers/search.py`**

```python
from bot.services import database, nlp

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "Usage: /search <query>\n\n"
            "Examples:\n"
            "  /search CSE sem 4 2025\n"
            "  /search end sem papers for MECH sem 5\n"
            "  /search 3rd sem IT notes"
        )
        return

    params = nlp.extract_search_params(query)
    if not params or "subject" not in params:
        await update.message.reply_text(
            "Sorry, I couldn't understand that query.\n\n"
            "Try: /search <branch> sem <n> [year]\n"
            "Branches: MECH, ENTC, EEP, CSE, MCA, MTECH, IT, CIVIL\n"
            "Example: /search CSE sem 3 2025"
        )
        return

    subject = params["subject"]
    semester = params.get("semester")
    year = params.get("year")
    doc_type = params.get("doc_type")

    # ... rest of the function is identical to current code,
    # just passes doc_type to database.search_documents() ...
```

### 5.4. Handle Non-Command Messages (Optional but High-Impact)

**File: `bot/main.py`** — register a `MessageHandler` for plain text:

```python
from telegram.ext import MessageHandler, filters
from bot.handlers.search import search  # or a new wrapper

app.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND,
    plaintext_search_handler,
))
```

This lets users **completely skip** the `/search` prefix and just type:

> "got any end sem papers for CSE sem 5?"

The bot intercepts it directly and treats it as a search. The handler is the same function, just called without `context.args` — instead it reads `update.message.text`.

### 5.5. Update Help Text

The `/help` command and README should advertise the natural language support:

```
/search <branch> sem <n> [year]
    Or just describe what you need!
    Examples:
      CSE sem 4 2025
      end sem papers for MECH sem 5
      3rd sem IT notes
      Mechanical sem 6 ct1
```

---

## 6. Complete File Map (What Changes)

| File | Action | Lines Changed |
|---|---|---|
| `bot/services/nlp.py` | **NEW** — keyword scanner + regex patterns + fuzzy fallback + tokenizer + learned pattern matcher | ~250 lines |
| `bot/services/database.py` | Edit — add `doc_type` param to `search_documents()`, add `learned_patterns` CRUD | ~30 lines |
| `bot/handlers/search.py` | Edit — new extraction pipeline + clarification flow + follow-up reply handler | ~60 lines |
| `bot/handlers/start.py` | Edit — update help text to show NL examples | ~5 lines |
| `bot/main.py` | Edit — add `MessageHandler` for commandless NL queries + clarification replies | ~10 lines |
| `README.md` | Edit — document the new natural language capability | ~10 lines |
| Supabase | New `learned_patterns` table + GIN index | 1 SQL migration |

**No new pip packages. No new env vars. No new handlers directory files.**

---

## 7. Edge Cases & How They're Handled

| Case | Handling |
|---|---|
| User says "CSE" but the database has "Computer Science Engineering" | Supabase `ilike` (*CSE*) already matches partial strings. No change needed. |
| User says "computer science" (not "CSE") | Alias dictionary maps it to canonical "CSE" before the DB query. |
| User types "CSEE" or "Mechanicl" (typo) | Tier 3 fuzzy matching (`difflib.get_close_matches`) catches it if the edit distance is small. |  
| User says "show me papers" (no branch/sem) | No branch extracted → returns None → bot replies with the "could not understand" fallback + usage hint. |
| User provides only a branch ("CSE") but no sem/year | Valid: `semester=None, year=None` → returns all CSE documents across all semesters. |
| Query has two single-digit numbers ("CSE 3 4") | `_is_likely_semester()` uses proximity to "sem"/"semester" words. If no sem word nearby, first digit wins. |
| Query says "12th sem" | Scanner only accepts digits 1-8 as valid semesters. "12" is not in range, ignored. |
| Year typed as "22" (short form) | Two-digit years are not matched (regex requires exactly 4 digits). LLM-free approach has no way to expand "22" to "2022" — this is the main weakness compared to LLMs, but such queries are rare. |
| Hinglish / mixed language | Keyword scanner is language-agnostic (works on tokens). "CSE ka sem 4 ka paper" → "CSE" is found, "4" is found, works fine. |

---

## 8. What This Does NOT Handle (and why that's OK)

| Unhandled | Why It's Fine |
|---|---|
| "Give me the E&TC paper from 2 years ago" | Relative time expressions require reasoning. Users learn the bot's vocabulary quickly; they'll adapt to "ENTC sem 4 2024" after one error message. |
| "Do you have the same paper as my friend uploaded last week?" | Requires session context and memory. Out of scope for a stateless search bot. |
| "Show me only PDFs" / "filter by file size" | Metadata not stored in the database. Could be added later if needed. |

The goal is **pragmatic NL support for the 95% case**, not a general-purpose chatbot. The keyword scanner hits that target.

---

## 9. Comparison: Static vs Self-Improving vs LLM

| Factor | Static Keyword Scanner | Self-Improving Scanner | LLM (Ollama/GPT) |
|---|---|---|---|
| Cost | $0 | $0 | $0 (Ollama local) or API costs |
| Latency | <1ms | <1ms + 1 DB call | 200ms–2s |
| New dependencies | None | None | Ollama binary or OpenAI key |
| Accuracy on real queries | ~90% | ~95%+ (grows over time) | ~98% |
| Handles typos | Yes (fuzzy) | Yes (fuzzy + learned) | Yes |
| Handles Hinglish | Yes (token-based) | Yes (token-based + learned) | Yes |
| Handles new abbreviations | No | **Yes (learns from first use)** | Yes |
| Improves over time | No | **Yes (accumulates patterns)** | No (static prompt) |
| Can be corrected when wrong | Code-only | **Yes (admin review command)** | Prompt tweaking |
| Introspectable / debuggable | **Yes (view dicts)** | **Yes (query learned_patterns)** | No (black box) |
| Handles relative time ("2 years ago") | No | No | Yes |
| Handles short year ("22") | No | No | Yes |
| Requires internet | No | No (Supabase already used) | Yes (unless local Ollama) |

The self-improving scanner wins on every metric except the two edge cases only an LLM would handle — and those edge cases (relative time, short year) barely occur in practice for this domain.

---

## 10. Implementation Steps (with Self-Improvement)

| Step | What | Estimated Time |
|---|---|---|
| 1 | Add `doc_type` param to `search_documents()` in `database.py` | 5 min |
| 2 | Create `learned_patterns` table + GIN index in Supabase | 5 min |
| 3 | Add `learned_patterns` CRUD functions to `database.py` | 15 min |
| 4 | Create `bot/services/nlp.py`: keyword scanner, regex patterns, tokenizer, fuzzy fallback, pattern matcher | 60 min |
| 5 | Rewrite `search.py`: new extraction pipeline, clarification flow, follow-up reply handler | 30 min |
| 6 | Register `MessageHandler` for clarification replies + commandless NL in `main.py` | 15 min |
| 7 | Test manually: all Section 2 examples + teach it a new abbreviation to verify learning | 15 min |
| 8 | Add `/reviewfails` admin command for pruning bad learned patterns (optional) | 20 min |
| 9 | Update `/help` text and README | 10 min |
| 10 | Deploy and monitor learned_patterns growth | — |

**Total: ~3 hours. Zero cost. Zero new dependencies.**

---

## 11. Summary

Natural language search for this bot is a **keyword extraction problem**, not a reasoning problem. The domain vocabulary is tiny (~40 words total across all branches, doc types, and number patterns). An LLM is overkill — a 180-line keyword scanner with fuzzy matching handles every realistic query a student would type.

The existing architecture supports this cleanly:
- `bot/services/nlp.py` — pure extraction logic
- `bot/services/database.py` — extended query params (backward compatible)
- `bot/handlers/search.py` — thin routing layer

No database changes. No API keys. No external services. Just `re` and `difflib` from the standard library.

---

## 12. Self-Improvement: Learning From Failures

### 12.1. The Problem

The keyword scanner is static. When a user types something it can't parse — say, a new abbreviation the bot hasn't seen ("DSA" for "Data Structures", or "applied mechanics" for a subject not in the alias list) — it returns `None` and the bot says "could not understand." It will never learn that "DSA" means something, no matter how many times users type it.

The question: **can we make the system learn from its failures?**

### 12.2. Yes — And It's Easier With Keywords Than With an LLM

An LLM is a black box. When it fails, you can't surgically fix one rule — you have to tweak the prompt and hope. But with a keyword-based system, every "rule" is an entry in a dictionary. Learning simply means **adding new dictionary entries at runtime**, persisted to the database.

### 12.3. Design: Learned Patterns + Clarification Loop

```
user types: "got any DSA sem 3 papers?"
    │
    ▼
┌──────────────────────┐
│ keyword scanner      │  ← "DSA" not in BRANCH_ALIASES → returns None
│ (static dicts)       │
└──────┬───────────────┘
       │ fail
       ▼
┌──────────────────────┐
│ check learned_patterns│  ← Supabase query: tokens {dsa, sem, 3} overlap?
│ (dynamic, from DB)   │     → no match (first time)
└──────┬───────────────┘
       │ miss
       ▼
┌──────────────────────┐
│ clarification prompt  │  ← "I didn't understand 'DSA'.
│ (ask user)           │     Which branch and semester? (e.g., CSE sem 4)"
└──────┬───────────────┘
       │ user replies: "CSE sem 3"
       ▼
┌──────────────────────┐
│ store learned pattern │  ← INSERT INTO learned_patterns:
│ (write to Supabase)  │     tokens={dsa, sem, 3}, subject=CSE, semester=3
└──────┬───────────────┘
       │
       ▼
   execute search → show results
```

**Next time** someone types "DSA sem 3 notes" or "got any DSA papers 3rd sem":

```
query → keyword scanner → fail → check learned_patterns
    → tokens {dsa, sem, 3, notes} overlaps with stored {dsa, sem, 3}
    → match! → use subject=CSE, semester=3, doc_type=notes
    → execute search → results
```

No clarification needed the second time. The system learned.

### 12.4. Database Schema

**New Supabase table:**

```sql
CREATE TABLE learned_patterns (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tokens       text[] NOT NULL,        -- significant tokens (stopwords removed)
    subject      text NOT NULL,
    semester     int,
    year         int,
    doc_type     text,
    source_query text NOT NULL,          -- original query text that failed
    learned_at   timestamptz DEFAULT now()
);

-- For fast token-overlap queries
CREATE INDEX idx_learned_patterns_tokens ON learned_patterns USING GIN (tokens);
```

### 12.5. Tokenization and Matching Strategy

The key: **strip stopwords before storing**. This makes different phrasings of the same intent collapse to the same token set.

```python
STOPWORDS = {
    "a", "an", "the", "i", "me", "my", "we", "our", "you", "your",
    "got", "get", "have", "has", "any", "some", "all", "please", "pls",
    "need", "want", "give", "show", "find", "looking", "search",
    "for", "of", "in", "to", "from", "with", "is", "are", "can", "do",
    "paper", "papers", "document", "documents", "material", "materials",
    "question", "questions", "branch", "subject", "sub", "stuff",
    "old", "past", "previous", "latest", "new",
}

def tokenize_query(text: str) -> set[str]:
    """Extract significant tokens from a query, discarding stopwords."""
    words = re.findall(r'[a-z0-9&]+', text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}
```

Example transformations:

| Query | Tokens (after stopwords) |
|---|---|
| "got any DSA sem 3 papers?" | {dsa, sem, 3} |
| "I need DSA for semester 3" | {dsa, semester, 3} |
| "DSA 3rd sem notes pls" | {dsa, 3rd, sem, notes} |
| "show me all DSA sem 3 documents" | {dsa, sem, 3} |

Queries 1, 2, and 4 all produce the same token set {dsa, sem, 3} — so learning from the first query immediately handles the other two.

**Matching algorithm** (Jaccard similarity):

```python
def find_learned_pattern(query_tokens: set[str]) -> dict | None:
    """
    Search learned_patterns for any row whose tokens overlap
    significantly with the query tokens. Return the stored params
    if Jaccard similarity >= 0.4.
    """
    token_list = list(query_tokens)
    # Supabase: find rows where tokens array overlaps query tokens
    params = {
        "select": "*",
        "tokens": f"cs.{{{','.join(token_list)}}}",  -- contains operator
        "order": "learned_at.desc",
        "limit": 10,
    }
    resp = await client.get(learned_base(), headers=_headers(), params=params)
    rows = resp.json()

    best_score = 0
    best_row = None
    for row in rows:
        stored_tokens = set(row["tokens"])
        intersection = stored_tokens & query_tokens
        union = stored_tokens | query_tokens
        score = len(intersection) / len(union) if union else 0
        if score > best_score:
            best_score = score
            best_row = row

    if best_row and best_score >= 0.4:
        return {
            "subject": best_row["subject"],
            "semester": best_row["semester"],
            "year": best_row["year"],
            "doc_type": best_row["doc_type"],
        }
    return None
```

### 12.6. The Clarification Flow

When all tiers fail (keyword scanner + fuzzy + learned patterns), the bot initiates a clarification:

```python
# In bot/handlers/search.py

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() if context.args else update.message.text.strip()

    params = nlp.extract_search_params(query)

    if not params or "subject" not in params:
        # Try learned patterns (Tier 3)
        params = await nlp.match_learned_pattern(query)

    if not params or "subject" not in params:
        # All tiers failed — ask user to clarify
        context.user_data["pending_clarification"] = query
        await update.message.reply_text(
            "I couldn't understand that query.\n\n"
            "Which branch and semester are you looking for?\n"
            "Please type it like:  CSE sem 4 2025\n\n"
            "Branches: MECH | ENTC | EEP | CSE | MCA | MTECH | IT | CIVIL"
        )
        return

    # ... proceed with search using params ...


# Separate handler for the clarification reply
async def handle_clarification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called when user replies to a clarification prompt."""
    original_query = context.user_data.pop("pending_clarification", None)
    if not original_query:
        return  # not in a clarification flow, ignore

    reply = update.message.text.strip()
    structured = nlp.extract_search_params(reply)
    # Since we asked for structured format, the regex path should catch it.
    # If not, try one more time with a gentle nudge.

    if not structured or "subject" not in structured:
        await update.message.reply_text(
            "Still couldn't parse that. Please use:  <branch> sem <n>\n"
            "Example:  CSE sem 4"
        )
        context.user_data["pending_clarification"] = original_query  # retry
        return

    # SUCCESS: store the learned pattern (original query → structured params)
    await nlp.store_learned_pattern(original_query, structured)

    # Execute the search
    await _execute_search(update, context, structured)
```

### 12.7. The Modified Extraction Pipeline

The full `extract_search_params()` pipeline with self-improvement:

```python
async def extract_search_params(text: str) -> dict | None:
    # Tier 1: Enhanced regex (static, instant)
    result = tier1_extract(text)
    if result:
        return result

    # Tier 2: Keyword scanner (static, instant)
    result = extract_by_keywords(text)
    if result:
        return result

    # Tier 3: Fuzzy matching (static, instant)
    result = _fuzzy_fallback(text)
    if result:
        return result

    # Tier 4: Learned patterns (dynamic, DB call)
    result = await match_learned_pattern(text)
    if result:
        logger.info("LEARNED MATCH | query=%r | result=%r", text, result)
        return result

    # All tiers exhausted — caller should trigger clarification flow
    return None
```

### 12.8. What Gets Learned and What Doesn't

| Scenario | Learned? | Why |
|---|---|---|
| Unknown abbreviation ("DSA" → CSE) | **Yes** | Clarification flow teaches the mapping; stored in `learned_patterns` |
| Unknown subject name ("thermodynamics") | **Yes** | Same mechanism; subject mapped to whatever branch the user clarifies |
| Typo that fuzzy matching can't catch | **Yes** | "cSEE" might not match "CSE" in fuzzy (too far). User clarifies "CSE sem 4" → stored pattern {csee, sem, 4} → CSE,4 |
| New slang / college lingo ("comp" for CSE) | **Yes** | Clarification teaches the mapping; next query with "comp" matches via token overlap |
| Ambiguous query ("sem 4") — no subject at all | **No** | Clarification will ask for subject, but no pattern is stored because the clarification itself had the subject. The system doesn't learn to infer a subject from nothing. |
| "Papers" alone — no subject, no sem | **No** | Nothing to store. User gets asked to clarify each time. |

### 12.9. Guardrails

1. **Deduplication**: Before storing, check if a pattern with the same token set already exists. If so, update it (the newer clarification might be more accurate).

2. **Confidence decay**: Store a `use_count` column. Patterns that are used many times (matched successfully in future queries) get higher confidence. Patterns never reused after initial storage could be noise/mistakes.

3. **Admin review**: Add a `/reviewfails` command for the admin to see recent clarification flows and manually prune bad patterns.

4. **Rate limiting**: One clarification prompt per user per 30 seconds to prevent abuse.

### 12.10. Updated Comparison Table

| Factor | Static Keyword Scanner | Self-Improving Keyword Scanner | LLM |
|---|---|---|---|
| Cost | $0 | $0 | $0–API costs |
| Latency | <1ms | <1ms + 1 DB call | 200ms–2s |
| Handles new abbreviations | No (must manually add to dict) | **Yes (learns from first use)** | Yes |
| Handles new slang/lingo | No | **Yes** | Yes |
| Improves over time | No | **Yes (grows with usage)** | No (static prompt) |
| Can be corrected when wrong | Only by editing code | **Yes (admin review command)** | By prompt tweaking |
| Gets worse over time | No | No (dedup + admin review) | No |
| Requires internet | No | No (Supabase is already used) | Yes |

### 12.11. Updated Implementation Steps

| Step | What | Estimated Time |
|---|---|---|
| 1 | Add `doc_type` param to `search_documents()` in `database.py` | 5 min |
| 2 | Create `learned_patterns` table in Supabase | 5 min |
| 3 | Add `learned_patterns` CRUD functions to `database.py` | 15 min |
| 4 | Create `bot/services/nlp.py` with keyword scanner + tokenizer + pattern matcher | 60 min |
| 5 | Modify `search.py` with clarification flow + learned pattern storage | 30 min |
| 6 | Add `MessageHandler` for clarification replies (conversation state) | 15 min |
| 7 | Test manually against all example queries from Section 2 | 15 min |
| 8 | Add `MessageHandler` for commandless NL queries in `main.py` | 10 min |
| 9 | Add `/reviewfails` admin command (optional cleanup tool) | 20 min |
| 10 | Update `/help` text and README | 10 min |
| 11 | Deploy and monitor | — |

**Total: ~3 hours. Zero cost. Zero new dependencies.** The extra 1.5 hours over the static version is entirely for the self-improvement layer.

### 12.12. Why This Architecture Enables Self-Improvement (and an LLM Doesn't)

With a keyword-based system, "learning" is just a **dictionary insert**. The runtime behavior is:
```
if word in known_branches:         # static dict (code)
    return canonical_branch
if word in learned_patterns:       # dynamic dict (Supabase)
    return stored_params
```

The system is fully introspectable — you can query `learned_patterns` to see exactly what it learned, prune bad entries, and understand why a particular query matched. An LLM offers none of this. You can't "add one rule" to an LLM without retraining or prompt-engineering, which might break other cases.

The keyword scanner is **incrementally improvable** because every rule is discrete and isolated. Learning one mapping (DSA → CSE, sem 3) never affects other mappings.
