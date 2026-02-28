"""
Fetch character images from Wikidata/Wikimedia Commons.

This script:
1) reads lesphinx/data/characters.json
2) finds a Wikidata item for each character name
3) resolves P18 image filename
4) downloads a 512px thumbnail locally into lesphinx/static/characters/
5) writes image metadata back into characters.json

Usage:
    python -m scripts.fetch_character_images
    python -m scripts.fetch_character_images --limit 20
    python -m scripts.fetch_character_images --overwrite
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).parent.parent
CHARACTERS_PATH = ROOT / "lesphinx" / "data" / "characters.json"
STATIC_CHAR_DIR = ROOT / "lesphinx" / "static" / "characters"
ATTRIBUTIONS_PATH = ROOT / "lesphinx" / "data" / "image_attributions.json"


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "LeSphinxImageFetcher/1.0 (hackathon project; contact: local-dev)"


def _http_json(url: str, timeout: int = 20, retries: int = 3) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < retries:
                attempt += 1
                time.sleep(1.2 * attempt)
                continue
            raise


def _http_bytes(url: str, timeout: int = 20, retries: int = 3) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < retries:
                attempt += 1
                time.sleep(1.2 * attempt)
                continue
            raise


def _search_wikidata_entities(name: str) -> list[str]:
    q = urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "type": "item",
            "limit": 5,
            "search": name,
        }
    )
    data = _http_json(f"{WIKIDATA_API}?{q}")
    hits = data.get("search", [])
    if not hits:
        return []

    exact = next((h for h in hits if h.get("label", "").lower() == name.lower()), None)
    ordered = []
    if exact and exact.get("id"):
        ordered.append(exact["id"])
    for hit in hits:
        qid = hit.get("id")
        if qid and qid not in ordered:
            ordered.append(qid)
    return ordered


def _entity_image_filename(qid: str) -> str | None:
    q = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "format": "json",
            "ids": qid,
            "props": "claims",
        }
    )
    data = _http_json(f"{WIKIDATA_API}?{q}")
    entity = data.get("entities", {}).get(qid, {})
    p18 = entity.get("claims", {}).get("P18", [])
    if not p18:
        return None
    try:
        return p18[0]["mainsnak"]["datavalue"]["value"]
    except Exception:
        return None


def _commons_image_info(filename: str) -> dict | None:
    title = f"File:{filename}"
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": 512,
        }
    )
    data = _http_json(f"{COMMONS_API}?{q}")
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None
    page = next(iter(pages.values()))
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None

    meta = info.get("extmetadata", {})
    return {
        "thumb_url": info.get("thumburl") or info.get("url"),
        "source_url": info.get("descriptionurl"),
        "license": (meta.get("LicenseShortName") or {}).get("value"),
        "author": (meta.get("Artist") or {}).get("value"),
    }


def _safe_ext_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"):
        if path.endswith(ext):
            return ext
    return ".jpg"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch character images from Wikimedia")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of characters (0 = all)")
    parser.add_argument("--overwrite", action="store_true", help="Re-download even if image exists")
    parser.add_argument("--sleep-ms", type=int, default=120, help="Delay between requests")
    args = parser.parse_args()

    if not CHARACTERS_PATH.exists():
        raise FileNotFoundError(f"Missing file: {CHARACTERS_PATH}")

    STATIC_CHAR_DIR.mkdir(parents=True, exist_ok=True)

    with open(CHARACTERS_PATH) as f:
        characters = json.load(f)

    if args.limit and args.limit > 0:
        characters = characters[: args.limit]

    updated = 0
    skipped = 0
    failed = 0
    attributions: list[dict] = []

    total = len(characters)
    for idx, char in enumerate(characters, start=1):
        name = char.get("name", "")
        char_id = char.get("id", "")
        existing = (char.get("image") or {}).get("local_path")

        if existing and not args.overwrite:
            local_existing = ROOT / "lesphinx" / "static" / existing.lstrip("/").split("static/")[-1]
            if local_existing.exists():
                skipped += 1
                print(f"[{idx}/{total}] SKIP {name} (already has image)")
                continue

        try:
            qids = _search_wikidata_entities(name)
            if not qids:
                failed += 1
                print(f"[{idx}/{total}] FAIL {name} (no Wikidata entity)")
                continue

            qid = None
            filename = None
            for candidate_qid in qids:
                file_candidate = _entity_image_filename(candidate_qid)
                if file_candidate:
                    qid = candidate_qid
                    filename = file_candidate
                    break

            if not filename:
                failed += 1
                print(f"[{idx}/{total}] FAIL {name} (no P18 image)")
                continue

            info = _commons_image_info(filename)
            if not info or not info.get("thumb_url"):
                failed += 1
                print(f"[{idx}/{total}] FAIL {name} (no Commons image info)")
                continue

            thumb_url = info["thumb_url"]
            ext = _safe_ext_from_url(thumb_url)
            local_name = f"{char_id}{ext}"
            local_path = STATIC_CHAR_DIR / local_name

            img_bytes = _http_bytes(thumb_url)
            local_path.write_bytes(img_bytes)

            image_meta = {
                "wikidata_id": qid,
                "commons_file": filename,
                "thumb_url": thumb_url,
                "local_path": f"/characters/{local_name}",
                "source_url": info.get("source_url"),
                "license": info.get("license"),
                "author": info.get("author"),
            }
            char["image"] = image_meta
            attributions.append({"id": char_id, "name": name, **image_meta})
            updated += 1
            print(f"[{idx}/{total}] OK   {name} -> {local_name}")
        except Exception as exc:
            failed += 1
            print(f"[{idx}/{total}] FAIL {name}: {exc}")
        finally:
            time.sleep(max(0, args.sleep_ms) / 1000.0)

    # Write back updated image metadata in the full dataset.
    full_data = json.loads(CHARACTERS_PATH.read_text())
    by_id = {c.get("id"): c for c in characters}
    for c in full_data:
        cid = c.get("id")
        if cid in by_id and "image" in by_id[cid]:
            c["image"] = by_id[cid]["image"]
    CHARACTERS_PATH.write_text(json.dumps(full_data, indent=2, ensure_ascii=False))

    # Rebuild attributions from all characters having an image block
    all_attributions = []
    for c in full_data:
        img = c.get("image")
        if not isinstance(img, dict):
            continue
        all_attributions.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "source_url": img.get("source_url"),
                "license": img.get("license"),
                "author": img.get("author"),
                "commons_file": img.get("commons_file"),
                "local_path": img.get("local_path"),
            }
        )
    ATTRIBUTIONS_PATH.write_text(json.dumps(all_attributions, indent=2, ensure_ascii=False))

    print("\nDone.")
    print(f"  updated: {updated}")
    print(f"  skipped: {skipped}")
    print(f"  failed:  {failed}")
    print(f"  images_dir: {STATIC_CHAR_DIR}")
    print(f"  attributions: {ATTRIBUTIONS_PATH}")


if __name__ == "__main__":
    main()
