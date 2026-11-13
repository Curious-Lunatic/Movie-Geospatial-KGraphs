# Review of the 437-row song-location scrape

The completed source run saved **437 candidate rows for 124 distinct songs**,
across 132 distinct song/evidence groups. These were possible matches, not 437
verified filming locations. Every row received a recorded review decision.

| Decision | Rows |
|---|---:|
| Imported as source-supported song/place links | 52 |
| Rejected as unsupported location evidence | 294 |
| Excluded as duplicate, wrong identity or unrelated context | 72 |
| Held for further identity/source review | 19 |

The 52 imported links cover 47 songs. Including the original two links, the
rebuilt graph has **54 song/place links for 49 songs**. It contains 10,742 songs,
8,595 places and 219,102 source assertions; 33 new film-scoped song identities
and 16 new place references were introduced. Movie-level filming assertions did
not increase. Full snapshot counts are in `Dataset/song_review/summary.json`.

## What verification means

The review checked the saved source statements, film/song identity, the clause
that actually names the filming location, duplicates, and geographic precision.
New place coordinates were reconciled with the saved primary-coordinate API
responses. These are **source-supported claims**, not independent confirmation
from production crews or verified camera coordinates. Existing geometry was kept.

The public snapshots retain URLs, source revisions/retrieval times, original
cache hashes, short excerpts and our own evidence summaries. The original 437-row
CSV and full cached paragraphs remain under ignored `outputs/`; they were not
changed. `outputs/song-location-review/decisions.csv` records all row decisions,
and a portable decision table is included under `Dataset/song_review/`.

Examples of decisions:

- Generic entries named “The”, “Cathedral” or “Monastery” were not treated as
  identified shooting sites. Actor names and production company names were excluded.
- A song called Burj Khalifa does not prove it was filmed at that tower. Its
  source supports Dubai at city precision.
- Sydney is in a separate clause from Khuda Jaane's Italy locations; it was excluded.
- A recreated Colosseum set at Film City does not establish filming at the Roman site.
- Norbulingka in Tibet was not accepted for a source describing an Indian location.
- A filming reference **near** Humayun's Tomb was held rather than becoming a
  filmed-at assertion for the tomb. A Mahabalipuram locality reference was not
  automatically promoted to the UNESCO property's identity.
- Language-version and shortened-title ambiguities were retained for review.

Named-site examples now in the explorer include Bismil / Martand Sun Temple,
Sab Tera / Poda Island, Ishq Sufiyana / Bidar Fort, and several songs / Film City.
Coordinates retain named-site, city, region or country reference precision.
The original 48 supplied song-location notes are a separate review queue; they
were not automatically resolved by this scrape's decisions.

## Reproduce and inspect

```powershell
rtk proxy python Queries/build_integrated_graph.py
rtk proxy python Queries/build_graph_explorer.py
rtk proxy python Queries/serve_demo.py --port 8768
```

Open `http://127.0.0.1:8768/graph_explorer.html#chat` and try `Song locations`,
`Where was the song Bismil filmed?`, or `Where was the song Sab Tera filmed?`.
The current portable archive is `Dataset/knowledge_graph/atlas_2026-11-12.zip`.

Validation: 42 JavaScript tests, 40 Python tests, direct RDF/CSV reconciliation,
all 54 song-claim provenance records, and all-song SongShape checks passed.
Browser checks confirmed both named-site examples and the 54-link result.
Full-graph provenance SHACL was not rerun. No native QGIS processing or public
website deployment was performed for this review; existing GIS projects remain
separate historical deliverables. Actual screenshots are saved under
`GIS/screenshots/2026-11-12/song-review/`.

## Discovery is not exhausted

There were no request errors reported in this source run. It reached the configured
**50,000 source-page ceiling**, with 11,279 automatic discovery queries remaining.
Its final JSON did not mean every location/song had been searched. A later run can
raise the ceiling with `--limit 100000 --resume`; this is optional and was not
started automatically. No current scraping process was stopped or reconfigured.
The scraper now filters generic place aliases and title-only matches on future
runs; all candidates still require review before graph import.
