#!/usr/bin/env python3
"""Add source-linked film soundtrack tracks from MusicBrainz.

Searches only films that currently have no song link. It accepts a soundtrack
release group only when the normalized title and first-release year exactly
match one film, then writes the release's tracklist with MusicBrainz IDs as
provenance. The API is deliberately limited to one request per second.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Dataset"
OUT = ROOT / "outputs" / "musicbrainz-enrichment"
API = "https://musicbrainz.org/ws/2"
UA = "GoodWillMapping-MusicBrainzEnrichment/1.0 (https://github.com/Curious-Lunatic/Movie-Geospatial-KGraphs)"
FIELDS = ["wikidata_id", "film", "year", "song", "singers", "music", "lyrics", "length",
          "song_location_note", "film_filming_locations", "film_filming_coords_wkt",
          "film_narrative_locations", "source_url", "source_evidence"]


def norm(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join("".join(c if unicodedata.category(c)[0] in "LMN" else " " for c in value).split())


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def cache_name(film_id):
    return hashlib.sha256(film_id.encode()).hexdigest() + ".json"


def load_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Client:
    def __init__(self, delay=1.1):
        self.delay = max(1.0, delay)
        self.last = 0.0
        self.requests = 0

    def get(self, url):
        for attempt in range(5):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            self.requests += 1
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    return json.loads(response.read())
            except urllib.error.HTTPError as error:
                if error.code not in (429, 503):
                    raise RuntimeError(f"MusicBrainz returned HTTP {error.code}.") from None
                if attempt == 4:
                    raise RuntimeError("MusicBrainz kept throttling the request; cached progress is retained. Retry later.") from None
                try:
                    wait = float(error.headers.get("Retry-After", ""))
                except ValueError:
                    wait = 30.0 * (attempt + 1)
                print(f"MusicBrainz throttled the request (HTTP {error.code}); waiting {max(wait, self.delay):.0f}s before retry {attempt + 2}/5.", flush=True)
                time.sleep(max(wait, self.delay))
                self.last = time.monotonic()
            except (urllib.error.URLError, TimeoutError) as error:
                raise RuntimeError(f"MusicBrainz connection failed: {getattr(error, 'reason', 'timeout')}.") from None
        raise RuntimeError("MusicBrainz request did not complete.")


def api_url(path, **params):
    params["fmt"] = "json"
    return API + path + "?" + urllib.parse.urlencode(params)


def search_query(title):
    special = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')
    escaped = special.sub(r"\\\1", title)
    return f'releasegroup:"{escaped}"'


def search_batch_query(films):
    clauses = sorted({search_query(f["title"]) for f in films})
    return "(" + " OR ".join(clauses) + ") AND secondarytype:soundtrack"


def credits(items):
    names = []
    for item in items or []:
        if isinstance(item, dict):
            artist = item.get("artist", {}).get("name") or item.get("name") or ""
            phrase = item.get("joinphrase", "")
            if artist:
                names.append(artist + phrase)
        elif isinstance(item, str):
            names.append(item)
    return "".join(names).strip()


def choose_release(group):
    releases = group.get("releases") or []
    year = group.get("first-release-date", "")[:4]
    candidates = [r for r in releases if r.get("date", "")[:4] == year]
    if not candidates:
        return None
    candidates.sort(key=lambda r: (r.get("status") != "Official", r.get("country") != "IN", r.get("date", ""), r.get("id", "")))
    return candidates[0]


def track_rows(release, film, group):
    rows = []
    release_id = release.get("id", "")
    for medium in release.get("media", []):
        for track in medium.get("tracks", []):
            title = (track.get("title") or (track.get("recording") or {}).get("title") or "").strip()
            if not title or norm(title) in {"total", "total length", "track listing"}:
                continue
            recording = track.get("recording") or {}
            singer = credits(track.get("artist-credit") or recording.get("artist-credit"))
            evidence = ("musicbrainz_soundtrack_tracklist; "
                        f"release_group={group.get('id','')}; release={release_id}; recording={recording.get('id','')}; "
                        f"medium={medium.get('position','')}; track={track.get('position','')}; "
                        "match=unique exact normalized title, exact first-release year, soundtrack type")
            rows.append({"wikidata_id": film.get("wikidata_id", ""), "film": film["title"], "year": film["release_year"],
                         "song": title, "singers": singer, "music": "", "lyrics": "", "length": track.get("length", ""),
                         "song_location_note": "", "film_filming_locations": "", "film_filming_coords_wkt": "",
                         "film_narrative_locations": "", "source_url": f"https://musicbrainz.org/release/{release_id}",
                         "source_evidence": evidence})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Process only the first N currently unlinked films")
    parser.add_argument("--delay", type=float, default=1.1, help="Seconds between requests; MusicBrainz requires at most one request per second")
    parser.add_argument("--include-covered", action="store_true", help="Search films that already have song links too")
    parser.add_argument("--plan", action="store_true", help="Show work estimate without making requests")
    parser.add_argument("--output", type=Path, default=DATA / "songs_musicbrainz.csv")
    args = parser.parse_args()

    films = read_csv(DATA / "integrated" / "films.csv")
    current_songs = read_csv(DATA / "integrated" / "songs.csv")
    covered = {r["film_id"] for r in current_songs}
    film_rows = [f for f in films if args.include_covered or f["film_id"] not in covered]
    if args.limit:
        film_rows = film_rows[:args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    cache_dir = OUT / "cache"
    cache_dir.mkdir(exist_ok=True)
    existing_output = {}
    if args.output.exists():
        existing_output = {(r.get("wikidata_id", ""), norm(r.get("film", "")), str(r.get("year", "")), norm(r.get("song", ""))): r
                           for r in read_csv(args.output)}
    cached_names = {p.name for p in cache_dir.glob("*.json")}
    to_process = [f for f in film_rows if cache_name(f["film_id"]) not in cached_names]
    search_batches = (len(to_process) + 24) // 25
    print(json.dumps({"films_in_graph": len(films), "currently_song_linked_films": len(covered),
                      "films_in_this_run": len(film_rows), "uncached_films_to_search": len(to_process),
                      "search_batches": search_batches,
                      "minimum_search_time_minutes": round(search_batches * args.delay / 60, 1),
                      "output": str(args.output)}, indent=2), flush=True)
    if args.plan:
        return

    client = Client(args.delay)
    rows = dict(existing_output)
    ambiguous = []
    skipped = 0

    # Search title batches to avoid one query per film; one exact result is still
    # assigned to one canonical film/year below, so title collisions do not merge.
    pending = []
    for film in film_rows:
        state = load_state(cache_dir / cache_name(film["film_id"]))
        if "candidate_groups" not in state:
            pending.append(film)
    for batch_no, offset in enumerate(range(0, len(pending), 25), 1):
        batch = pending[offset:offset + 25]
        print(f"MusicBrainz search: batch {batch_no}/{(len(pending)+24)//25} ({len(batch)} film titles).", flush=True)
        query = search_batch_query(batch)
        groups = []
        offset_mb = 0
        while True:
            response = client.get(api_url("/release-group", query=query, limit=100, offset=offset_mb))
            groups.extend(response.get("release-groups", []))
            count = int(response.get("count", len(groups)))
            offset_mb += len(response.get("release-groups", []))
            if offset_mb >= count or not response.get("release-groups"):
                break
        by_title_year = {}
        for film in batch:
            by_title_year.setdefault((norm(film["title"]), str(film["release_year"])), []).append(film)
        matches = {film["film_id"]: [] for film in batch}
        for group in groups:
            if not any(t.casefold() == "soundtrack" for t in group.get("secondary-types", [])):
                continue
            key = (norm(group.get("title")), group.get("first-release-date", "")[:4])
            films_for_title = by_title_year.get(key, [])
            if len(films_for_title) == 1:
                matches[films_for_title[0]["film_id"]].append(group)
        for film in batch:
            path = cache_dir / cache_name(film["film_id"])
            state = load_state(path)
            state.update({"film_id": film["film_id"], "candidate_groups": matches[film["film_id"]], "stage": "search_complete"})
            path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        print(f"MusicBrainz search: cached results for {len(batch)} films; {len(groups)} groups returned.", flush=True)

    for i, film in enumerate(film_rows, 1):
        path = cache_dir / cache_name(film["film_id"])
        state = load_state(path)
        groups = state.get("candidate_groups", [])
        if len(groups) != 1:
            if len(groups) > 1:
                ambiguous.append({"film_id": film["film_id"], "film": film["title"], "year": film["release_year"],
                                  "groups": [{"id": g.get("id"), "title": g.get("title"), "year": g.get("first-release-date"),
                                              "url": "https://musicbrainz.org/release-group/" + g.get("id", "")} for g in groups]})
            skipped += 1
        else:
            group = groups[0]
            if "release_group" not in state:
                state["release_group"] = client.get(api_url("/release-group/" + group["id"], inc="releases"))
                path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            release_choice = choose_release(state["release_group"])
            if release_choice:
                if "release_detail" not in state:
                    state["release_detail"] = client.get(api_url("/release/" + release_choice["id"], inc="recordings+artist-credits"))
                    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                for row in track_rows(state["release_detail"], film, group):
                    key = (row["wikidata_id"], norm(row["film"]), str(row["year"]), norm(row["song"]))
                    rows[key] = row
        if i % 25 == 0 or i == len(film_rows):
            ordered = sorted(rows.values(), key=lambda r: (r["year"], norm(r["film"]), norm(r["song"])))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader(); writer.writerows(ordered)
            (OUT / "ambiguous_release_groups.json").write_text(json.dumps(ambiguous, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"MusicBrainz progress: {i}/{len(film_rows)} films; {len(rows)} track rows; {skipped} no unique exact-title/year soundtrack match; {client.requests} API requests.", flush=True)

    print(json.dumps({"track_rows": len(rows), "ambiguous_film_matches": len(ambiguous), "films_without_unique_match": skipped,
                      "api_requests": client.requests, "output": str(args.output)}, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print("MusicBrainz soundtrack enrichment stopped: " + str(error), file=sys.stderr)
        raise SystemExit(2)
