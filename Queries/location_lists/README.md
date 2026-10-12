# Location-first Wikipedia enrichment

Completed for the existing 1970–2025 film corpus. The original source CSVs remain intact; the enrichment tables and integrated graph are updated.

## Results

| Measure | Count |
|---|---:|
| New distinct film–filming-location connections | 63 |
| Films with new locations | 53 |
| Films gaining their first supported filming location | 21 |
| Distinct places represented by new connections | 13 |
| New place entities | 9 |
| Supported film–location pairs before | 3236 |
| Supported film–location pairs after | 3299 |
| Source assertions retained, including corroborating evidence | 1533 |
| Unique source pages including category pagination | 55 |

The headline count is **63 new connections**, not the 1,533 source assertions. A film linked to two places contributes two connections; an additional source for an existing connection contributes zero. Counts compare with the frozen pre-import `baseline.json`, using film and place IDs. They refer to `Dataset/enriched`, before the integrated graph's separate identity reconciliation.

## Additions by place

| Place | New connections |
|---|---:|
| Rajasthan | 22 |
| Varanasi | 20 |
| Udaipur | 3 |
| Jodhpur | 2 |
| Jaisalmer | 2 |
| Bikaner | 5 |
| Jaipur | 3 |
| Mandawa | 1 |
| Gajner Palace | 1 |
| City Palace, Jaipur | 1 |
| Bagore-ki-Haveli | 1 |
| Birla Mandir, Jaipur | 1 |
| Nagaur | 1 |

All nine new place records have representative coordinates from their Wikipedia geographic articles.

New place entities: Bagore-ki-Haveli, Bikaner, Birla Mandir, Jaipur, City Palace, Jaipur, Gajner Palace, Jaisalmer, Jodhpur, Nagaur, Udaipur.

## Sources and method

The [Rajasthan list](https://en.wikipedia.org/wiki/List_of_films_shot_in_Rajasthan) and [Varanasi list](https://en.wikipedia.org/wiki/List_of_films_shot_in_Varanasi) supply film entries. Direct members of location categories such as [Films shot in Jaipur](https://en.wikipedia.org/wiki/Category:Films_shot_in_Jaipur) supply additional source evidence. The selected categories span major Indian and international locations; see `sources.json`. The existing corpus already contains almost all matching category evidence, so the net additions in this run come from the location lists.

Only exact Wikipedia film-page identities are accepted, including year disambiguation. No fuzzy title matches, new films, television sections, category subtrees, reference links or navigation links are imported. Unmatched entries (mostly non-corpus films, but also unresolved aliases) are recorded separately and excluded from the totals. This conservative join can miss valid matches.

A list's overall location supplies only that city/state. More specific Rajasthan places are extracted only when the same film entry explicitly links that place. Red links and unlinked place text are not automatically promoted. Geographic article coordinates are representative points, not exact shooting positions. Blank coordinates remain blank.

These are Wikipedia editorial assertions, marked `source_supported` consistently with the project's existing category method. They are not independent confirmation or primary-source verification; the Rajasthan article itself requests more citations. Source URLs, revision IDs, retrieval timestamps, evidence text and raw HTML with hashes are retained. Wikipedia content is subject to its attribution and CC BY-SA terms; retain provenance when redistributing.

## Files

- `sources.json`: selected source pages, place mapping and section/entry filters.
- `snapshots/`: cached public HTML and retrieval/hash metadata, including geographic pages.
- `assertions.csv`: all accepted evidence, including corroborating sources.
- `added_film_locations.csv`: exactly one row for each of the 63 new connections.
- `places.csv`: place records used by this batch, for reproducible base-pipeline imports.
- `baseline.json`: pre-import distinct filming pairs, place IDs and file hashes.
- `report.json`: machine-readable counts, provenance manifest and failures.
- `unmatched_films.csv`: entries with no unique exact corpus identity.
- `discovery_failures.json`: proposed categories that were missing or had no direct film entries; not imported.
- `validation.json`, `idempotence.json`: executed checks.

## Reproduce

From the repository root:

```sh
python -m pip install -r Queries/requirements-location-lists.txt
python Queries/enrich_from_location_lists.py --apply
python Queries/validate_location_lists.py
python -m unittest discover -s Queries -p test_location_lists.py -v
python Queries/build_integrated_graph.py --start-year 1970 --end-year 2025
python Queries/build_graph_explorer.py
```

`--fetch --apply` downloads missing snapshots; existing snapshots are reused. The offline command requires only the current enrichment CSVs and saved snapshots, so it works independently of unavailable inputs/caches needed by the older enrichment pipeline. Reapplying is byte-for-byte idempotent for the three enriched tables, as recorded in `idempotence.json`. `enrich_locations.py` also imports the saved assertions and places when its original inputs are available, so a base rebuild retains this batch.

New assertions are appended as evidence and existing evidence is preserved. Original filming/narrative source CSVs are not edited. The film summary's supported filming locations and source attribution are synchronized. The graph and offline explorer are rebuilt; the older GIS project and demo snapshots are not refreshed by this workflow.

## Validation

Three extraction tests and six existing integration tests passed. All 1,533 imported assertions reached the integrated graph with revision IDs and retrieval timestamps. The enriched summaries, place references, deduplicated additions and before/after counts reconcile. An offline reapply leaves all three enriched CSVs byte-for-byte unchanged.
