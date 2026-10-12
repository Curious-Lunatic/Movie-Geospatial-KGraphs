#!/usr/bin/env python3
"""Validate and report heritage improvements against the saved pre-change graph."""
from collections import Counter
import json
from pathlib import Path
from enrich_from_location_lists import read_csv, write_csv
from enrich_heritage_locations import METHODS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Queries/heritage_enrichment'
GRAPH = ROOT / 'Dataset/integrated'
films = {f['film_id']: f for f in read_csv(GRAPH / 'films.csv')}
places = {p['place_id']: p for p in read_csv(GRAPH / 'places.csv')}
claims = [c for c in read_csv(GRAPH / 'claims.csv') if c['relation'] == 'filming'
          and c['object_id'].startswith(('heritage:', 'heritage-component:'))]
baseline = json.loads((WORK / 'baseline.json').read_text())
before = {tuple(p) for p in baseline['property_filming_pairs']}


def pair(c):
    site = places[c['object_id']]
    return (c['subject_id'], site['heritage_parent_id'] or site['place_id'])


after = {pair(c) for c in claims}
old_evidence = {pair(c) for c in claims if c['method'] not in METHODS}
recovered = old_evidence - before
new = after - old_evidence
added = after - before
assert before <= after
assert recovered.isdisjoint(new) and recovered | new == added
expected = read_csv(WORK / 'assertions.csv')
imported = [c for c in claims if c['method'] in METHODS]
assert len(imported) == len(expected)
assert all(c['source_url'] and c['retrieved_at'] and c['evidence'] for c in imported)
assert all(c['status'] == 'source_supported' for c in claims)
for pid in {c['object_id'] for c in claims}:
    assert places[pid]['latitude'] and places[pid]['longitude']
rows = []
seen = set()
for c in claims:
    key = pair(c)
    if key not in added or key in seen:
        continue
    # Select the original evidence for recovered identities, new evidence otherwise.
    if (key in recovered) != (c['method'] not in METHODS):
        continue
    seen.add(key)
    fid, pid = key
    rows.append(dict(film_id=fid, title=films[fid]['title'], release_year=films[fid]['release_year'],
        heritage_id=pid, heritage_site=places[pid]['place_name'], filming_entity_id=c['object_id'],
        filming_entity=places[c['object_id']]['place_name'],
        addition_type='recovered_existing_evidence' if key in recovered else 'new_source_evidence',
        source_file=c['source_file'], source_row=c['source_row'], source_url=c['source_url'], evidence=c['evidence']))
assert len(rows) == len(added)
write_csv(WORK / 'added_heritage_connections.csv', rows, list(rows[0]))
before_counts = Counter(p for f, p in before)
after_counts = Counter(p for f, p in after)
report = dict(passed=True, before_film_heritage_pairs=len(before), after_film_heritage_pairs=len(after),
    added_film_heritage_pairs=len(added), recovered_existing_connections=len(recovered),
    newly_sourced_connections=len(new), new_source_assertions=len(imported),
    before_linked_heritage_properties=len(before_counts), after_linked_heritage_properties=len(after_counts),
    new_heritage_properties=len(set(after_counts) - set(before_counts)),
    films_gaining_heritage_connections=len({f for f, p in added}),
    by_site=[dict(heritage_id=p, name=places[p]['place_name'], before=before_counts[p],
                  after=after_counts[p], added=after_counts[p]-before_counts[p]) for p in sorted(after_counts)],
    counting_rule='Unique film–UNESCO-property pairs; components roll up to their parent. Multiple sources do not increase the count.',
    scope='1970–2025 corpus; UNESCO properties in the supplied dataset inscribed by 2025. Evidence is not independent verification; coordinates represent sites, not camera positions.')
(WORK / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
