# Cinema atlas: run, review and reproduce

This is a Bollywood/Hindi-cinema project with filming references worldwide.
The canonical film list comes from the team's supplied datasets. A source's
language does not establish a film's language or industry. Discovery stays
bound to that film list; unrelated regional films are not automatically added.
The cached metadata identifies 7,894 films as originally Hindi. Another 550 are
only listed as Hindi in a supplied source, 1,064 have unconfirmed scope metadata,
and one reviewed record is multilingual with a Hindi version. These categories
are visible in Data quality; the full film count is not a claim that every
record's production language has been independently verified.

## Open the atlas

From the repository root:

```powershell
rtk proxy python Queries/build_integrated_graph.py
rtk proxy python Queries/build_graph_explorer.py
rtk proxy python Queries/build_atlas_product.py
rtk proxy python Queries/serve_demo.py --port 8769
```

Open `http://127.0.0.1:8769/atlas.html`. Use an unused port if you already have
a demo running. The original graph explorer remains available from its link.
The atlas needs an HTTP server, including when using the portable download.
Opening its HTML directly with `file://` cannot fetch the compressed assets.

The public version is read only. Search, graph evidence, map filters, journeys,
timelines, region comparisons and supported questions work in the browser.
Review editing requires the loopback-only local server. The public build never
includes the private review SQLite database, scraped page caches or credentials.

## Suggested demonstration

1. Search **Fanaa**, open its connections, and select Songs & music or People &
   characters. The all-relationships diagram gives each recorded entity category
   space; the full relationship list remains available below it.
2. Ask **Where was the song Bismil filmed?** Open its source evidence. Film
   locations are never automatically assigned to individual songs.
3. Ask **Movies within 5 km of Taj Mahal**, then **only Romance** or
   **between 2000 and 2020**. The answer states the interpreted filters.
4. Open Map & journeys. Use a suggestion's stable record ID when names are
   ambiguous. Change the radius, release-year range, genre and precision filter.
   Hollow points are broad references; named-site points still do not establish
   the camera position. Download the actual selected points as GeoJSON.
5. Plan two to eight stops, one name or record ID per line. The first stop stays
   fixed. The result minimizes straight-line distance over all stop orders;
   actual road travel uses the separate road tool in the classic explorer.
6. Open Time & regions, select a release year and play the reference-point map.
   Release year is not filming date. Compare states and download regional counts.
7. Use Data quality to show both accepted coverage and pending discovery work.

## Review and scene evidence

Review desk imports completed CSV snapshots without editing the original runs.
Select a candidate, resolve its canonical film, song and place, check the source,
and approve, reject, correct or flag a conflict. Every saved decision increments
its version and appends an audit event. A stale editor cannot overwrite a newer
decision. Export creates `Queries/curation/approved_records.json`; rebuilding
applies approved records to the graph and regenerates the browser catalogue.

New scene proposals remain pending. Optional start/end seconds, scene URL,
coordinate uncertainty and source-reported shooting coordinates are stored as
claim qualifiers. A shooting-coordinate claim needs explicit review, a scene
reference, valid coordinates and its coordinate-source URL. These qualifiers
do not silently replace a named site's representative geometry. Do not invent
timestamps, camera positions or numeric confidence scores.

Song identities include the canonical film ID, so remakes cannot merge merely
because they share a title. Reviewed title aliases are in
`Queries/curation/rules.json`; possible short-title/version pairs appear in the
duplicate review list. Uncertain language/version variants stay separate until
their identity is reviewed. Add aliases only with an appropriate source.

## Continue discovery without touching earlier runs

```powershell
rtk proxy python Queries/scrape_song_locations_v2.py --resume --max-requests 2000 --max-jobs 10000 --languages en,hi
```

The default output is `outputs/discovery-v2`. Page revisions are fetched in
batches of up to 20; searches and pages alternate. The queue retains every
pending job when a budget is reached or the process pauses. Search continuation
pages are queued. Crashed workers' expired leases can be recovered. Each run
has a request budget, not a silent dataset ceiling. Use `--offline` to process
existing caches without network requests. The original scrape folders are read
only to this worker. One process per output directory is recommended.

English and Hindi are the defaults. Additional supported Wikipedia editions
can be configured, but translation/transliteration coverage is incomplete.
Conservative text matching can miss valid native-script song/place variants;
that is a documented recall limit, not evidence that no locations exist.
All extracted matches require review. Provider refusals/rate limits stop access;
`--retry-blocked` is an explicit later retry after the provider issue is resolved.
TMDB metadata does not establish song filming. IMDb access is not bypassed;
the earlier collector supports authorized evidence imports.

The queue can finish all scheduled work and still miss songs with no accessible
source. The current accepted dataset has **54 links for 49 songs**; pending
candidate counts are not accepted facts or complete filming coverage.

## Native QGIS analysis

On this machine:

```powershell
rtk proxy "C:\Program Files\QGIS 4.0.0\bin\python-qgis.bat" Queries/build_regional_analysis.py
```

Open `GIS/analysis/Regional_Analysis.qgz`. All layer paths are relative. The
workflow fixes the supplied research boundaries, executes native point-in-
polygon counts, counts distinct film IDs and song IDs, reprojects reference
points and executes QGIS kernel-density estimation. An independent distinct-ID
intersection calculation reconciles every regional count.

The saved execution uses 152 Indian filming reference points, 2,225 distinct
film/place links and 28 song/place references across 771 state/district polygons.
States retain 2011 boundary dates; districts retain 2021 dates. Song counts in a
polygon are distinct songs, not the number of production visits. A film or song
can occur in multiple polygons; summing overlapping administrative levels
double counts entities.

The density raster gives each unique reference place one equal weight. It uses
a 100,000 metre quartic kernel and 5,000 metre pixels in a custom WGS 84 AEQD
projection centred at 22° N, 79° E. Distance distortion varies away from its
centre. City/region reference points can create artificial clusters. This is
exploratory reference density, not a statistical significance test, a filming-
event count or a map of exact shooting addresses.

## Tests and portable release

Install `rdflib` and `pyshacl` for RDF tests and Node.js for the browser engines.
The normal graph/catalogue build otherwise uses Python's standard library.

```powershell
rtk proxy python Queries/evaluate_atlas.py
rtk proxy python Queries/verify_cinema_graph.py
rtk proxy python Queries/build_release.py --skip-build
```

The release builder also rebuilds the graph, explorer, atlas and evaluation
when `--skip-build` is omitted. QGIS is a separate explicit build step so machines
without it can consume the retained, attributed spatial artifacts.

`outputs/release-site` is suitable for static hosting. Its download archive
contains the atlas, public datasets, compressed RDF/claim tables, QGIS outputs,
evaluation and file hashes. Extract it and run `rtk proxy python -m http.server
8771 --bind 127.0.0.1` from that extracted folder. Local review writes require the
repository's `serve_demo.py`, rather than that static server.

The evaluation reports measured search timing and initial catalogue bytes.
RDF verification checks the direct graph, a provenance sample, every song-location
provenance record and the Song shape. It does not claim full-graph SHACL coverage
or independent validation of every real-world source assertion. Retained source
websites, Wikipedia/UNESCO material, OSM tiles and vendor libraries keep their
respective attribution and reuse conditions.
