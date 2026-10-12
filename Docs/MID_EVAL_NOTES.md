# Satyendhran's integration contribution

For the mid evaluation on **14 October 2026**. The chat discusses a **3 pm** slot;
confirm the team's final booking separately if needed.

## Explain the contribution

The team's latest division of work changed my part to researching how to combine
the collected data. The implemented approach resolves movie identities across
the source datasets, preserves the original metadata and relationship evidence,
and creates normalized CSV tables plus an RDF knowledge graph.

Matching starts with shared Wikidata, IMDb, TMDB, Filmapia and Wikipedia identities.
A unique title and year provides a conservative fallback. Conflicting identities
and unresolved songs remain review items. This avoids treating two remakes as the
same movie or joining every actor, song and location into duplicated movie rows.

The graph separates **filmed at**, **story set in**, **cast member**, **directed
by**, and **song in film**. A movie filmed in a city does not prove its story is
set there, and its film location does not establish where each song was shot.

## Demonstrate the work

1. Open `Docs/INTEGRATION_METHOD.md` to show the compared integration methods and
   source-to-schema mapping.
2. Run `python Queries/build_integrated_graph.py`. Show 6,182 movie entities,
   5,378 film-linked songs and 57,589 sourced graph relationships.
3. Run `python -m unittest discover -s Queries -p "test_integration.py" -v`.
   Explain one conflicting-ID or wrong-song-year test.
4. Run `python Queries/query_integrated_graph.py --heritage "Taj Mahal" --radius-km 5`.
   Explain the Jodhaa Akbar → Agra Fort result, its source row, and the 2.14 km
   representative-point distance.
5. Show `Dataset/integration_demo/sparql_demo.csv` and `validation.json` for the
   executed provenance query and successful graph-structure validation.
6. Open `GIS/Good_Will_Mapping.qgz` in QGIS. Demonstrate the field-value joins,
   EPSG:32644 projection, 5 km buffer and spatial join using `Docs/GIS_WORKFLOW.md`.
   Show the source row in the result attributes and open the two print layouts.

The QGIS extension is now implemented and executed. For the GIS presentation,
open **`GIS/Good_Will_Mapping.qgz`** and follow **`Docs/GIS_WORKFLOW.md`**.
Show the attribute join, reprojected point layers, **5,000 metre buffer**, spatial
join and **2,144.978 metre** QGIS distance result. Use the actual application
screenshots in **`GIS/screenshots/`** and the two saved QGIS print layouts.
The Python merge supplies clean identity keys; QGIS performs the geographic
joins, mapping and projected distance analysis.

## Be precise when answering questions

**Why not join on titles alone?** Different films can share a title, and spellings
can differ. Strong IDs come first; unique title/year matches are a guarded fallback.

**Why keep original fields?** Sources can disagree. The attribute table and
crosswalk preserve both values and their original records for later review.

**Is it an LLM?** This contribution builds the data-integration and graph layer.
A future natural-language interface can query it and return the source evidence.

**Are the locations verified?** The graph preserves supplied source-supported
assertions. SHACL validates structure, not the historical truth of filming claims.
Unreviewed text candidates remain outside the main graph.

**Can we claim a movie was shot within 5 km?** The current demo compares reference
points of named sites. Precise shooting-coordinate and boundary-distance claims
need finer geometry and source evidence. Broad city/country points are excluded
from the default query.

**What is next?** Review ambiguous identities and song years, add checked place
aliases, collect precise filming geometry, and run the supplied distance query
in a GeoSPARQL-capable store. Song datasets currently cover only the supplied years.

The code, generated data and commit are local. Nothing has been pushed or
submitted to GitHub.
