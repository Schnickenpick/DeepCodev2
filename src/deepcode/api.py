import json
import httpx
from typing import AsyncIterator

BASE = "https://unlimited-ai-proxy.sportsmoments97.workers.dev"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://unlimited-ai-2jw.pages.dev",
    "Referer": "https://unlimited-ai-2jw.pages.dev/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
}


async def stream_chat(message: str, model: str) -> AsyncIterator[dict]:
    body = {"message": message, "model": model}
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{BASE}/api/chat", json=body, headers=HEADERS) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue


async def stream_merge(message: str) -> AsyncIterator[dict]:
    body = {"message": message}
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream("POST", f"{BASE}/api/merge", json=body, headers=HEADERS) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue


async def stream_search(query: str) -> AsyncIterator[dict]:
    body = {"query": query}
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{BASE}/api/search", json=body, headers=HEADERS) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue


async def extract_memory(conversation: list[dict], existing: list[str]) -> list[str]:
    body = {"conversation": conversation, "existingMemory": existing}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{BASE}/api/memory", json=body, headers=HEADERS)
            data = resp.json()
            return data.get("facts", [])
    except Exception:
        return []
