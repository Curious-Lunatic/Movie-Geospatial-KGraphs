# Executed integration demo

Run locally on 12 October 2026 using the team's repository snapshots. Rebuild with
`python Queries/build_integrated_graph.py` before repeating the queries.

| Measure | Result |
|---|---:|
| Movie entities, earliest observed year 2000–2025 | 6,182 |
| Film-linked song entities | 5,378 |
| People with TMDB credits | 15,063 |
| Geographic place entities | 8,572 |
| Heritage properties inscribed through 2025, worldwide | 1,248 |
| Separate heritage components | 5,645 |
| Usable geographic points | 7,330 |
| Sourced relationships | 57,589 |
| Filming/narrative relationships | 11,469 |
| Movies with a supported filming assertion | 1,366 |
| Movies with a supported story-setting assertion | 1,301 |
| Preserved source attribute values | 196,132 |
| Location assertions kept for review | 4,983 |

`summary.json` records the source counts and SHA-256 input hashes. These are counts
of resolved records in the supplied corpus, not a verified census of Bollywood.

## Spatial demonstration

```sh
python Queries/query_integrated_graph.py --heritage "Taj Mahal" --radius-km 5
```

The result in `taj_mahal_5km.csv` is **Jodhaa Akbar (2008)** at **Agra Fort**, with
a representative-point distance of **2.140626 km** from the Taj Mahal reference
point. Its provenance is logical row 76 of `filmapia_film_locations.csv`.
This measures reference-point proximity, not a verified camera position or the
distance between site boundaries. The default query excludes broad city/country
coordinates. Heritage component identities stay separate from parent properties.

## Validation evidence

Five regression tests pass. They exercise conflicting identity chains, duplicate
titles/remakes, alternate-title identity components, Hindi combining marks,
coordinate axis order, review-only assertions, incorrect song years and the
rule against inheriting film shooting locations onto individual songs.

`validation.json` records a successful full RDF parse and SHACL check:
**767,435 RDF triples**, **57,589 reified source statements**, and matching RDF/CSV
entity counts. The executed basic SPARQL demonstration returns **9 provenance
rows**, recorded in `sparql_demo.csv`. The report includes the exact graph hash.

The GeoSPARQL-store distance example is supplied for future store deployment.
It has not been run in a GeoSPARQL engine. The Python spatial query above was run.

## Issues to explain during evaluation

The build reports 20 rejected conflicting-ID merges, 24 ambiguous title/year
groups, 424 movie-year disagreements, 124 unresolved song-film rows, 14 song
location notes requiring review, and 26 standalone song records needing a film
mapping. Counts describe issue records, not mutually exclusive film populations.
They remain visible rather than becoming guessed graph facts.

No upstream dataset was edited. Full normalized tables, RDF and map outputs
remain locally available in `Dataset/integrated/` and are reproducible from code.
