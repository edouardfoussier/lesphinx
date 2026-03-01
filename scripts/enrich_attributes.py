#!/usr/bin/env python3
"""Deterministically enrich character attributes from existing facts.

Extracts birth_year, death_year, era, has_nobel_prize, has_oscar,
and primary_language from the facts and attributes already present
in characters.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "lesphinx" / "data" / "characters.json"


def extract_year(text: str, keyword: str) -> int | None:
    pattern = rf"{keyword}\D*(\d{{4}})"
    m = re.search(pattern, text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def classify_era(birth_year: int | None) -> str:
    if birth_year is None:
        return "unknown"
    if birth_year < 500:
        return "ancient"
    if birth_year < 1400:
        return "medieval"
    if birth_year < 1600:
        return "renaissance"
    if birth_year < 1900:
        return "modern"
    return "contemporary"


def enrich_character(char: dict) -> dict:
    attrs = char.get("attributes", {})
    facts = char.get("facts", [])
    all_text = " ".join(facts).lower()

    # Birth year
    if "birth_year" not in attrs:
        by = None
        for f in facts:
            by = extract_year(f, r"(?:born|ne|nee|naissance)")
            if by:
                break
        if by is None:
            for f in facts:
                m = re.search(r"\((\d{4})\s*[-–]\s*", f)
                if m:
                    by = int(m.group(1))
                    break
        if by:
            attrs["birth_year"] = by

    # Death year
    if "death_year" not in attrs:
        dy = None
        for f in facts:
            dy = extract_year(f, r"(?:died|mort|morte|deces|decede)")
            if dy:
                break
        if dy is None:
            for f in facts:
                m = re.search(r"[-–]\s*(\d{4})\)", f)
                if m:
                    dy = int(m.group(1))
                    break
        if dy:
            attrs["death_year"] = dy

    # Era
    if "era" not in attrs or attrs["era"] == "unknown":
        attrs["era"] = classify_era(attrs.get("birth_year"))

    # Nobel prize
    if "has_nobel_prize" not in attrs:
        attrs["has_nobel_prize"] = bool(re.search(r"nobel", all_text))

    # Oscar
    if "has_oscar" not in attrs:
        attrs["has_oscar"] = bool(re.search(r"oscar|academy award", all_text))

    # Primary language
    if "primary_language" not in attrs:
        nationality = attrs.get("nationality", "").lower()
        lang_map = {
            "french": "french", "francais": "french", "française": "french",
            "american": "english", "british": "english", "english": "english",
            "australian": "english", "canadian": "english",
            "german": "german", "allemand": "german",
            "spanish": "spanish", "espagnol": "spanish",
            "italian": "italian", "italien": "italian",
            "portuguese": "portuguese",
            "russian": "russian", "russe": "russian",
            "chinese": "chinese", "chinois": "chinese",
            "japanese": "japanese", "japonais": "japanese",
            "indian": "hindi",
        }
        for key, lang in lang_map.items():
            if key in nationality:
                attrs["primary_language"] = lang
                break
        else:
            attrs["primary_language"] = "unknown"

    char["attributes"] = attrs
    return char


def main() -> None:
    data = json.loads(DATA_PATH.read_text())
    enriched = [enrich_character(c) for c in data]
    DATA_PATH.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    print(f"Enriched {len(enriched)} characters.")


if __name__ == "__main__":
    main()
