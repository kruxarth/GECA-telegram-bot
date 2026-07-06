import logging
import os

import httpx

logger = logging.getLogger(__name__)

DOC_TYPE_LABELS = {
    "class_test_1": "Class Test 1",
    "class_test_2": "Class Test 2",
    "end_sem": "End Sem PYQ",
    "bundle": "Paper Bundle",
    "notes": "Notes",
}


def _headers() -> dict:
    key = os.environ["SUPABASE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/documents"


async def insert_document(data: dict) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_base(), headers=_headers(), json=data)
        resp.raise_for_status()
        return resp.json()[0]


async def search_documents(
    subject: str,
    semester: int | None = None,
    year: int | None = None,
    doc_type: str | None = None,
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


async def get_document(doc_id: str) -> dict | None:
    params = {"select": "*", "id": f"eq.{doc_id}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()
        return data[0] if data else None


# --- Uploader allowlist ---

def _uploaders_base() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/uploaders"


async def is_uploader(user_id: int) -> bool:
    params = {"select": "user_id", "user_id": f"eq.{user_id}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_uploaders_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return len(resp.json()) > 0


async def add_uploader(user_id: int) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_uploaders_base(), headers=_headers(), json={"user_id": user_id})
        resp.raise_for_status()


async def remove_uploader(user_id: int) -> bool:
    """Returns True if the user was found and removed, False if they weren't in the list."""
    params = {"user_id": f"eq.{user_id}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(_uploaders_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return len(resp.json()) > 0


async def list_uploaders() -> list[dict]:
    params = {"select": "*", "order": "added_at.asc"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_uploaders_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


# --- Learned patterns (self-improving NL) ---

def _learned_base() -> str:
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/learned_patterns"


async def search_learned_patterns(tokens: list[str]) -> list[dict]:
    """Find learned patterns whose token arrays overlap with the query tokens."""
    token_param = "{" + ",".join(tokens) + "}"
    params = {
        "select": "*",
        "tokens": f"ov.{token_param}",
        "order": "learned_at.desc",
        "limit": 10,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_learned_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


async def insert_learned_pattern(
    tokens: list[str],
    subject: str,
    source_query: str,
    semester: int | None = None,
    year: int | None = None,
    doc_type: str | None = None,
) -> dict:
    """Store a learned mapping from natural query to structured params."""
    data = {
        "tokens": tokens,
        "subject": subject,
        "source_query": source_query,
    }
    if semester is not None:
        data["semester"] = semester
    if year is not None:
        data["year"] = year
    if doc_type is not None:
        data["doc_type"] = doc_type

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_learned_base(), headers=_headers(), json=data)
        resp.raise_for_status()
        return resp.json()[0]


async def delete_learned_pattern(pattern_id: str) -> bool:
    """Delete a learned pattern by UUID. Returns True if found and removed."""
    params = {"id": f"eq.{pattern_id}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.delete(_learned_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return len(resp.json()) > 0


async def list_learned_patterns() -> list[dict]:
    """List all learned patterns ordered by recency (for admin review)."""
    params = {"select": "*", "order": "learned_at.desc"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_learned_base(), headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()
