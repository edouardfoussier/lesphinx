#!/usr/bin/env python3
"""Enrich characters with physical attributes and notable works using Mistral LLM.

Adds: hair_color, ethnicity, height_category, notable_works
Preserves existing attributes -- only fills in missing ones.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mistralai import Mistral

DATA_PATH = Path(__file__).resolve().parent.parent / "lesphinx" / "data" / "characters.json"

ENRICHMENT_PROMPT = """Given the famous person described below, provide additional attributes.
Respond ONLY with a JSON object containing these fields:

- "hair_color": one of "black", "brown", "blond", "red", "gray", "white", "bald", "unknown"
  (their most commonly known hair color, or at the peak of their fame)
- "ethnicity": one of "european", "african", "east_asian", "south_asian", "middle_eastern", "latino", "mixed", "unknown"
- "height_category": one of "tall", "average", "short", "unknown"
  (tall = >185cm/6'1", short = <170cm/5'7", average = in between)
- "notable_works": list of 3-5 most famous works, achievements, or creations
  (films, songs, books, discoveries, laws, artworks, etc. -- things people would recognize)

Person info:
- Name: {name}
- Field: {field}
- Nationality: {nationality}

Known facts:
{facts}

Return ONLY valid JSON. Example:
{{"hair_color": "brown", "ethnicity": "european", "height_category": "tall", "notable_works": ["Titanic", "Inception", "The Revenant"]}}
"""


async def enrich_one(client: Mistral, char: dict, model: str) -> dict:
    attrs = char.get("attributes", {})
    needs_enrichment = (
        "hair_color" not in attrs
        or "ethnicity" not in attrs
        or "height_category" not in attrs
        or "notable_works" not in attrs
    )
    if not needs_enrichment:
        return char

    facts = char.get("facts", [])
    facts_text = "\n".join(f"- {f}" for f in facts[:8])

    prompt = ENRICHMENT_PROMPT.format(
        name=char["name"],
        field=attrs.get("field", "unknown"),
        nationality=attrs.get("nationality", "unknown"),
        facts=facts_text,
    )

    try:
        response = await client.chat.complete_async(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300,
        )
        data = json.loads(response.choices[0].message.content.strip())

        valid_hair = {"black", "brown", "blond", "red", "gray", "white", "bald", "unknown"}
        valid_eth = {"european", "african", "east_asian", "south_asian", "middle_eastern", "latino", "mixed", "unknown"}
        valid_height = {"tall", "average", "short", "unknown"}

        if "hair_color" not in attrs:
            h = data.get("hair_color", "unknown").lower()
            attrs["hair_color"] = h if h in valid_hair else "unknown"

        if "ethnicity" not in attrs:
            e = data.get("ethnicity", "unknown").lower()
            attrs["ethnicity"] = e if e in valid_eth else "unknown"

        if "height_category" not in attrs:
            ht = data.get("height_category", "unknown").lower()
            attrs["height_category"] = ht if ht in valid_height else "unknown"

        if "notable_works" not in attrs:
            works = data.get("notable_works", [])
            if isinstance(works, list):
                attrs["notable_works"] = [str(w) for w in works[:5]]
            else:
                attrs["notable_works"] = []

        char["attributes"] = attrs
    except Exception as exc:
        print(f"  WARN: Failed to enrich {char['name']}: {exc}")

    return char


async def main() -> None:
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        try:
            from lesphinx.config.settings import settings
            api_key = settings.mistral_api_key
        except Exception:
            pass
    if not api_key:
        print("ERROR: MISTRAL_API_KEY not set")
        sys.exit(1)

    model = "mistral-large-latest"
    client = Mistral(api_key=api_key)

    data = json.loads(DATA_PATH.read_text())
    total = len(data)

    to_enrich = [c for c in data if "hair_color" not in c.get("attributes", {})]
    print(f"Total characters: {total}, need enrichment: {len(to_enrich)}")

    batch_size = 5
    for i in range(0, len(to_enrich), batch_size):
        batch = to_enrich[i:i + batch_size]
        tasks = [enrich_one(client, c, model) for c in batch]
        await asyncio.gather(*tasks)
        done = min(i + batch_size, len(to_enrich))
        print(f"  Enriched {done}/{len(to_enrich)}")

    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Saved {total} characters to {DATA_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
