"""
Build the characters database using a curated list + Mistral enrichment.

Usage:
    python -m scripts.build_characters [--skip-enrichment]
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from mistralai import Mistral

OUTPUT_PATH = Path(__file__).parent.parent / "lesphinx" / "data" / "characters.json"

# Curated list: (name, difficulty, field_hint)
# easy = universally known, medium = well-known, hard = niche
CURATED_PEOPLE: list[tuple[str, str, str]] = [
    # --- EASY (universally famous) ---
    ("Albert Einstein", "easy", "science"),
    ("Leonardo da Vinci", "easy", "arts"),
    ("Napoleon Bonaparte", "easy", "politics"),
    ("William Shakespeare", "easy", "literature"),
    ("Cleopatra", "easy", "politics"),
    ("Michael Jackson", "easy", "music"),
    ("Marilyn Monroe", "easy", "cinema"),
    ("Cristiano Ronaldo", "easy", "sports"),
    ("Queen Elizabeth II", "easy", "politics"),
    ("Mozart", "easy", "music"),
    ("Pablo Picasso", "easy", "arts"),
    ("Charles Darwin", "easy", "science"),
    ("Mahatma Gandhi", "easy", "politics"),
    ("Martin Luther King Jr.", "easy", "politics"),
    ("Elvis Presley", "easy", "music"),
    ("Nelson Mandela", "easy", "politics"),
    ("Walt Disney", "easy", "cinema"),
    ("Muhammad Ali", "easy", "sports"),
    ("Marie Curie", "easy", "science"),
    ("Steve Jobs", "easy", "business"),
    ("Lionel Messi", "easy", "sports"),
    ("Beyonce", "easy", "music"),
    ("Elon Musk", "easy", "business"),
    ("Barack Obama", "easy", "politics"),
    ("Taylor Swift", "easy", "music"),
    ("Leonardo DiCaprio", "easy", "cinema"),
    ("Usain Bolt", "easy", "sports"),
    ("Oprah Winfrey", "easy", "cinema"),
    ("Michael Jordan", "easy", "sports"),
    ("Madonna", "easy", "music"),
    ("Charlie Chaplin", "easy", "cinema"),
    ("Bruce Lee", "easy", "cinema"),
    ("Abraham Lincoln", "easy", "politics"),
    ("Winston Churchill", "easy", "politics"),
    ("Ludwig van Beethoven", "easy", "music"),
    ("Frida Kahlo", "easy", "arts"),
    ("Vincent van Gogh", "easy", "arts"),
    ("Bob Marley", "easy", "music"),
    ("Princess Diana", "easy", "politics"),
    ("Pelé", "easy", "sports"),
    ("Coco Chanel", "easy", "business"),
    ("Stephen Hawking", "easy", "science"),
    ("John Lennon", "easy", "music"),
    ("Serena Williams", "easy", "sports"),
    ("Tom Hanks", "easy", "cinema"),
    ("Rihanna", "easy", "music"),
    ("Zinedine Zidane", "easy", "sports"),
    ("Drake", "easy", "music"),
    ("Dwayne Johnson", "easy", "cinema"),
    ("Eminem", "easy", "music"),
    # --- MEDIUM (well-known) ---
    ("Isaac Newton", "medium", "science"),
    ("Nikola Tesla", "medium", "science"),
    ("Galileo Galilei", "medium", "science"),
    ("Aristotle", "medium", "philosophy"),
    ("Alexander the Great", "medium", "politics"),
    ("Julius Caesar", "medium", "politics"),
    ("Genghis Khan", "medium", "politics"),
    ("Marco Polo", "medium", "exploration"),
    ("Edgar Allan Poe", "medium", "literature"),
    ("Mark Twain", "medium", "literature"),
    ("Celine Dion", "medium", "music"),
    ("Freddie Mercury", "medium", "music"),
    ("David Bowie", "medium", "music"),
    ("Jimi Hendrix", "medium", "music"),
    ("Prince", "medium", "music"),
    ("Adele", "medium", "music"),
    ("Morgan Freeman", "medium", "cinema"),
    ("Meryl Streep", "medium", "cinema"),
    ("Alfred Hitchcock", "medium", "cinema"),
    ("Steven Spielberg", "medium", "cinema"),
    ("Quentin Tarantino", "medium", "cinema"),
    ("Roger Federer", "medium", "sports"),
    ("Rafael Nadal", "medium", "sports"),
    ("Mike Tyson", "medium", "sports"),
    ("Neymar", "medium", "sports"),
    ("Kylian Mbappe", "medium", "sports"),
    ("LeBron James", "medium", "sports"),
    ("Tiger Woods", "medium", "sports"),
    ("Simone Biles", "medium", "sports"),
    ("Thomas Edison", "medium", "science"),
    ("Alexander Graham Bell", "medium", "science"),
    ("Sigmund Freud", "medium", "science"),
    ("Louis Pasteur", "medium", "science"),
    ("Ada Lovelace", "medium", "science"),
    ("Alan Turing", "medium", "science"),
    ("Charles de Gaulle", "medium", "politics"),
    ("Margaret Thatcher", "medium", "politics"),
    ("Che Guevara", "medium", "politics"),
    ("Dalai Lama", "medium", "religion"),
    ("Mother Teresa", "medium", "religion"),
    ("Jeff Bezos", "medium", "business"),
    ("Mark Zuckerberg", "medium", "business"),
    ("Bill Gates", "medium", "business"),
    ("Edith Piaf", "medium", "music"),
    ("Frank Sinatra", "medium", "music"),
    ("Louis Armstrong", "medium", "music"),
    ("Andy Warhol", "medium", "arts"),
    ("Salvador Dali", "medium", "arts"),
    ("Claude Monet", "medium", "arts"),
    ("Agatha Christie", "medium", "literature"),
    ("Ernest Hemingway", "medium", "literature"),
    ("Victor Hugo", "medium", "literature"),
    ("J.K. Rowling", "medium", "literature"),
    ("Stephen King", "medium", "literature"),
    ("Audrey Hepburn", "medium", "cinema"),
    ("Scarlett Johansson", "medium", "cinema"),
    ("Keanu Reeves", "medium", "cinema"),
    ("Robert De Niro", "medium", "cinema"),
    ("Kendrick Lamar", "medium", "music"),
    ("Ariana Grande", "medium", "music"),
    # --- HARD (niche / less mainstream) ---
    ("Rosalind Franklin", "hard", "science"),
    ("Niels Bohr", "hard", "science"),
    ("Max Planck", "hard", "science"),
    ("Erwin Schrodinger", "hard", "science"),
    ("Blaise Pascal", "hard", "science"),
    ("Emmy Noether", "hard", "science"),
    ("Lise Meitner", "hard", "science"),
    ("Ramanujan", "hard", "science"),
    ("Dmitri Mendeleev", "hard", "science"),
    ("Simone de Beauvoir", "hard", "philosophy"),
    ("Jean-Paul Sartre", "hard", "philosophy"),
    ("Friedrich Nietzsche", "hard", "philosophy"),
    ("Immanuel Kant", "hard", "philosophy"),
    ("Fyodor Dostoevsky", "hard", "literature"),
    ("Franz Kafka", "hard", "literature"),
    ("Gabriel Garcia Marquez", "hard", "literature"),
    ("Jorge Luis Borges", "hard", "literature"),
    ("Virginia Woolf", "hard", "literature"),
    ("Albert Camus", "hard", "literature"),
    ("Akira Kurosawa", "hard", "cinema"),
    ("Federico Fellini", "hard", "cinema"),
    ("Ingmar Bergman", "hard", "cinema"),
    ("Andrei Tarkovsky", "hard", "cinema"),
    ("Billie Holiday", "hard", "music"),
    ("Nina Simone", "hard", "music"),
    ("Miles Davis", "hard", "music"),
    ("John Coltrane", "hard", "music"),
    ("Caravaggio", "hard", "arts"),
    ("Gustav Klimt", "hard", "arts"),
    ("Rene Magritte", "hard", "arts"),
    ("Yayoi Kusama", "hard", "arts"),
    ("Roald Amundsen", "hard", "exploration"),
    ("Yuri Gagarin", "hard", "exploration"),
    ("Valentina Tereshkova", "hard", "exploration"),
    ("Ayrton Senna", "hard", "sports"),
    ("Nadia Comaneci", "hard", "sports"),
    ("Jesse Owens", "hard", "sports"),
    ("Bjorn Borg", "hard", "sports"),
    ("Sun Tzu", "hard", "philosophy"),
    ("Hypatia", "hard", "science"),
    ("Boudicca", "hard", "politics"),
    ("Hatshepsut", "hard", "politics"),
    ("Saladin", "hard", "politics"),
    ("Confucius", "hard", "philosophy"),
    ("Avicenna", "hard", "science"),
    ("Grace Hopper", "hard", "science"),
    ("Hedy Lamarr", "hard", "science"),
    ("Rachel Carson", "hard", "science"),
    ("Amelia Earhart", "hard", "exploration"),
    ("Nikita Khrushchev", "hard", "politics"),
    ("Golda Meir", "hard", "politics"),
]


ENRICHMENT_PROMPT = """You are a knowledge expert. Generate detailed structured data about this famous person.

