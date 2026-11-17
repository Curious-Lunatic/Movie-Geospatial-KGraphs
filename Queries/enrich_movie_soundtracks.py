#!/usr/bin/env python3
"""Expand film-to-song links from explicit soundtrack tracklists on Wikipedia.

The collector uses a film's Wikidata item to resolve its English Wikipedia page,
then accepts track titles only from a table inside an explicitly named soundtrack
section. It writes a provenance-bearing CSV that the normal graph build can ingest.
It never copies film filming locations onto songs.
"""
import argparse
import csv
import gzip
import hashlib
import html
import json
import email.utils
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Dataset"
OUT = ROOT / "outputs" / "movie-soundtrack-enrichment"
UA = "GoodWillMapping-SoundtrackEnrichment/1.0 (academic project; contact via repository)"
FIELDS = ["wikidata_id", "film", "year", "song", "singers", "music", "lyrics", "length",
          "song_location_note", "film_filming_locations", "film_filming_coords_wkt",
          "film_narrative_locations", "source_url", "source_evidence"]
SOUNDTRACK_SECTION_WORDS = re.compile(r"\b(?:soundtracks?|songs?|tracks?|track\s*list(?:ing)?s?|music)\b", re.I)


def clean_markup(value):
    value = re.sub(r"<!--.*?-->|<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>", "", value, flags=re.S | re.I)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    value = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", lambda m: m[2], value)
    value = re.sub(r"\[(?:https?://\S+\s+)?([^\]]*)\]", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"'{2,5}", "", value)
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    value = re.sub(r"\[citation needed\]", "", value, flags=re.I)
    return " ".join(html.unescape(value).replace("&nbsp;", " ").split()).strip(" '’\"“”–—-;:")


def table_rows(table):
    rows = []
    for raw in re.split(r"\n\s*\|-", table):
        cells = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith(("{|", "|}", "|+")):
                continue
            if line.startswith(("!", "|")):
                content = line[1:]
                separator = r"(?<!\!)!!(?!\!)" if line.startswith("!") else r"(?<!\|)\|\|(?!\|)"
                cells.extend(clean_markup(cell.split("|", 1)[-1] if "|" in cell else cell)
                             for cell in re.split(separator, content))
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def track_rows(wikitext):
    """Return title/credit tuples from titled track-listing tables only."""
    headings = list(re.finditer(r"^(={2,6})\s*(.*?)\s*\1\s*$", wikitext, flags=re.M))
    found = {}
    for index, heading in enumerate(headings):
        name = re.sub(r"\s+", " ", clean_markup(heading.group(2))).casefold()
        if not SOUNDTRACK_SECTION_WORDS.search(name):
            continue
        end = len(wikitext)
        level = len(heading.group(1))
        for later in headings[index + 1:]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        section = wikitext[heading.end():end]
        for table in re.findall(r"\{\|.*?\|\}", section, flags=re.S):
            rows = table_rows(table)
            if len(rows) < 2:
                continue
            header_at = next((i for i, row in enumerate(rows[:3])
                              if any(re.search(r"\b(title|song|track name)\b", c, re.I) for c in row)), None)
            if header_at is None:
                continue
            headers = [c.casefold() for c in rows[header_at]]
            title_col = next((i for i, c in enumerate(headers) if re.search(r"\b(title|song|track name)\b", c)), None)
            if title_col is None:
                continue
            singer_col = next((i for i, c in enumerate(headers) if re.search(r"singer|vocal|performer", c)), None)
            music_col = next((i for i, c in enumerate(headers) if re.search(r"music|composer", c)), None)
            lyric_col = next((i for i, c in enumerate(headers) if re.search(r"lyric", c)), None)
            for row in rows[header_at + 1:]:
                if title_col >= len(row):
                    continue
                title = row[title_col]
                if not title or re.search(r"^(total|track listing|title|unknown|n/?a)$", title, re.I):
                    continue
                if re.fullmatch(r"[\d. ()-]+", title) or len(title) < 2 or len(title) > 180:
                    continue
                def credit(col):
                    return row[col] if col is not None and col < len(row) else ""
                found.setdefault(title.casefold(), (title, credit(singer_col), credit(music_col), credit(lyric_col)))
    return list(found.values())


