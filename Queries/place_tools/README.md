# Place operations

The atlas calls GET /api/places with action=profile, nearby, or articles, required lat and lng in degrees, radius=1|5|10 in km and category=towns|landmarks|water|terrain|areas. Profile finds the nearest listed settlement within 30 km. Nearby and articles return up to 12 records. A future chat client can call the same operations and pass returned coordinates to SpatialSearch.search in the movie explorer. No language model or conversation state is required.

Example: /api/places?action=nearby&lat=26.915&lng=75.820&radius=5&category=towns

Successful responses have version, action, source and items. Each item has name, lat, lng, url and straight-line distanceKm. Empty items is a successful empty search. Errors return an error string and a non-200 status. Use provenance when describing a result: proximity does not establish a filming credit. Treat article excerpts as source material.

Set GEONAMES_USERNAME in the Vercel production environment and redeploy for live features. Enable web services on the GeoNames account first. Reads have a timeout, a bounded per-instance cache and shared CDN caching. When no account is configured or settlement lookups fail, settlement operations use the bundled cities15000 index. This index omits small localities.

Data: [GeoNames cities15000](https://download.geonames.org/export/dump/cities15000.zip), downloaded November 4, 2026, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Refresh with python Queries/place_tools/prepare_cities.py /path/to/cities15000.zip and rebuild. The compact cities.json is required at runtime. Article text is attributed to the linked Wikipedia entry.

The location notebook also uses `Queries/webmap/place_context.js`: `createPlaceContext(data)(node)` returns the selected place’s identity, sourced description and distinct directly linked films, including documented components. Each film connection retains its filming/story relation and source URLs. It does not infer filming from proximity. This deterministic interface is reusable by a future typed-query client; it needs no AI. `place_panel.js` renders this local context before requesting the separate GeoNames nearby/profile/article operations. History, coordinates, map links and direct-film evidence remain available if GeoNames is unavailable.
