# Cinema atlas: spatial tools

The atlas is part of the existing graph explorer. The statistics and movie graph remain above it. Six tools share the same movie filters, graph IDs, evidence and result renderer.

| Tool | Calculation | Inputs |
| --- | --- | --- |
| Nearby | Haversine distance selection and a geographic circle | Place/map point; 0.1–500 km |
| Heritage | The same radius selection centred on a recorded heritage site | Heritage name; radius |
| Regions | Point-in-polygon overlay with state/district boundaries | State/union territory; optional district |
| Draw area | Polygon containment including holes and boundaries | Map clicks or coordinates; finish/undo/clear |
| Along a route | Road route → geographic corridor buffer → point-in-polygon selection | Start/end; car/walking/bicycle; 0.1–25 km corridor |
| Travel time | Road-network isochrone → point-in-polygon selection | Start; car/walking/bicycle; 5–120 minutes |

Common filters cover filming/story setting/both, genre, release years and heritage-only result locations. Movie counts are distinct within each selection. Multiple matching connections are preserved in the exports. Movies with missing coordinates or missing relationships cannot appear.

## Interface

- Tool tabs, compact control sidebar, a large map, collapsible movie filters and poster result cards.
- On smaller screens, controls stack above the map and tool tabs scroll horizontally.
- Light and dark themes follow the existing site setting.
- Results link to the movie graph, Google Maps and available source evidence.
- CSV exports contain every matching movie/place relationship, coordinates, source references, distance type and search filters.
- GeoJSON exports include the search geometry, actual route if applicable, and every matching movie/place connection. Open directly in QGIS.
- The existing deterministic typed-query parser is an optional **nearby-search** shortcut. It does not interpret arbitrary region, polygon or routing questions.

Examples: `Movies within 10 km of Agra Fort`, `Romance movies near Jaipur between 2000 and 2020`, `Movies set within 25 km of here`.

## Data and geographic limitations

Coordinates are representative points, often for cities, regions or heritage properties. They are not necessarily shooting addresses. Being near a heritage site does not establish a filmed-at relationship with that site. Corridor distance means distance from the route, not the driving distance required to leave it. Travel-time contours are modelled areas and are not per-location arrival-time guarantees or live-traffic predictions.

The committed `data/` folder contains **36 state/union-territory features and 735 district features**, plus a place-to-region join. These are generated from geoBoundaries revision `9469f09`. The source metadata reports 2011 for states and 2021 for districts; they are research layers and may differ from current administrative boundaries. Actual feature counts are used, rather than the upstream metadata's district count of 736.

Known India/state reference points are excluded from district results and district rankings. Otherwise a broad reference such as “Rajasthan” would incorrectly inflate the district containing its representative point. State results exclude the country reference, while retaining state-level records. Other unresolved granularity limitations are disclosed in the interface.

`boundary_sources.json` records the original metadata, source URLs, source hashes, licenses and preparation method. The state layer is licensed CC BY 2.5 IN; the district layer is ODbL 1.0 (Pathways Data / Local Government Directory). Derived boundary geometry and its membership index are distributed openly here with those source obligations. Movie records retain their own provenance.

## QGIS role and reproducibility

`Queries/prepare_spatial_boundaries.py` uses Shapely to repair geometry, simplify it with topology preservation at 0.001 degrees, set a 0.00001-degree coordinate precision grid, assign districts to states by greatest polygon overlap, and join place points to the resulting polygons. QGIS can inspect or reproduce those operations. **No new QGIS process is invoked by the website.**

To inspect an analysis in QGIS, drag the downloaded GeoJSON into QGIS. The file uses WGS 84 longitude/latitude. It contains both polygon/line analysis features and movie-location points; QGIS may offer separate geometry layers. Filter by `role`. For independent metre-based buffers, reproject to an appropriate local projected CRS first. Region source layers are also linked from the website.

The nearby-search tests compare against the existing saved `GIS/qgis_report.json` Taj Mahal/Agra Fort example: spherical web distance 2.1406 km, saved projected QGIS distance 2.1450 km. This checks consistency with earlier analysis, not a fresh QGIS run.

Build and test from the repository root:

```sh
# Only needed when regenerating boundary assets:
python -m pip install -r Queries/webmap/requirements.txt
python Queries/prepare_spatial_boundaries.py

# Regular website build uses the committed boundary assets:
python Queries/build_graph_explorer.py
node Queries/webmap/spatial_engine.test.cjs
node Queries/webmap/spatial_tools.test.cjs
python Queries/prepare_vercel_site.py
```

Source download caches are under ignored `outputs/boundary-sources/`. Use `--cache` to reuse an existing source download. The deployment builder copies the prepared layers and serves the large region GeoJSON gzip-compressed; it loads only when Regions is selected.

## Routing service

`spatial_tools.js` uses the public FOSSGIS Valhalla service at `https://valhalla1.openstreetmap.de`. It sends a request only after an explicit search, with the identifying `X-Client-Id: places-and-stories.vercel.app` header. The UI explains that selected coordinates are sent to this provider. There is no device geolocation request, bulk processing, background polling or automatic retry. One request may be active at a time, new calls are spaced at least 1.5 seconds apart, and up to 20 responses are cached for the session. Requests time out after 30 seconds and can be cancelled. Input changes prevent stale responses from updating the interface.

This public demonstration service has rate limits and no availability guarantee. Errors are displayed; a straight-line route or circular radius is never substituted for a failed road calculation. For sustained public traffic, supply an operated Valhalla endpoint through `SpatialTools.createRouter({base: 'https://your-routing-host'})` in the UI initialization. FOSSGIS/Valhalla asks public app owners to announce their applications through its GitHub Discussions; no external message was posted automatically.

References:
- https://valhalla.github.io/valhalla/api/route/api-reference/
- https://valhalla.github.io/valhalla/api/isochrone/
- https://valhalla.github.io/valhalla/
- https://www.geoboundaries.org/api.html

## Files

- `spatial_engine.js`: shared movie filters, deduplication, radius/area search and typed nearby queries.
- `spatial_tools.js`: polygon validation, geographic buffers, corridor distance and routing client.
- `spatial_ui.js`: controls, map drawing, asynchronous state, rankings and exports.
- `map_panel.html`, `map.css`: atlas markup, responsive styles and page refinements.
- `data/`: prepared boundaries, membership index and source/license metadata; required deployment assets.
- `vendor/`: Leaflet 1.9.4 and Turf 7.2.0 with their licenses; bundled locally.
- `*.test.cjs`: distance/geometry/filter/query, service error/cancellation/cache and boundary regression tests.

OpenStreetMap tiles and posters require internet. Local geographic selections operate on downloaded data; routing requires the external service. Tiles use ordinary on-demand loading with visible attribution, without offline tile prefetch.
