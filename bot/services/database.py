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


async def search_documents(subject: str, semester: int, year: int | None) -> list[dict]:
    params = {
        "select": "*",
        "subject": f"ilike.*{subject}*",
        "semester": f"eq.{semester}",
        "order": "uploaded_at.desc",
    }
    if year:
        params["year"] = f"eq.{year}"

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
