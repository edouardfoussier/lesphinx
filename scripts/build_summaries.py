"""
Enrich characters.json with bilingual educational summaries.

Usage:
    python -m scripts.build_summaries
    python -m scripts.build_summaries --limit 20
    python -m scripts.build_summaries --overwrite
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from mistralai import Mistral


ROOT = Path(__file__).parent.parent
CHARACTERS_PATH = ROOT / "lesphinx" / "data" / "characters.json"


SUMMARY_PROMPT = """You are writing short educational bios for a guessing game.

Character:
- Name: {name}
- Difficulty: {difficulty}
- Attributes: {attributes_json}
- Facts:
{facts_text}

Return ONLY valid JSON with this exact shape:
{{
  "fr": "2-3 short pedagogical sentences in French, plain text.",
  "en": "2-3 short educational sentences in English, plain text."
}}

Constraints:
- Keep both versions factual and easy to understand.
- Mention why this person is notable.
- If relevant, include period/field/context.
- Do NOT invent uncertain facts.
- No markdown, no bullet points, no quotes around names unless natural.
"""


def _load_characters() -> list[dict]:
    return json.loads(CHARACTERS_PATH.read_text())


def _save_characters(characters: list[dict]) -> None:
    CHARACTERS_PATH.write_text(json.dumps(characters, indent=2, ensure_ascii=False))


def _has_summary(character: dict) -> bool:
    summary = character.get("summary")
    if not isinstance(summary, dict):
        return False
    fr = summary.get("fr")
    en = summary.get("en")
    return isinstance(fr, str) and len(fr.strip()) > 20 and isinstance(en, str) and len(en.strip()) > 20


async def _generate_summary(client: Mistral, character: dict) -> dict | None:
    facts = character.get("facts") or []
    facts_text = "\n".join(f"- {f}" for f in facts[:12]) or "- No facts provided."
    prompt = SUMMARY_PROMPT.format(
        name=character.get("name", ""),
        difficulty=character.get("difficulty", "medium"),
        attributes_json=json.dumps(character.get("attributes", {}), ensure_ascii=False),
        facts_text=facts_text,
    )

    try:
        resp = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout_ms=30000,
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        fr = str(data.get("fr", "")).strip()
        en = str(data.get("en", "")).strip()
        if len(fr) < 20 or len(en) < 20:
            return None
        return {"fr": fr, "en": en}
    except Exception:
        return None


async def _run(args: argparse.Namespace) -> None:
    api_key = args.api_key or os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing MISTRAL_API_KEY. Set .env or pass --api-key")

    characters = _load_characters()
    if args.limit and args.limit > 0:
        characters = characters[: args.limit]

    client = Mistral(api_key=api_key)
    sem = asyncio.Semaphore(args.concurrency)
    lock = asyncio.Lock()

    updated = 0
    skipped = 0
    failed = 0
    processed = 0
    total = len(characters)

    async def one(idx: int, c: dict) -> None:
        nonlocal updated, skipped, failed, processed

        if _has_summary(c) and not args.overwrite:
            async with lock:
                skipped += 1
                processed += 1
                print(f"[{processed}/{total}] SKIP {c.get('name')}")
            return

        async with sem:
            summary = await _generate_summary(client, c)

        async with lock:
            if summary is None:
                failed += 1
                processed += 1
                print(f"[{processed}/{total}] FAIL {c.get('name')}")
            else:
                c["summary"] = summary
                updated += 1
                processed += 1
                print(f"[{processed}/{total}] OK   {c.get('name')}")

            # Checkpoint save every 10 processed items.
            if processed % 10 == 0:
                _save_characters(characters)

    await asyncio.gather(*(one(i, c) for i, c in enumerate(characters)))
    _save_characters(characters)

    print("\nDone.")
    print(f"  updated: {updated}")
    print(f"  skipped: {skipped}")
    print(f"  failed:  {failed}")
    print(f"  file: {CHARACTERS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate bilingual summaries for characters.json")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N characters")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate existing summaries")
    parser.add_argument("--concurrency", type=int, default=6, help="Concurrent API calls")
    parser.add_argument("--api-key", type=str, default=None, help="Optional Mistral API key")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
