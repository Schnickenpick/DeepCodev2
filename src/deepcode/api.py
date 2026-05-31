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
    async with httpx.AsyncClient(timeout=300) as client:
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


async def extract_memory_split(conversation: list[dict], global_md: str, project_md: str, user_md: str) -> dict:
    """Extract facts and classify into global/project/user buckets."""
    turn_text = ""
    for msg in conversation[-2:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        turn_text += f"{role.upper()}: {content}\n\n"

    prompt = (
        "You are a memory extraction assistant. Read the conversation turn below and extract NEW facts worth remembering.\n\n"
        "Classify each fact into exactly one of three categories:\n"
        "- GLOBAL: general personal preferences, communication style, name, background — applies everywhere\n"
        "- PROJECT: specific to the current project/codebase/task — not useful in other projects\n"
        "- USER: identity facts (name, job, location, skills) — goes in USER.md\n\n"
        f"Already in global memory (skip duplicates):\n{global_md or '(empty)'}\n\n"
        f"Already in project memory (skip duplicates):\n{project_md or '(empty)'}\n\n"
        f"Already in user memory (skip duplicates):\n{user_md or '(empty)'}\n\n"
        f"Conversation:\n{turn_text}\n"
        "Respond with JSON only, no markdown:\n"
        '{"global": ["fact1", "fact2"], "project": ["fact3"], "user": ["fact4"]}\n'
        "Only include facts that are genuinely new and worth storing. Empty arrays are fine."
    )
    try:
        result = ""
        async for chunk in stream_chat(prompt, "claude-haiku-4-5-20251001"):
            if chunk.get("delta"):
                result += chunk["delta"]
            if chunk.get("done"):
                break
        result = result.strip()
        # strip markdown code fences if present
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        data = json.loads(result)
        return {
            "global": [str(f) for f in data.get("global", [])],
            "project": [str(f) for f in data.get("project", [])],
            "user": [str(f) for f in data.get("user", [])],
        }
    except Exception:
        return {"global": [], "project": [], "user": []}


async def compress_memory(content: str, label: str) -> str:
    """LLM-compress a memory file — deduplicate, merge, trim stale facts."""
    prompt = (
        f"You are compressing a {label} memory file for an AI assistant.\n\n"
        "Rules:\n"
        "- Merge duplicate or overlapping facts into one\n"
        "- Remove facts that are clearly outdated or superseded\n"
        "- Keep facts that are genuinely useful for future conversations\n"
        "- Output ONLY a tight bullet list (- fact), no headers, no explanation\n"
        "- Be aggressive: cut anything that isn't clearly useful\n\n"
        f"Current memory:\n{content}\n\n"
        "Compressed memory:"
    )
    try:
        result = ""
        async for chunk in stream_chat(prompt, "claude-haiku-4-5-20251001"):
            if chunk.get("delta"):
                result += chunk["delta"]
            if chunk.get("done"):
                break
        return result.strip()
    except Exception:
        return content
