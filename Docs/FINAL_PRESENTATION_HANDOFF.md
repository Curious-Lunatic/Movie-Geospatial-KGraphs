# Material for the slides and report owner

Requested emphasis: **very short project recap; geospatial chat and live demo**.
This is copy-ready material; it does not replace the teammate's deck or report.

## Suggested slide sequence

1. **Problem and objective — 20–30 seconds.** Connect cinema, people, music and
   geographic evidence; answer location questions through a conversational UI.
2. **Data and method — one slide.** Supplied 1970–2025 corpus; compatible external
   film IDs; typed relationships; source file/row; geometry; review lists.
   Current build: 9,509 films, 10,708 songs, 7,372 geocoded place identities.
3. **Chat-to-map workflow.** Question → deterministic intent/filter parser →
   existing graph/spatial engine → distinct films and evidence → map/export.
   Support: nearby, states/districts, film connections and contextual refinements.
4. **Live demo: nearby and follow-up.** Taj Mahal, 5 km: 14 films / 2 places.
   “Only heritage”: Jodhaa Akbar / Agra Fort, 2.141 km spherical point distance.
   Show `GIS/screenshots/2026-11-11/01-chat-heritage.jpg`.
5. **Live demo: region and film graph.** Romance in Rajasthan: 46 films / 16
   places; “after 2010”: 20 / 11. Fanaa supplies all six entity categories.
   Show `02-chat-region.jpg` and `03-chat-film-evidence.jpg` from the same folder.
6. **GIS interoperability.** Download actual query geometry and matching movie
   points as GeoJSON. Open the prepared `GIS/chat_demo/Chat_Query_Demo.qgz`.
   The website is not running QGIS processing or a QGIS server.
7. **Evaluation and limitations.** 32 JavaScript tests, eight integration tests;
   real-data chat/map benchmark and actual browser export. Direct RDF projection
   and sampled provenance validated, with query/CSV agreement. This November
   verification did not rerun full-graph SHACL. No invented accuracy percentage.
   Representative coordinates, incomplete evidence, research boundary dates,
   controlled question patterns and local-data coverage limit the answers.

Do not label the 41 film-linked heritage identities as 41 UNESCO World Heritage
properties: upstream now also includes documented historic sites and components.
Do not label 7,372 place identities as unique shooting addresses. The graph's
filming and narrative links remain separate. No unverified Jeans/Genie import
was added; Fanaa is the tested example.

## Report-ready implementation paragraph

The system integrates supplied cinema and heritage snapshots through compatible
external identifiers and guarded title/year matching. Supported assertions retain
their source file, row, method and available evidence. A deterministic chat layer
maps supported questions and follow-up refinements to explicit filters. Nearby
queries use spherical point distances, while state and district questions use
point-in-polygon selection on published boundaries. The chat and existing map
share the same selection engine and canonical entity identifiers. Responses
display distinct film counts, interpreted filters and evidence references. Film
queries expose soundtrack, cast, character, genre, place and heritage links.
Results can be inspected in the graph and exported as CSV or GeoJSON for QGIS.
Ambiguous identities, unavailable records and unsupported questions are reported
explicitly. No model-generated facts are inserted into the accepted graph.

## Research-paper outline for later

Title suggestion: *Evidence-Preserving Cinema Knowledge Graphs for Conversational
Geospatial Exploration*. Sections: motivation and research questions; related
work; dataset and coverage; ontology and identity resolution; evidence model;
chat query planning; spatial methods; reproducible experiments; limitations;
conclusion. Add a labelled question set before reporting parser accuracy or
benchmark comparisons. The current regression suite checks selected scenarios;
it is not a measured accuracy rate on arbitrary natural-language questions.
