#!/usr/bin/env python3
"""Query the integrated CSV graph offline; no database server or API key needed."""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def distance_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between representative points on a spherical Earth."""
    lat1, lon1, lat2, lon2 = map(math.radians, (float(lat1), float(lon1), float(lat2), float(lon2)))
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def read(directory, name):
    with (Path(directory) / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def nearby(directory, heritage, radius=5, site_only=True, relation="filming"):
    films = {r["film_id"]: r for r in read(directory, "films.csv")}
    places = {r["place_id"]: r for r in read(directory, "places.csv")}
    matches = [p for p in places.values() if p["place_id"].startswith(("heritage:", "heritage-component:"))
               and (p["place_id"] == heritage or p["place_name"].casefold() == heritage.casefold())]
    if len(matches) != 1:
        raise ValueError("Heritage name is missing or ambiguous. Use the place_id from places.csv.")
    target = matches[0]
    if target["latitude"] == "":
        raise ValueError("This heritage site has no usable representative coordinate.")
    if not math.isfinite(radius) or radius < 0:
        raise ValueError("Radius must be a finite non-negative number of kilometres.")
    groups = {}
    for claim in read(directory, "claims.csv"):
        if claim["relation"] != relation or claim["status"] != "source_supported":
            continue
        place = places[claim["object_id"]]
        if place["latitude"] == "":
            continue
        if site_only and not place["place_id"].startswith(("heritage:", "heritage-component:")):
            continue
        distance = distance_km(target["latitude"], target["longitude"], place["latitude"], place["longitude"])
        if distance <= radius:
            pair = (claim["subject_id"], claim["object_id"])
            if pair not in groups:
                film = films[claim["subject_id"]]
                groups[pair] = dict(film_id=film["film_id"], title=film["title"], release_year=film["release_year"],
                    relation=relation, place_id=place["place_id"], place_name=place["place_name"],
                    heritage_site=target["place_name"], distance_km=round(distance, 6),
                    coordinate_scope=place["coordinate_scope"],
                    interpretation="Representative point proximity; not a verified shooting position or boundary distance",
                    sources=set())
            groups[pair]["sources"].add(claim["source_file"] + ":" + claim["source_row"])
    result = []
    for row in groups.values():
        row["sources"] = "|".join(sorted(row["sources"]))
        result.append(row)
    return sorted(result, key=lambda r: (r["distance_km"], r["title"], r["place_name"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "Dataset" / "integrated")
    parser.add_argument("--heritage", default="Taj Mahal")
    parser.add_argument("--radius-km", type=float, default=5)
    parser.add_argument("--include-broad-places", action="store_true",
                        help="Include city/country representative points as review candidates")
    parser.add_argument("--relation", choices=["filming", "narrative"], default="filming")
    parser.add_argument("--output", type=Path, help="Optional result CSV")
    args = parser.parse_args()
    try:
        rows = nearby(args.data_dir, args.heritage, args.radius_km, not args.include_broad_places, args.relation)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = ["film_id", "title", "release_year", "relation", "place_id", "place_name", "heritage_site",
                  "distance_km", "coordinate_scope", "interpretation", "sources"]
        with args.output.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(rows, ensure_ascii=True, indent=2))
    print("%d matching film/place pairs" % len(rows))


if __name__ == "__main__":
    main()