def get_json(url, delay, state):
    for attempt in range(5):
        time.sleep(max(0, delay - (time.monotonic() - state["last"])))
        state["last"] = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                body = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                break
        except urllib.error.HTTPError as err:
            if err.code == 429:
                if attempt == 4:
                    raise RuntimeError("Provider continued returning HTTP 429 after five backoff attempts; cached progress is retained. Retry later.") from None
                retry_after = err.headers.get("Retry-After", "")
                try:
                    wait = max(0.0, float(retry_after))
                except ValueError:
                    try:
                        wait = max(0.0, email.utils.parsedate_to_datetime(retry_after).timestamp() - time.time())
                    except (TypeError, ValueError, OverflowError):
                        wait = 30.0 * (2 ** attempt)
                print(f"HTTP 429: waiting {max(wait, delay):.0f}s before retry {attempt + 2}/5; progress cache is retained.", flush=True)
                time.sleep(max(wait, delay))
                state["last"] = time.monotonic()
                continue
            if err.code == 403:
                raise RuntimeError("Provider returned HTTP 403; stopped without bypassing its access controls.") from None
            raise RuntimeError(f"Provider returned HTTP {err.code}.") from None
        except (urllib.error.URLError, TimeoutError) as err:
            raise RuntimeError(f"Provider connection failed: {err.reason if isinstance(err, urllib.error.URLError) else 'timeout'}") from None
    return json.loads(body), hashlib.sha256(body).hexdigest()