Person: {name}
Field hint: {field}

Return a JSON object with EXACTLY this structure:
{{
  "aliases": ["list of common short names or nicknames, e.g. last name only"],
  "attributes": {{
    "gender": "male" or "female",
    "alive": true or false,
    "nationality": "primary nationality, lowercase (e.g. french, american, german)",
    "field": "one of: science, politics, music, cinema, sports, literature, arts, business, philosophy, religion, exploration",
    "subfield": "more specific, e.g. physics, rap, football, painting",
    "continent": "one of: europe, americas, asia, africa, oceania",
    "born_before_1900": true or false,
    "born_before_1950": true or false,
    "fictional": false
  }},
  "facts": [
    "12-15 specific factual statements about this person",
    "Each fact should be a single concise English sentence",
    "Cover: achievements, career, personal traits, famous works, awards, anecdotes",
    "Be specific with dates, names, numbers when possible",
    "Do NOT start facts with the person's name"
  ]
}}

Return ONLY valid JSON, no other text."""


def make_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:50]


async def enrich_character(
    name: str, difficulty: str, field: str, client: Mistral
) -> dict | None:
    """Generate full character data using Mistral."""
    prompt = ENRICHMENT_PROMPT.format(name=name, field=field)

    try:
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout_ms=30000,
        )
        content = response.choices[0].message.content
        data = json.loads(content)

        facts = data.get("facts", [])
        if isinstance(facts, list):
            facts = [f for f in facts if isinstance(f, str) and len(f) > 10]

        attrs = data.get("attributes", {})
        aliases = data.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]

        return {
            "id": make_id(name),
            "name": name,
            "aliases": [a for a in aliases if isinstance(a, str) and a != name],
            "difficulty": difficulty,
            "attributes": {
                "gender": str(attrs.get("gender", "unknown")),
                "alive": bool(attrs.get("alive", False)),
                "nationality": str(attrs.get("nationality", "unknown")).lower(),
                "field": str(attrs.get("field", field)).lower(),
                "subfield": str(attrs.get("subfield", "")).lower(),
                "continent": str(attrs.get("continent", "unknown")).lower(),
                "born_before_1900": bool(attrs.get("born_before_1900", False)),
                "born_before_1950": bool(attrs.get("born_before_1950", False)),
                "fictional": False,
            },
            "facts": facts,
        }
    except Exception as e:
        print(f"    [ERROR] Failed for {name}: {e}")
        return None


async def enrich_all(
    people: list[tuple[str, str, str]], api_key: str, concurrency: int = 5
) -> list[dict]:
    """Enrich all people with Mistral-generated data."""
    client = Mistral(api_key=api_key)
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict | None] = [None] * len(people)
    total = len(people)

    async def enrich_one(idx: int, name: str, diff: str, field: str):
        async with semaphore:
            result = await enrich_character(name, diff, field, client)
            results[idx] = result
            status = f"{len(result['facts'])} facts" if result else "FAILED"
            print(f"  [{idx + 1}/{total}] {name}: {status}")

    tasks = [
        enrich_one(i, name, diff, field)
        for i, (name, diff, field) in enumerate(people)
    ]
    await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build LeSphinx character database")
    parser.add_argument("--skip-enrichment", action="store_true")
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("MISTRAL_API_KEY", "")

    people = CURATED_PEOPLE
    by_diff = {"easy": 0, "medium": 0, "hard": 0}
    for _, d, _ in people:
        by_diff[d] += 1
    print(f"Curated list: {len(people)} people")
    print(f"  easy={by_diff['easy']}, medium={by_diff['medium']}, hard={by_diff['hard']}")

    if args.skip_enrichment:
        characters = [
            {"id": make_id(n), "name": n, "aliases": [], "difficulty": d,
             "attributes": {"field": f, "fictional": False}, "facts": []}
            for n, d, f in people
        ]
    else:
        if not api_key:
            print("[ERROR] No Mistral API key. Set MISTRAL_API_KEY or use --api-key")
            sys.exit(1)
        print(f"Enriching {len(people)} characters with Mistral (concurrency={args.concurrency})...")
        characters = asyncio.run(enrich_all(people, api_key, args.concurrency))

    # Filter out characters with too few facts
    before = len(characters)
    characters = [c for c in characters if len(c.get("facts", [])) >= 5]
    print(f"Validated: {before} -> {len(characters)} characters (min 5 facts)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(characters, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(characters)} characters to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
