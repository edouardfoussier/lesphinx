"""
Enrich characters.json with normalized themes.

Usage:
    python -m scripts.build_themes
    python -m scripts.build_themes --limit 30
    python -m scripts.build_themes --overwrite
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

ALLOWED_THEMES = [
    "science",
    "technology",
    "arts",
    "literature",
    "music",
    "cinema",
    "sports",
    "politics",
    "history",
    "philosophy",
    "business",
    "activism",
    "exploration",
    "religion",
]

THEMES_PROMPT = """You classify famous people into game themes.

Allowed themes (choose 1 to 4 max):
{themes}

Character:
- Name: {name}
- Field: {field}
- Subfield: {subfield}
- Summary FR: {summary_fr}
- Summary EN: {summary_en}
- Facts:
{facts}

Return ONLY valid JSON with this schema:
{{
  "themes": ["theme1", "theme2"]
}}

Rules:
- Only use allowed themes.
- Pick the most relevant themes for a guessing game.
- Include at least 1 theme.
- Prefer specific relevance over broad tagging.
"""


def _load() -> list[dict]:
    return json.loads(CHARACTERS_PATH.read_text())


def _save(characters: list[dict]) -> None:
    CHARACTERS_PATH.write_text(json.dumps(characters, indent=2, ensure_ascii=False))


def _has_themes(char: dict) -> bool:
    themes = char.get("themes")
    return isinstance(themes, list) and len(themes) > 0


def _sanitize(themes: list[str], field: str) -> list[str]:
    normalized = []
    for t in themes:
        key = str(t).strip().lower()
        if key in ALLOWED_THEMES and key not in normalized:
            normalized.append(key)
    if not normalized and field in ALLOWED_THEMES:
        normalized.append(field)
    if not normalized:
        normalized.append("history")
    return normalized[:4]


async def _infer_themes(client: Mistral, char: dict) -> list[str] | None:
    attrs = char.get("attributes", {})
    facts = char.get("facts", [])
    summary = char.get("summary") or {}
    field = str(attrs.get("field", "")).strip().lower()
    subfield = str(attrs.get("subfield", "")).strip().lower()
    prompt = THEMES_PROMPT.format(
        themes=", ".join(ALLOWED_THEMES),
        name=char.get("name", ""),
        field=field,
        subfield=subfield,
        summary_fr=str(summary.get("fr", ""))[:600],
        summary_en=str(summary.get("en", ""))[:600],
        facts="\n".join(f"- {f}" for f in facts[:8]) or "- No facts",
    )

    try:
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout_ms=20000,
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        raw = data.get("themes", [])
        if not isinstance(raw, list):
            raw = []
        return _sanitize([str(x) for x in raw], field)
    except Exception:
        if field in ALLOWED_THEMES:
            return [field]
        return None


async def _run(args: argparse.Namespace) -> None:
    api_key = args.api_key or os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise RuntimeError("Missing MISTRAL_API_KEY")

    chars = _load()
    if args.limit and args.limit > 0:
        chars = chars[: args.limit]

    sem = asyncio.Semaphore(args.concurrency)
    client = Mistral(api_key=api_key)
    updated = 0
    skipped = 0
    failed = 0
    total = len(chars)
    done = 0

    async def one(char: dict) -> None:
        nonlocal updated, skipped, failed, done

        if _has_themes(char) and not args.overwrite:
            skipped += 1
            done += 1
            print(f"[{done}/{total}] SKIP {char.get('name')}")
            return

        async with sem:
            themes = await _infer_themes(client, char)

        if themes:
            char["themes"] = themes
            updated += 1
            status = "OK"
        else:
            failed += 1
            status = "FAIL"
        done += 1
        print(f"[{done}/{total}] {status:4} {char.get('name')}")

        if done % 20 == 0:
            _save(chars)

    await asyncio.gather(*(one(c) for c in chars))
    _save(chars)
    print("\nDone.")
    print(f"  updated: {updated}")
    print(f"  skipped: {skipped}")
    print(f"  failed:  {failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized themes in characters.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