def api_url(endpoint, **params):
    return endpoint + "?" + urllib.parse.urlencode(params)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def all_films():
    film_rows = read_csv(DATA / "integrated" / "films.csv")
    films = {r["film_id"]: r for r in film_rows}
    attrs = read_csv(DATA / "integrated" / "film_attributes.csv")
    titles = {}
    for row in attrs:
        if row.get("field") == "wikipedia_url" and "en.wikipedia.org/wiki/" in row.get("value", ""):
            if row["film_id"] in films:
                titles.setdefault(row["film_id"], urllib.parse.unquote(row["value"].split("/wiki/", 1)[1]).replace("_", " "))
    qid_owner = {r["wikidata_id"]: fid for fid, r in films.items() if r.get("wikidata_id", "").startswith("Q")}
    return films, titles, qid_owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Limit film pages for a small initial run")
    parser.add_argument("--delay", type=float, default=1.0, help="Minimum seconds between API requests")
    parser.add_argument("--output", type=Path, default=DATA / "songs_soundtrack_additions.csv")
    parser.add_argument("--offline", action="store_true", help="Use only previously cached responses")
    parser.add_argument("--plan", action="store_true", help="Print page coverage and stop")
    args = parser.parse_args()

    films, titles, qid_owner = all_films()
    film_ids = list(films)
    if args.limit:
        film_ids = film_ids[:args.limit]
    needs_qid = [films[fid].get("wikidata_id", "") for fid in film_ids
                 if not titles.get(fid) and films[fid].get("wikidata_id", "").startswith("Q")]
    print(json.dumps({"films": len(film_ids), "known_english_wikipedia_pages": sum(bool(titles.get(fid)) for fid in film_ids),
                      "needs_wikidata_sitelink_lookup": len(needs_qid), "without_wikidata_id": sum(not films[fid].get("wikidata_id") for fid in film_ids),
                      "output": str(args.output)}, indent=2))
    if args.plan:
        return

    cache_dir = OUT / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    state = {"last": 0.0}
    for fid in film_ids:
        path = cache_dir / (hashlib.sha1(fid.encode()).hexdigest() + ".json")
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8")); titles[fid] = cached.get("title", "") or titles.get(fid, "")
            except (OSError, ValueError):
                pass
    if not args.offline:
        missing = [films[fid]["wikidata_id"] for fid in film_ids
                   if not titles.get(fid) and films[fid].get("wikidata_id", "").startswith("Q")]
        batches = (len(missing) + 49) // 50
        for batch_no, offset in enumerate(range(0, len(missing), 50), 1):
            batch = missing[offset:offset + 50]
            print(f"Wikidata sitelinks: batch {batch_no}/{batches} ({len(batch)} items).", flush=True)
            body, digest = get_json(api_url("https://www.wikidata.org/w/api.php", action="wbgetentities", ids="|".join(batch), props="sitelinks", format="json"), args.delay, state)
            for qid, entity in body.get("entities", {}).items():
                page_title = (entity.get("sitelinks", {}).get("enwiki") or {}).get("title", "")
                fid = qid_owner.get(qid)
                if fid:
                    titles[fid] = page_title
                    record = {"title": page_title, "wikidata_response_sha256": digest}
                    (cache_dir / (hashlib.sha1(fid.encode()).hexdigest() + ".json")).write_text(json.dumps(record), encoding="utf-8")
            print(f"Wikidata sitelinks: cached batch {batch_no}/{batches}.", flush=True)

    pages_to_fetch = [fid for fid in film_ids if titles.get(fid)]
    snapshots = {}
    # Previous versions wrote the full accumulated snapshot map after each batch.
    # Reuse its largest checkpoint once instead of repeatedly loading multi-GB copies.
    old_checkpoints = list(cache_dir.glob("wiki-*.json"))
    if old_checkpoints:
        latest = max(old_checkpoints, key=lambda p: p.stat().st_size)
        try:
            snapshots.update(json.loads(latest.read_text(encoding="utf-8")))
            print(f"Wikipedia revisions: loaded {len(snapshots)} cached pages from the existing checkpoint.", flush=True)
        except (OSError, ValueError) as error:
            print(f"Wikipedia revisions: could not load checkpoint {latest.name}: {error}.", flush=True)
    batches = (len(pages_to_fetch) + 49) // 50
    for batch_no, offset in enumerate(range(0, len(pages_to_fetch), 50), 1):
        batch = pages_to_fetch[offset:offset + 50]
        missing_pages = [fid for fid in batch if fid not in snapshots]
        if not missing_pages:
            print(f"Wikipedia revisions: reused cached batch {batch_no}/{batches} ({len(batch)} pages).", flush=True)
            continue
        if args.offline:
            print(f"Wikipedia revisions: {len(missing_pages)} pages missing from cache in batch {batch_no}/{batches}; skipped (--offline).", flush=True)
            continue
        print(f"Wikipedia revisions: requesting batch {batch_no}/{batches} ({len(batch)} pages).", flush=True)
        titles_arg = "|".join(titles[fid] for fid in missing_pages)
        body, digest = get_json(api_url("https://en.wikipedia.org/w/api.php", action="query", prop="revisions", titles=titles_arg,
                                         rvprop="ids|content", rvslots="main", redirects=1, formatversion=2, format="json"), args.delay, state)
        pages = body.get("query", {}).get("pages", [])
        by_title = {p.get("title"): p for p in pages}
        aliases = {x["from"]: x["to"] for x in body.get("query", {}).get("normalized", []) + body.get("query", {}).get("redirects", [])}
        batch_snapshots = {}
        for fid in missing_pages:
            name = titles[fid]
            seen = set()
            while name in aliases and name not in seen:
                seen.add(name); name = aliases[name]
            page = by_title.get(name, {})
            revision = (page.get("revisions") or [{}])[0]
            content = revision.get("slots", {}).get("main", {}).get("content", "")
            batch_snapshots[fid] = {"title": page.get("title", titles[fid]), "revision_id": revision.get("revid", ""),
                                    "wikitext": content, "response_sha256": digest}
        snapshots.update(batch_snapshots)
        cache_path = cache_dir / ("wiki-batch-" + hashlib.sha256("|".join(missing_pages).encode()).hexdigest() + ".json")
        cache_path.write_text(json.dumps(batch_snapshots, ensure_ascii=False), encoding="utf-8")
        print(f"Wikipedia revisions: saved batch {batch_no}/{batches}; {len(snapshots)} pages processed so far.", flush=True)

    if args.offline and not snapshots:
        raise RuntimeError("No cached soundtrack-page responses are available; rerun without --offline when network access is available.")

    existing = {(re.sub(r"\W+", " ", r["film"].casefold()).strip(), str(r.get("year", "")),
                 re.sub(r"\W+", " ", r["song"].casefold()).strip())
                for source in DATA.glob("songs_[0-9]*_[0-9]*.csv") for r in read_csv(source)}
    rows = []
    for fid in film_ids:
        snapshot = snapshots.get(fid, {})
        film = films[fid]
        for title, singers, music, lyrics in track_rows(snapshot.get("wikitext", "")):
            key = (re.sub(r"\W+", " ", film["title"].casefold()).strip(), str(film["release_year"]),
                   re.sub(r"\W+", " ", title.casefold()).strip())
            if key in existing:
                continue
            existing.add(key)
            rows.append({"wikidata_id": film.get("wikidata_id", ""), "film": film["title"], "year": film["release_year"], "song": title,
                         "singers": singers, "music": music, "lyrics": lyrics, "length": "", "song_location_note": "",
                         "film_filming_locations": "", "film_filming_coords_wkt": "", "film_narrative_locations": "",
                         "source_url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(snapshot.get("title", "").replace(" ", "_"), safe=""),
                         "source_evidence": "wikipedia_soundtrack_tracklist; revision=" + str(snapshot.get("revision_id", "")) +
                                            "; response_sha256=" + str(snapshot.get("response_sha256", ""))})
    print(f"Tracklist parsing complete: {len(rows)} new song rows from {len({(r['film'], r['year']) for r in rows})} films.", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"wikipedia_pages_with_tracklists": len({(r["film"], r["year"]) for r in rows}), "new_track_rows": len(rows),
                      "output": str(args.output), "source": "explicit soundtrack-section tracklist tables only"}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print("Soundtrack enrichment stopped: " + str(error), file=sys.stderr)
        raise SystemExit(2)
