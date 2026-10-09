#!/usr/bin/env python3
"""
Add filming and narrative locations to a TMDB movies CSV using Wikidata.

Wikidata properties used:
  P915 = filming location
  P840 = narrative location
  P17  = country (used to label each location's country)

Usage:
  pip install requests pandas
  python fetch_locations.py tmdb_movies.csv movies_with_locations.csv

Notes:
  - Needs the 'wikidata_id' column (e.g. Q58428079) in the input CSV.
  - Results are cached in wikidata_cache.json, so you can stop (Ctrl+C) and
    re-run; it resumes where it left off.
  - Please edit USER_AGENT below with your contact info. Wikidata asks for this.
"""

import json
import os
import re
import sys
import time

import pandas as pd
import requests

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "MovieLocationsScript/1.0 (soubhagyarbiswal@gmail.com)"  # <-- edit me
BATCH_SIZE = 150          # movies per query; lower this if you get timeouts
PAUSE_SECONDS = 1.5       # polite delay between queries
MAX_RETRIES = 6
CACHE_FILE = "wikidata_cache.json"
QID_RE = re.compile(r"^Q\d+$")

QUERY_TEMPLATE = """
SELECT ?film ?prop ?locLabel ?countryLabel WHERE {{
  VALUES ?film {{ {values} }}
  {{ ?film wdt:P915 ?loc . BIND("filming" AS ?prop) }}
  UNION
  {{ ?film wdt:P840 ?loc . BIND("narrative" AS ?prop) }}
  OPTIONAL {{ ?loc wdt:P17 ?country . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul". }}
}}
"""


def run_query(qids):
    values = " ".join(f"wd:{q}" for q in qids)
    query = QUERY_TEMPLATE.format(values=values)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(ENDPOINT, data={"query": query}, headers=headers, timeout=120)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            if r.status_code in (429, 502, 503, 504):
                wait = int(r.headers.get("Retry-After", 5 * attempt))
                print(f"  HTTP {r.status_code}, waiting {wait}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            r.raise_for_status()
        except (requests.Timeout, requests.ConnectionError) as e:
            wait = 5 * attempt
            print(f"  {type(e).__name__}, waiting {wait}s (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
    raise RuntimeError("Query failed after retries; try a smaller BATCH_SIZE.")


def label_ok(label):
    """Wikidata returns the bare Q-id as the label when no label exists; skip those."""
    return bool(label) and not QID_RE.match(label)


def collect(bindings):
    """Turn raw SPARQL rows into {qid: {filming: {loc: set(countries)}, narrative: {...}}}"""
    out = {}
    for row in bindings:
        qid = row["film"]["value"].rsplit("/", 1)[-1]
        prop = row["prop"]["value"]
        loc = row.get("locLabel", {}).get("value")
        country = row.get("countryLabel", {}).get("value")
        if not label_ok(loc):
            continue
        entry = out.setdefault(qid, {"filming": {}, "narrative": {}})
        countries = entry[prop].setdefault(loc, [])
        if label_ok(country) and country not in countries and country != loc:
            countries.append(country)
    return out


def fmt_locations(locs):
    parts = []
    for loc, countries in sorted(locs.items()):
        parts.append(f"{loc} ({', '.join(sorted(countries))})" if countries else loc)
    return "|".join(parts)


def fmt_countries(locs):
    countries = set()
    for loc, cs in locs.items():
        countries.update(cs if cs else [loc])  # a country-level location is its own country
    return "|".join(sorted(countries))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    in_path, out_path = sys.argv[1], sys.argv[2]

    df = pd.read_csv(in_path)
    if "wikidata_id" not in df.columns:
        sys.exit("Input CSV has no 'wikidata_id' column.")

    qids = sorted({q for q in df["wikidata_id"].dropna().astype(str).str.strip() if QID_RE.match(q)})
    print(f"{len(df)} movies, {len(qids)} with a valid Wikidata ID.")

    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        print(f"Loaded {len(cache)} cached movies from {CACHE_FILE}.")

    todo = [q for q in qids if q not in cache]
    total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        print(f"Batch {i // BATCH_SIZE + 1}/{total_batches} ({len(batch)} movies)...")
        found = collect(run_query(batch))
        for q in batch:
            # Store an empty entry for movies with no data, so they aren't re-queried
            cache[q] = found.get(q, {"filming": {}, "narrative": {}})
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
        time.sleep(PAUSE_SECONDS)

    def get(qid, key):
        return cache.get(str(qid).strip(), {}).get(key, {}) if isinstance(qid, str) else {}

    df["filming_locations"] = df["wikidata_id"].apply(lambda q: fmt_locations(get(q, "filming")))
    df["filming_countries"] = df["wikidata_id"].apply(lambda q: fmt_countries(get(q, "filming")))
    df["narrative_locations"] = df["wikidata_id"].apply(lambda q: fmt_locations(get(q, "narrative")))
    df["narrative_countries"] = df["wikidata_id"].apply(lambda q: fmt_countries(get(q, "narrative")))

    df.to_csv(out_path, index=False)

    n = len(df)
    has_f = (df["filming_locations"] != "").sum()
    has_n = (df["narrative_locations"] != "").sum()
    has_either = ((df["filming_locations"] != "") | (df["narrative_locations"] != "")).sum()
    print("\n--- Coverage ---")
    print(f"Filming location:    {has_f}/{n} ({has_f / n:.1%})")
    print(f"Narrative location:  {has_n}/{n} ({has_n / n:.1%})")
    print(f"Either:              {has_either}/{n} ({has_either / n:.1%})")
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()