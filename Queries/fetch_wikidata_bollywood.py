import argparse
import time

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

USER_EMAIL = "soubhagyarbiswal@gmail.com"  # REQUIRED: change this


# ---------------------------------------------------------------- queries
def films_query(year):
    return f"""
    SELECT ?movie ?movieLabel ?releaseDate ?directorLabel
           ?narrativeLocationLabel ?narrativeCoords
           ?filmingLocationLabel ?filmingCoords
    WHERE {{
      ?movie wdt:P31 wd:Q11424 ;
             wdt:P495 wd:Q668 ;
             wdt:P364 wd:Q1568 ;
             wdt:P577 ?releaseDate .

      OPTIONAL {{ ?movie wdt:P57 ?director . }}
      OPTIONAL {{
          ?movie wdt:P840 ?narrativeLocation .
          OPTIONAL {{ ?narrativeLocation wdt:P625 ?narrativeCoords . }}
      }}
      OPTIONAL {{
          ?movie wdt:P915 ?filmingLocation .
          OPTIONAL {{ ?filmingLocation wdt:P625 ?filmingCoords . }}
      }}

      FILTER(?releaseDate >= "{year}-01-01T00:00:00Z"^^xsd:dateTime &&
             ?releaseDate <= "{year}-12-31T23:59:59Z"^^xsd:dateTime)

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """


def songs_query(year):
    # Songs/singles whose language of work (P407) is Hindi.
    # Songs rarely carry location data on Wikidata, so none is requested.
    return f"""
    SELECT ?song ?songLabel ?releaseDate ?performerLabel
           ?composerLabel ?lyricistLabel ?partOfLabel
    WHERE {{
      VALUES ?type {{ wd:Q7366 wd:Q134556 }}      # song, single
      ?song wdt:P31 ?type ;
            wdt:P407 wd:Q1568 ;                   # language: Hindi
            wdt:P577 ?releaseDate .

      OPTIONAL {{ ?song wdt:P175 ?performer . }}
      OPTIONAL {{ ?song wdt:P86  ?composer . }}
      OPTIONAL {{ ?song wdt:P676 ?lyricist . }}
      OPTIONAL {{ ?song wdt:P361 ?partOf . }}     # film / album it belongs to

      FILTER(?releaseDate >= "{year}-01-01T00:00:00Z"^^xsd:dateTime &&
             ?releaseDate <= "{year}-12-31T23:59:59Z"^^xsd:dateTime)

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """


# ---------------------------------------------------------------- row parsing
def val(r, key):
    return r.get(key, {}).get("value", "")


def parse_film(r):
    return {
        "wikidata_id": val(r, "movie").split("/")[-1],
        "title": val(r, "movieLabel"),
        "release_date": val(r, "releaseDate").split("T")[0],
        "director": val(r, "directorLabel"),
        "narrative_location": val(r, "narrativeLocationLabel"),
        "narrative_coordinates": val(r, "narrativeCoords"),
        "filming_location": val(r, "filmingLocationLabel"),
        "filming_coordinates": val(r, "filmingCoords"),
    }


def parse_song(r):
    return {
        "wikidata_id": val(r, "song").split("/")[-1],
        "title": val(r, "songLabel"),
        "release_date": val(r, "releaseDate").split("T")[0],
        "performer": val(r, "performerLabel"),
        "composer": val(r, "composerLabel"),
        "lyricist": val(r, "lyricistLabel"),
        "part_of": val(r, "partOfLabel"),
    }


CONFIG = {
    "films": {
        "query": films_query,
        "parse": parse_film,
        "group_cols": ["director", "narrative_location", "narrative_coordinates",
                       "filming_location", "filming_coordinates"],
    },
    "songs": {
        "query": songs_query,
        "parse": parse_song,
        "group_cols": ["performer", "composer", "lyricist", "part_of"],
    },
}


# ---------------------------------------------------------------- fetching
def fetch_year(year, sparql, kind, retries=3):
    cfg = CONFIG[kind]
    sparql.setQuery(cfg["query"](year))
    sparql.setReturnFormat(JSON)

    for attempt in range(1, retries + 1):
        try:
            res = sparql.query().convert()
            return [cfg["parse"](r) for r in res["results"]["bindings"]]
        except Exception as e:
            print(f"  {year} attempt {attempt}/{retries} failed: {e}")
            time.sleep(5 * attempt)  # back off before retrying
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=["films", "songs"], default="films")
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True, help="inclusive")
    args = ap.parse_args()

    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.agent = f"BollywoodGeoGraphBot/1.0 ({USER_EMAIL}) SPARQLWrapper/1.8.5"

    rows = []
    for year in range(args.start, args.end + 1):  # end is inclusive
        print(f"Fetching {args.type} for {year}...")
        rows.extend(fetch_year(year, sparql, args.type))
        time.sleep(2)  # be polite to the endpoint

    df = pd.DataFrame(rows)
    if df.empty:
        print("No data retrieved.")
        return

    join = lambda x: " | ".join(sorted(set(filter(None, x))))
    agg = {c: join for c in CONFIG[args.type]["group_cols"]}
    df = df.groupby(["wikidata_id", "title", "release_date"], as_index=False).agg(agg)
    df = df.sort_values("release_date", ascending=False)

    filename = f"bollywood_{args.type}_{args.start}_{args.end}.csv"
    df.to_csv(filename, index=False, encoding="utf-8")
    print(f"\nSuccess! Saved {len(df)} unique {args.type} to {filename}")


if __name__ == "__main__":
    main()