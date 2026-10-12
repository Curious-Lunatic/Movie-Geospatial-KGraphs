#!/usr/bin/env python3
"""Check imported provenance, identity, summary consistency and reported deltas."""
from collections import defaultdict
import json
from enrich_from_location_lists import WORK, OUT, read_csv, pair, METHODS

films = read_csv(OUT / 'films_enriched.csv')
claims = read_csv(OUT / 'location_assertions.csv')
places = read_csv(OUT / 'places.csv')
batch = read_csv(WORK / 'assertions.csv')
baseline = json.loads((WORK / 'baseline.json').read_text())
report = json.loads((WORK / 'report.json').read_text())
film_ids = {f['film_id'] for f in films}
place_ids = {p['place_id'] for p in places}
assert len(film_ids) == len(films)
assert len(place_ids) == len(places)
signatures = set()
for a in batch:
    assert a['film_id'] in film_ids and a['place_id'] in place_ids
    assert a['relation'] == 'filming' and a['method'] in METHODS
    assert a['source_url'].startswith('https://en.wikipedia.org/')
    assert a['evidence'] and a['retrieved_at']
    signature = (a['film_id'], a['place_id'], a['source_url'])
    assert signature not in signatures
    signatures.add(signature)
assert signatures <= {(a['film_id'], a['place_id'], a['source_url']) for a in claims if a['method'] in METHODS}
supported = defaultdict(set)
for a in claims:
    if a['relation'] == 'filming' and a['status'] == 'source_supported':
        supported[a['film_id']].add(a['place_name'])
for f in films:
    assert set(filter(None, f['filming_locations'].split('|'))) == supported[f['film_id']]
before = {tuple(p) for p in baseline['filming_pairs']}
added = {pair(a) for a in batch} - before
assert len(added) == report['new_film_location_pairs']
assert len({f for f, p in added}) == report['films_with_new_locations']
assert len({a['place_id'] for a in batch} - set(baseline['place_ids'])) == report['new_place_entities']
assert {pair(a) for a in read_csv(WORK / 'added_film_locations.csv')} == added
after = {pair(a) for a in claims if a['relation'] == 'filming' and a['status'] == 'source_supported'}
assert before <= after
# Other independently imported batches may add claims after this batch's report.
assert {pair(a) for a in batch} <= after
assert len(after) >= report['after_supported_filming_pairs']
result = dict(passed=True, batch_assertions=len(batch), added_film_location_pairs=len(added),
              missing_revision_ids=sum(not a['revision_id'] for a in batch))
(WORK / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
