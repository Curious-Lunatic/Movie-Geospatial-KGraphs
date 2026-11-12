# Place quality, wider spatial search and song geotags

This contribution extends the November conversational demo. It was synced with
upstream `main` at `1094d0a` before implementation; no newer upstream commit was
available. Historical October maps and November 11 reports retain their dates.

## What changed

- Map markers, search choices, result cards and exports identify city, country,
  region, named venue and heritage references separately, with coordinate precision.
  City points use hollow markers. Unknown types remain explicitly unclassified.
- Chennai remains the city Q1352. Fort St. George Q1438739 is a separately sourced
  landmark reference, and UNESCO property 249 remains **Group of Monuments at
  Mahabalipuram**, at Mamallapuram. These are different entities. No film assertion
  was created just because a landmark is near Chennai.
- Named heritage references can be shown independently of movie links. The place
  notebook preserves the selected site's identity when displaying a nearby town.
  The local demo now supplies settlement context from the bundled GeoNames index.
  Live-only article/other-feature lookups fail explicitly when unavailable.
- Nearby/heritage radii support **0.1–2,000 km**, with a slider and presets. Route
  corridors support **0.1–250 km**. Existing polygon, region and travel-time tools
  remain available. Road calculations still require an explicit provider request.
- Search uses recorded aliases and Unicode labels, including Madras and சென்னை.
  Ambiguous place names offer stable record choices. An optional filter excludes
  classified city/country/region points before counting movies.
- Song locations are explicit `Song → songFilmedAt → Place` relationships. They
  appear in chat, the map, film graph, place notebook, RDF and GeoJSON exports.
  Film locations are never copied onto songs.
- A geotag form accepts an existing song, place, coordinate, precision, evidence
  URL, explanation and optional scene timestamp. It downloads a **proposed** JSON
  record for review; it does not edit the accepted graph or upload to a server.

## Demonstration

```sh
python Queries/build_integrated_graph.py
python Queries/build_graph_explorer.py
python Queries/serve_demo.py --port 8768
```

Open `http://127.0.0.1:8768/graph_explorer.html#chat`. Try:

1. **Heritage sites within 100 km of Chennai**: Fort St. George at 1.33 km and
   Group of Monuments at Mahabalipuram at 52.58 km. Both have zero direct recorded
   film links in this snapshot. Click Fort St. George, then Nearby town: the site
   title remains Fort St. George while Chennai is labelled settlement context.
2. **Movies within 1000 km of Chennai**: 409 distinct movies / 53 matching places.
   Results identify broad city references; these are not camera positions.
3. **Which songs were filmed where?**: two explicit source-supported links.
4. **Where was the song Chaiyya Chaiyya filmed?**: Nilgiri Mountain Railway, a
   railway-component reference point. The exact train position/segment is unknown.
5. **Where was the song Gerua filmed?**: Iceland, a country reference. This source
   does not justify choosing a particular waterfall, beach or camera position.
6. **Song locations for Fanaa**: zero accepted tags. Soundtrack membership and film
   filming locations exist separately; neither proves an individual song location.
7. Open **Propose a song location or scene geotag**, choose a song, add evidence
   and download the proposal. Review it before adding a curated source record.

The song GeoJSON uses `[longitude, latitude]` in WGS 84, with source URL, evidence,
song/film/place IDs, precision and status on each feature. Open it in QGIS as a
point layer and inspect these attributes. A country or route centroid must not
be interpreted as an exact filming site or used for precise proximity claims.
Nearby-song searches omit country/locality/unknown tags; route results are only
distance to a route reference point, not distance to the full railway geometry.

## Data coverage and evidence

The rebuild has 9,509 films, 10,709 songs, 8,579 places and 219,017 source assertions.
There are **two** accepted song-location links, and **48** existing location notes
still awaiting review. This is a supported initial feature, not complete song
geolocation coverage. New song performer/composer credits were not guessed.

Place profiles include 431 public Wikidata records, plus three reviewed identity
overrides. Of 8,579 place entities, 1,347 remain unclassified; the rest include
heritage properties/components and classified cities/countries/regions/venues.
Original geometry and movie assertions were retained. Classification is based on
an exact allowlist of instance-of labels, not a complete type-hierarchy reasoner.

Sources: [Chennai District](https://chennai.nic.in/about-district/),
[district heritage descriptions](https://chennai.nic.in/tourism/places-of-interest/),
[UNESCO property 249](https://whc.unesco.org/en/list/249/),
[Fort St. George Wikidata identity](https://www.wikidata.org/wiki/Q1438739),
[existing railway source](https://en.wikipedia.org/wiki/Nilgiri_Mountain_Railway_X_class),
[official Iceland production listing](https://filminiceland.com/made-in-iceland/dilwale).
Source snapshots/revisions/hashes and own-word evidence summaries are retained.

## Validation and deliverables

42 JavaScript tests and 15 Python tests passed. Browser checks covered named
Chennai identities, local settlement context, 1,000 km search, the 250 km corridor
control, song evidence, missing Fanaa geotags, GeoJSON export and the proposal form.
The direct RDF projection and sampled provenance were parsed, aggregate queries
were reconciled, and both song claims and the song SPARQL query were checked.
Every song passed SongShape on the direct projection. Full-graph provenance SHACL
was not rerun. The 31.9 MB public bundle was prepared; it was not deployed.

- Current generated graph and explorer: `Dataset/integrated/` (rebuilt, gitignored).
- Current portable atlas: `Dataset/knowledge_graph/atlas_2026-11-12.zip`, with
  verified extraction hashes and explicit projection-level validation metadata.
- Reproducible sources and code: `Queries/place_profiles/`, `Queries/song_locations/`
  and `Queries/webmap/`.
- Executed result snapshots and browser-exported GeoJSON: `Dataset/song_demo/`.
- Actual browser screenshots: `GIS/screenshots/2026-11-12/`.
- This task did not execute a new native QGIS analysis. Earlier QGIS projects and
  screenshots remain separate historical evidence; the new GeoJSON is importable.

Validate a downloaded proposal locally with:

```sh
python Queries/validate_song_geotag.py path/to/proposed-song-geotag.json
```

Successful schema validation keeps status `proposed`; it is not evidence approval.
After manual source review, add an explicit canonical-film/place record to
`Queries/song_locations/reviewed.json`, store the supporting source snapshot, and
rebuild. Exact film ID/year and source-token checks guard that import.
