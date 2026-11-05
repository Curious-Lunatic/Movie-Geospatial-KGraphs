"""Report distinct site counts and distinguish recovered from newly sourced links."""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent


def report():
    def read(name):
        return list(csv.DictReader((ROOT / "Dataset/integrated" / name).open()))
    places = {row["place_id"]: row for row in read("places.csv")}
    films = {row["film_id"]: row for row in read("films.csv")}
    baseline = {tuple(pair) for pair in json.loads((WORK / "baseline.json").read_text())["pairs"]}
    pairs = defaultdict(list)
    previous_filming = set()
    added_filming = set()
    for claim in read("claims.csv"):
        if claim["relation"] != "filming":
            continue
        pid = claim["object_id"]
        place = places[pid]
        if not (pid.startswith(("heritage:", "heritage-component:")) or place.get("heritage_kind")):
            continue
        pair = claim["subject_id"], place["heritage_parent_id"] or pid
        pairs[pair].append(claim)
        if claim["method"] == "reviewed_heritage_expansion":
            added_filming.add(pair)
        else:
            previous_filming.add(pair)
    assert baseline <= pairs.keys(), "A previous heritage connection was lost"
    assert len(pairs) == len(set(pairs))
    additions = set(pairs) - baseline
    summary = dict(
        before_sites=len({site for film, site in baseline}),
        after_sites=len({site for film, site in pairs}),
        before_connections=len(baseline), after_connections=len(pairs),
        added_connections=len(additions), films=len({film for film, site in pairs}),
        recovered_existing_connections=len(additions & previous_filming),
        newly_sourced_connections=len(added_filming - previous_filming),
        new_source_assertions=sum(c["method"] == "reviewed_heritage_expansion"
                                  for claims in pairs.values() for c in claims),
        counting_rule="Distinct film and parent-site pairs. Aliases and components do not inflate site counts.",
        sites=[dict(site=places[site]["place_name"],
                    films=len({film for film, target in pairs if target == site}))
               for site in sorted({site for film, site in pairs},
                                  key=lambda site: places[site]["place_name"])]
    )
    (WORK / "report.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (WORK / "added_connections.csv").open("w") as output:
        writer = csv.writer(output)
        writer.writerow(["film_id", "film", "site_id", "site", "addition_type", "evidence_sources"])
        for film, site in sorted(additions):
            claims = pairs[film, site]
            writer.writerow([film, films[film]["title"], site, places[site]["place_name"],
                             "recovered_existing" if (film, site) in previous_filming else "newly_sourced",
                             " | ".join(sorted({c["source_url"] or c["source_file"] + ":" + c["source_row"]
                                                for c in claims}))])
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    report()
