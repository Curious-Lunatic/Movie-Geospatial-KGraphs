# Heritage-site filming enrichment

The graph now contains **25 distinct film–UNESCO-property connections**, up from **5**, spanning **9 properties**, up from **3**. This adds **20 connections across 18 films**: 10 recovered from existing filming evidence through reviewed name matching, and 10 from newly inspected sources.

Twelve new source assertions were saved; two corroborate connections recovered from the existing data. Sources are never counted as additional distinct film–site connections.

| UNESCO property | Before | After | Added |
|---|---:|---:|---:|
| Red Fort Complex | 0 | 2 | 2 |
| Humayun's Tomb, Delhi | 0 | 7 | 7 |
| Qutb Minar and its Monuments, Delhi | 0 | 3 | 3 |
| Hill Forts of Rajasthan | 3 | 5 | 2 |
| Agra Fort | 1 | 1 | 0 |
| Fatehpur Sikri | 0 | 2 | 2 |
| Petra | 1 | 1 | 0 |
| Mountain Railways of India | 0 | 3 | 3 |
| Chhatrapati Shivaji Terminus (formerly Victoria Terminus) | 0 | 1 | 1 |

## What changed

`build_integrated_graph.py` reads the reviewed `site_aliases.csv` crosswalk. Exact same-site aliases such as Humayuns Tomb, Qutub Minar complex, Amer/Amber Fort and Darjeeling Toy Train now resolve to the correct UNESCO property or component. Country context is checked when supplied. The mapping file is hashed in graph provenance and each recovered Filmapia claim retains its original source row and full location string, with the identity mapping appended to its evidence. This changes site recognition, not the original source's evidentiary strength.

`enrich_heritage_locations.py` imports 12 inspected filming claims into `Dataset/enriched/location_assertions.csv`, synchronizes film summaries and adds the corresponding UNESCO place records. It verifies exact film IDs and Wikipedia identities, source snapshot hashes, source text and reviewed PDF page facts. `enrich_locations.py` retains these saved claims and places on subsequent base rebuilds.

The integrated graph and offline explorer were rebuilt. The older GIS project and demo snapshots are not refreshed.

## Evidence

- **Delhi Tourism Calendar 2018**, PDF pages 5 and 7: five films at Humayun's Tomb and three at Qutub Minar. Both pages were rendered and visually inspected. Source spellings Veer Zara, Chini Kam and Black And White were explicitly matched to the corresponding corpus films; the Kurbaan photograph identifies the 2009 film. Original PDF, extracted text and structured page facts are retained.
- **Incredible India, Fatehpur Sikri**: the official site overview names Pardes and Yamla Pagla Deewana among productions using the site. Other named films outside this corpus are omitted.
- **Wikipedia, Nilgiri Mountain Railway X class**: the filming account for the Chaiyya Chaiyya sequence connects Dil Se to the Nilgiri Mountain Railway component of the Mountain Railways of India.
- **Wikipedia, Chhatrapati Shivaji Terminus**: the station article identifies the Jai Ho sequence in Slumdog Millionaire as filmed there. That film is already in the supplied corpus.
- **Existing Filmapia snapshot**: ten already-present shooting claims gain UNESCO identities through reviewed aliases; their old source provenance is retained. UNESCO identity references are recorded in the alias crosswalk. These are not new external filming claims.

Heritage eligibility and representative coordinates use the existing `whc001.csv` snapshot, with the project cutoff of inscription by 2025. Components are linked individually, then grouped by parent property for the headline count. A place may have been filmed before its UNESCO inscription; this is a present-day classification under that cutoff.

The scope remains UNESCO World Heritage, matching the project's heritage dataset. An attractive old building, an ASI monument, or a tentative-list site is not automatically a UNESCO World Heritage property. City-level filming, nearby locations, replicas, denied filming permission and depiction-only references are excluded. The Red Fort calendar wording says filming occurred around the complex, so those calendar candidates were excluded. Existing site-specific Filmapia claims for Red Fort are retained.

Coordinates are representative site/component points, not camera positions. Source-supported claims are not independent verification. The new evidence does not assign filming locations to songs generally; a described film sequence supports a film-level location only. See `excluded_candidates.json` for reviewed exclusions.

## Reproduce

From the repository root, with the existing Beautiful Soup dependency installed:

```sh
python Queries/enrich_heritage_locations.py --apply
python Queries/build_integrated_graph.py --start-year 1970 --end-year 2025
python Queries/build_graph_explorer.py
python Queries/report_heritage_enrichment.py
python -m unittest discover -s Queries -p test_heritage_enrichment.py -v
python -m unittest discover -s Queries -p test_integration.py -v
```

Successful source snapshots are committed alongside their hashes and timestamps. `python Queries/fetch_heritage_sources.py --fetch` retrieves missing originals; `--only SNAPSHOT_FILENAME` limits a fetch. The government PDF server was slow, so the full PDF was completed with resumed downloads. The inspected structured facts are preserved as an explicit review input, not regenerated through unrestricted scraping.

`baseline.json` records the pre-change graph. `report.json` and `added_heritage_connections.csv` provide the verified totals and all 20 additions with their classification and provenance. `reviewed_evidence.json`, `assertions.csv` and `places.csv` retain the new claims. `idempotence.json` verifies that an offline reapply leaves enriched outputs unchanged. The 2 new matching tests and 6 existing integration tests passed; all 12 new assertions reached the graph and all 5 prior heritage connections remain.
