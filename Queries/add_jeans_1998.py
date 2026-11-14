#!/usr/bin/env python3
"""Add source-backed metadata and location claims for Jeans (1998)."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKIDATA = "https://www.wikidata.org/wiki/Q3176321"
WIKIPEDIA = "https://en.wikipedia.org/wiki/Jeans_(film)"


def append_once(relative_path, row, key_fields, extra_fields=()):
    path = ROOT / relative_path
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    fields = list(reader.fieldnames or [])
    rows = list(reader)
    if any(all(existing.get(k, "") == row.get(k, "") for k in key_fields) for existing in rows):
        return
    line_ending = "\r\n" if b"\r\n" in raw else "\n"
    buffer = __import__("io").StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator=line_ending)
    writer.writerow(row)
    addition = buffer.getvalue().encode("utf-8")
    with path.open("ab") as stream:
        if raw and not raw.endswith((b"\n", b"\r")):
            stream.write(line_ending.encode("ascii"))
        stream.write(addition)


def main():
    append_once("Dataset/enriched/films_enriched.csv", {
        "film_id": "Q3176321", "title": "Jeans", "release_year": "1998",
        "wikidata_id": "Q3176321", "imdb_id": "tt0151121", "wikipedia_url": WIKIPEDIA,
        "sources": "Wikidata Q3176321; Wikipedia Jeans (film)",
    }, ("film_id",))

    append_once("Dataset/wikidata_movies.csv", {
        "wikidata_id": "Q3176321", "title": "Jeans", "release_date": "1998-04-24",
        "director": "S. Shankar", "narrative_location": "Los Angeles|Chennai|Karaikudi",
        "narrative_coordinates": "Point(-118.24368 34.05223)|Point(80.275 13.0825)|Point(78.7732 10.0735)",
        "filming_location": "Egypt|Rome|Los Angeles",
        "filming_coordinates": "Point(29 27)|Point(12.48277778 41.89333333)|Point(-118.24368 34.05223)",
        "original_language": "Tamil", "hindi_dubbed_release": "1998", "wikipedia_url": WIKIPEDIA,
    }, ("wikidata_id",))

    append_once("Dataset/tmdb_movies.csv", {
        "tmdb_id": "30086", "imdb_id": "tt0151121", "wikidata_id": "Q3176321",
        "title": "Jeans", "original_title": "Jeans", "release_date": "1998-04-24",
        "runtime": "172", "genres": "Comedy|Drama|Romance", "vote_average": "",
        "vote_count": "", "production_countries": "IN",
    }, ("tmdb_id",))

    film_locations = [
        ("filming", "Chennai", "Q1352", "The filming section identifies Chennai among the Tamil Nadu filming cities."),
        ("filming", "Karaikudi", "Q1023693", "The filming section identifies Karaikudi among the Tamil Nadu filming cities."),
        ("filming", "Madurai", "Q228405", "The filming section identifies Madurai among the Tamil Nadu filming cities."),
        ("filming", "Las Vegas", "Q23768", "The filming section names Las Vegas production scenes."),
        ("filming", "Los Angeles", "Q65", "The filming section describes production in Los Angeles."),
        ("filming", "Universal Studios", "", "The filming section describes scenes filmed inside Universal Studios."),
        ("filming", "Grand Canyon", "heritage:75", "The filming section names the Grand Canyon; mapped to the project's Grand Canyon National Park reference point."),
        ("filming", "Valley of Fire", "", "The filming section lists Valley of Fire as a shooting location."),
        ("filming", "Manhattan Beach", "", "The filming section lists Manhattan Beach as a shooting location."),
        ("filming", "Malibu Lake", "", "The filming section lists Malibu Lake as a shooting location."),
        ("filming", "New Jersey", "Q1408", "The filming section reports additional shooting in New Jersey."),
        ("filming", "New York City", "Q60", "The filming section reports shooting in New York City."),
        ("filming", "World Trade Center", "", "The filming section identifies the World Trade Center as a New York shooting site."),
        ("filming", "Piazza del Duomo, Pisa", "heritage:395", "The filming section names the Leaning Tower of Pisa; mapped to the UNESCO Piazza del Duomo, Pisa reference."),
        ("filming", "Empire State Building", "", "The filming section names the Empire State Building in the Poovukkul world-tour sequence."),
        ("filming", "The Great Wall", "heritage:438", "The filming section names the Great Wall; mapped to the UNESCO Great Wall reference."),
        ("filming", "Taj Mahal", "heritage:252", "The filming section names the Taj Mahal in the Poovukkul world-tour sequence."),
        ("filming", "Memphis and its Necropolis – the Pyramid Fields from Giza to Dahshur", "heritage:86", "The filming section names the Egyptian pyramids; mapped to the UNESCO pyramid-fields reference."),
        ("filming", "Colosseum", "", "The filming section names the Colosseum in the Poovukkul world-tour sequence."),
        ("filming", "Eiffel Tower", "", "The filming section names the Eiffel Tower in the Poovukkul world-tour sequence."),
        ("filming", "Group of Monuments at Mahabalipuram", "heritage:249", "The filming section says the Columbus song was filmed at Mahabalipuram; mapped to its UNESCO property reference."),
        ("filming", "Rome", "Q220", "Wikidata lists Rome as a filming location for the film."),
        ("filming", "Egypt", "Q79", "Wikidata lists Egypt as a filming location for the film."),
    ]
    narrative = [
        ("narrative", "Los Angeles", "Q65", "The plot section places the family's home and restaurant in Los Angeles."),
        ("narrative", "Chennai", "Q1352", "The plot section places story events in Chennai."),
        ("narrative", "Karaikudi", "Q1023693", "The plot section places the family flashback and restaurant story in Karaikudi."),
    ]
    path = ROOT / "Dataset/enriched/location_assertions.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    existing = {(r.get("film_id"), r.get("relation"), r.get("place_id"), r.get("place_name"), r.get("source_url")) for r in rows}
    added = 0
    for relation, name, pid, evidence in film_locations + narrative:
        row = {"film_id": "Q3176321", "relation": relation, "place_name": name,
               "place_id": pid, "method": "wikipedia_production_section_review",
               "source_url": WIKIPEDIA, "evidence": evidence,
               "status": "source_supported", "revision_id": "", "retrieved_at": ""}
        key = (row["film_id"], relation, pid, name, WIKIPEDIA)
        if key in existing:
            continue
        rows.append(row); existing.add(key); added += 1
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    print(f"Jeans (1998): source rows added or updated; {added} supported location assertions added.")


if __name__ == "__main__":
    main()
