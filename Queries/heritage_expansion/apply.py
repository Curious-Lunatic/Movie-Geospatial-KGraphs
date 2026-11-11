"""Apply reviewed historic-site identities and filming evidence to an Integration build."""
import hashlib
import json
from pathlib import Path


def apply(graph):
    directory = Path(__file__).resolve().parent
    relative = "../Queries/heritage_expansion/"
    sites_path = graph.data / relative / "sites.csv"
    if not sites_path.exists():
        return
    sites = graph.read(relative + "sites.csv")
    aliases = {}
    for site in sites:
        snapshot = directory / "sources" / site["source_snapshot"]
        source = json.loads(snapshot.read_text(encoding='utf-8'))
        if source["url"] != site["heritage_source"]:
            raise ValueError("Heritage identity source mismatch")
        if site["canonical_id"]:
            aliases[site["place_id"]] = site["canonical_id"]
            continue
        pid = site["place_id"]
        point = (float(site["latitude"]), float(site["longitude"])) if site["latitude"] else None
        graph.add_place(pid, site["place_name"], point, "historic_site_representative_point",
                        site["coordinate_source"])
        place = graph.places[pid]
        place.update(heritage_kind=site["heritage_kind"],
                     heritage_source=site["heritage_source"],
                     heritage_parent_id=site["heritage_parent_id"],
                     country_codes="IN", country_names="India")
        if point and place["latitude"] == "":
            place.update(latitude=point[0], longitude=point[1],
                         coordinate_scope="historic_site_representative_point",
                         coordinate_source=site["coordinate_source"])
    for alias, canonical in aliases.items():
        if canonical not in graph.places:
            raise ValueError("Unknown canonical heritage site")
        for claim in graph.claims.values():
            if claim["object_id"] == alias:
                claim["object_id"] = canonical
                claim["evidence"] += "; Reviewed same-site identity: " + alias + " -> " + canonical
        graph.places.pop(alias, None)

    filename = relative + "reviewed_claims.json"
    raw = (graph.data / filename).read_bytes()
    records = json.loads(raw)
    graph.inputs[filename] = dict(rows=len(records), sha256=hashlib.sha256(raw).hexdigest())
    for row, record in enumerate(records, 1):
        source_path = directory / "sources" / record["source_snapshot"]
        source = json.loads(source_path.read_text(encoding='utf-8'))
        if record["verify_text"] not in source["text"] or record["source_url"] != source["url"]:
            raise ValueError("Filming evidence does not match the reviewed snapshot")
        film = graph.lookup("wikidata", record["wikidata_id"]) if record["wikidata_id"] else record["film_id"]
        if not film or film not in graph.films:
            continue  # Film falls outside the requested corpus.
        if graph.films[film]["title"] != record["title"]:
            raise ValueError("Film identity changed: " + record["title"])
        place = record["place_id"]
        if place not in graph.places:
            continue  # Respect an earlier UNESCO inscription cutoff.
        graph.claim(film, "filming", place, filename, row, "reviewed_heritage_expansion",
                    record["source_url"], evidence=record["evidence"])
    for path in sorted((directory / "sources").glob("*.json")):
        graph.inputs[relative + "sources/" + path.name] = dict(
            rows=1, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
