# Good Will Mapping: dataset integration

This repository contains the team's movie, song and heritage source datasets.
Satyendhran's integration contribution combines them into a reproducible graph
for the 14 October 2026 mid evaluation.

Read [the method and source mapping](Docs/INTEGRATION_METHOD.md) and
[the executed demo results](Dataset/integration_demo/README.md).

## Run the contribution

From the repository root, Python 3.9+ is sufficient for the merge and distance demo.
No API keys, downloads or database server are required for these commands:

```sh
python Queries/build_integrated_graph.py
python Queries/query_integrated_graph.py --heritage "Taj Mahal" --radius-km 5
python -m unittest discover -s Queries -p "test_integration.py" -v
```

The build writes `Dataset/integrated/`:

| Output | Purpose |
|---|---|
| `films.csv` | One canonical movie entity per accepted identity group |
| `film_crosswalk.csv` | Map original source records to movie entities |
| `film_attributes.csv` | Preserve all nonempty source metadata with provenance |
| `people.csv`, `songs.csv` | People and film-linked songs |
| `places.csv` | Place/heritage/component identities and usable coordinates |
| `claims.csv` | Supported graph edges with source file, row, method and evidence |
| `location_review.csv`, `issues.csv` | Claims and matches requiring review |
| `places.geojson` | Geographic point layer for QGIS |
| `graph.ttl` | RDF projection with typed relations, GeoSPARQL WKT and provenance |
| `summary.json` | Counts, issue totals and SHA-256 hashes of source inputs |

Derived files are ignored by Git and regenerated locally. A small, executed
result snapshot is committed in `Dataset/integration_demo/`; source CSVs stay intact.

Optional RDF/SPARQL/SHACL verification:

```sh
python -m pip install -r Queries/requirements-integration.txt
python Queries/validate_integrated_graph.py --report Dataset/integrated/validation.json
```

The validator writes `sparql_demo.csv`. A GeoSPARQL-store query is provided in
`Queries/integration_nearby_geosparql.sparql`; RDFLib does not execute its distance
extension. Use the Python query for the available offline spatial demonstration.

## Mid-evaluation demonstration

1. Show the source mapping and identity-resolution choices in the method document.
2. Run the build and show the movie/song/heritage counts and review issues.
3. Open `Dataset/integrated/places.geojson` in QGIS with **Add Vector Layer**. The
   file supplies longitude/latitude geometry; filter `place_id` starting with
   `heritage:` or `heritage-component:` to show the heritage layer.
4. Run the Taj Mahal query. The supplied Filmapia snapshot links **Jodhaa Akbar
   (2008)** to **Agra Fort**, whose representative point is about **2.141 km** from
   the Taj Mahal representative point. The claim's original CSV row remains visible.
5. Explain why a filming relation, story setting, and a song-film membership are
   separate edges. Show an unresolved song-year or identity conflict in `issues.csv`.

The map is worldwide because Hindi films have international locations. Use
`country_codes` containing `IN` for Indian heritage properties/components.
All distances are between representative points. Source-supported assertions
are evidence from the named input, not independently verified shooting positions.
