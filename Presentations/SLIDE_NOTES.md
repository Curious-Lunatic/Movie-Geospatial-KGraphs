## Slide 1: Good Will Mapping

Geospatial knowledge graph of Indian cinema
Mid evaluation · 14 October 2026

Speaker notes: Source deck: https://docs.google.com/presentation/d/19AJkpIwel35Kh1gxN_7hzznjK3QnWGQlSNvKDjQ14uI/edit. Updated implementation and source snapshots as of 13 October 2026.

## Slide 2: Team

[["Name","Student ID"],["Vardaan Goel","2025117001"],["Vanshrajsinh Chauhan","2025117003"],["Soubhagya Ranjan Biswal","2025117010"],["Satyendhran L","2025117006"],["Abhinav PV","2025121015"]]

Speaker notes: Names and IDs follow the supplied team slide. The new integration/GIS refresh and presentation contribution belongs to Satyendhran. Existing collectors, the ontology extensions and heritage evidence include upstream team work.

## Slide 3: Project scope

Connect films, songs, credited people, characters, places and heritage sites.

Study geographic associations across the supplied 1970–2025 film corpus.

Keep the source evidence behind every accepted relationship.

Speaker notes: Implemented entity classes and relation counts: Dataset/integrated/summary.json. Event and Landscape classes are reserved without instances.

## Slide 4: Cinema geography

A film can link an audience to a real place, a story setting or a depicted heritage site.

Those links support research and tourism discovery when the evidence and spatial scope are explicit.

Speaker notes: This slide describes potential uses. No measured causal tourism increase is claimed.

## Slide 5: Filming and story settings

[["Relationship","Meaning"],["filmedAt","The source identifies a production location"],["setIn","The source identifies a narrative setting"],["inFilm","A song belongs to a film"],["partOfHeritage","A UNESCO component belongs to a property"]]

Speaker notes: Wikidata definitions: https://www.wikidata.org/wiki/Property:P915 and https://www.wikidata.org/wiki/Property:P840. Current ontology: Queries/cinema_ontology.ttl. A story-setting relationship does not establish a shooting location.

## Slide 6: Geographic questions

Which places are associated with Romance-tagged films?

Which UNESCO properties have filming connections across genres?

Which sourced film-location points fall within 5 km of a heritage reference point?

Speaker notes: Executed queries: Queries/knowledge_graph_queries/romance.sparql, heritage.sparql and the QGIS native spatial pipeline. Romance is a film genre, not a scene-level emotion label.

## Slide 7: Tourism discovery

Explore the sourced films linked to a named place.

Inspect each claim before treating the place as a visitor destination.

A broad city coordinate cannot identify an exact scene or camera position.

Speaker notes: Application proposal only. The current graph is a research demonstration and does not contain permit availability, opening hours, safety or access information.

## Slide 8: Research uses

Compare filming geography with narrative geography.

Group accepted heritage connections by film genre.

Trace a relationship to its input file, row and supporting evidence.

Speaker notes: Queries/build_graph_explorer.py exports reproducible aggregate results. Counts reflect the supplied corpus and unresolved geographic aliases.

## Slide 9: Source datasets

[["Source","Role in the current build"],["TMDB","Movie IDs, metadata, cast, roles and genres"],["Wikidata / Wikipedia","Film identity and geographic assertions"],["Song CSV batches","Song membership and scoped music credits"],["Filmapia snapshot","Existing filming-place assertions"],["UNESCO export","Property/component identities and coordinates"]]

Speaker notes: Input hashes and record counts are retained in Dataset/integrated/summary.json. IMDb IDs are already present as matching keys. Their presence does not imply IMDb location-page scraping.

## Slide 10: Collection workflow

Collectors request structured data through source APIs.

They parse JSON or article revisions and flatten records into CSV tables.

Caching, batching and retry delays reduce duplicate requests.

The integration imports those supplied exports without changing them.

Speaker notes: Repository collectors: Queries/fetch_wikidata_films.py, fetch_wikidata_bollywood.py, pull_tmdb.py and enrich_locations.py. This contribution rebuilds supplied snapshots, rather than claiming a new scraping run for every website.

## Slide 11: Wikidata locations

P915 stores a filming-location relationship.

P840 stores a narrative-location relationship.

P625 supplies a place coordinate when one exists.

SPARQL collectors retain film IDs and keep these meanings separate.

Speaker notes: https://www.wikidata.org/wiki/Property:P915 ; https://www.wikidata.org/wiki/Property:P840 ; https://www.wikidata.org/wiki/Property:P625 . Repository code: Queries/fetch_wikidata_films.py. Missing coordinates stay missing.

## Slide 12: Wikipedia and TMDB

Wikipedia enrichment retrieves article revisions and categories through the MediaWiki API. Text candidates retain evidence and review status.

TMDB requests supply movie details, credits and external IDs. Production-country metadata does not establish filming geography.

Speaker notes: https://www.mediawiki.org/wiki/API:Revisions . Repository code: Queries/enrich_locations.py, location_text.py and pull_tmdb.py. No claim that every article or soundtrack row has been independently reviewed.

## Slide 13: IMDb feasibility

A direct fetch of the Jodhaa Akbar filming-locations page returned HTTP 403. No records came from that attempt.

IMDb’s free dataset schemas omit filming locations. Its published guidance restricts automated website scraping.

A future IMDb import needs authorized access and confirmed field coverage.

Speaker notes: Checked 13 October 2026. Sample: https://www.imdb.com/title/tt0449994/locations/ . Official schemas: https://data.imdb.com/non-commercial-datasets/ . Usage guidance: https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX . One failed sample does not establish that all pages are inaccessible.

## Slide 14: Film coverage by decade

{"figure":"decades"}

Speaker notes: Exact counts from accepted films.csv rows. The 2020s bar covers 2020–2025 only. Films use their earliest observed release year. The source corpus includes shorts/documentaries and possible non-Bollywood records, so this is not a census of all Bollywood releases.

## Slide 15: Current graph

[["Movies",9509],["Songs",10708],["Credited roles",44416],["Source assertions",218993]]

Speaker notes: Dataset/integrated/summary.json. Period 1970–2025, inscription cutoff 2025. Distinct relationships: 211,297. People/credits: 33,524, genres: 19. Person-name credits are source-and-film scoped and are not a count of unique individuals.

## Slide 16: Movie identity resolution

Shared Wikidata, IMDb, TMDB and Wikipedia identities provide the primary joins.

A unique normalized title and year provides a guarded fallback.

Conflicting identifiers and ambiguous titles remain review items.

Speaker notes: Queries/build_integrated_graph.py and Docs/INTEGRATION_METHOD.md. The constrained merge rejects conflicting identifiers even through transitive links. It preserves source records and observed years.

## Slide 17: Evidence and quality

The crosswalk links original records to canonical film IDs.

Accepted assertions retain source file, logical row, URL and evidence where available.

Automatic text candidates remain outside accepted graph edges.

Missing evidence is never replaced with an inferred coordinate.

Speaker notes: Metadata preservation: film_attributes.csv, film_crosswalk.csv and claims.csv. Some legacy source snapshots lack original URLs or retrieval dates, and these are not invented. No numerical accuracy study or graph-embedding prediction is claimed.

## Slide 18: Songs, people and characters

[["Link","Identity rule"],["Song to film","Resolve film identity and check release year"],["Song to music credit","Scope name-only credits to source and film"],["Person to character","Scope the credited role to performer and film"],["Film to genre","Use the supplied TMDB genre taxonomy"]]

Speaker notes: Upstream extensions from original main, plus the current RDF identityScope export and validation. Songs are not assigned all film locations. Credited roles can include self appearances and compound role names.

## Slide 19: Knowledge graph example

{"figure":"outputs/14-october-review/deck_build/jodhaa_graph.svg"}

Speaker notes: Actual SVG exported from the current offline graph explorer after selecting Places and genres. The neighbourhood contains 14 visible neighbours and 46 direct film relationships in all categories. The complete graph contains 211,297 distinct assertion-backed relationships.

## Slide 20: QGIS joins

Join supported assertions to movies using canonical film IDs.

Join each assertion to its place geometry with a one-to-many field join.

Keep filming and narrative layers separate.

The updated project contains 22 persistent layers and nine linked-table relations.

Speaker notes: Native QGIS processing executed through PyQGIS: native:joinattributestable. Current project: GIS/Good_Will_Mapping_1970_2025.qgz. Report: GIS/qgis_report.json. https://docs.qgis.org/3.44/en/docs/user_manual/processing_algs/qgis/vectorgeneral.html .

## Slide 21: India geographic overview

{"figure":"GIS/india_overview.png"}

Speaker notes: Actual current QGIS print-layout export. 4422 filming features, 44 property points and 128 component points. Features represent assertions and can repeat a place or film. 5039 narrative features are available in a separate QGIS layer. Context boundaries are generalized QGIS bundled data.

## Slide 22: The 5 km spatial query

{"figure":"GIS/agra_5km_map.png"}

Speaker notes: QGIS reprojects Taj Mahal and local named-site filming points to EPSG:32644, buffers 5,000 metres, intersects points and joins target attributes by location. https://docs.qgis.org/3.44/en/docs/user_manual/processing_algs/qgis/vectorgeometry.html . It measures representative-point proximity, not UNESCO boundaries or camera positions.

## Slide 23: Agra query result

[["Film","Jodhaa Akbar"],["Filming reference","Agra Fort"],["Distance","2.145 km"],["Original record","Filmapia row 76"]]

Speaker notes: QGIS result: GIS/qgis_nearby_movies.csv. Projected distance 2,144.978 m. The independent spherical calculation returns 2,140.626 m and the same film/place pair. Both are reference-point models.

## Slide 24: Places in Romance-tagged films

{"figure":"romance"}

Speaker notes: Data: romance_places.csv. Counts distinct films per accepted place entity and relationship. Filming and narrative counts may overlap. Mumbai has 175 filming-linked Romance films and 129 narrative-linked Romance films. Geographic aliases are not all consolidated. Genre association does not classify scene emotion.

## Slide 25: Heritage connections across genres

[["UNESCO property","Films","Genres"],["Humayun's Tomb, Delhi","7","7"],["Hill Forts of Rajasthan","5","5"],["Fatehpur Sikri","2","5"],["Qutb Minar and its Monuments, Delhi","3","4"],["Agra Fort","1","3"],["Mountain Railways of India","3","3"]]

Speaker notes: Data: heritage_genres.csv. The graph links nine properties through 25 film/property pairs. A film can link to more than one property and more than one genre. Components are grouped under the corresponding property. Present-day UNESCO classification uses inscription by 2025 and does not imply historical designation at filming time.

## Slide 26: Validation and remaining limits

Eight integration regression tests passed.

Full RDF parsing and SHACL validation passed for 2,706,799 triples.

SPARQL results are checked against the exported tables.

Event and landscape instances, scene emotions and embedding predictions remain future work.

Speaker notes: Full validation: Dataset/integrated/validation.json. Regression tests: Queries/test_integration.py. Aggregate checks: graph_verification.json and validate_graph_queries.py. Structure checks do not establish the historical truth of source assertions. Review queue: 5,365 location candidates, 2,659 suspicious song rows and 335 unresolved song/film rows.

## Slide 27: Discussion

Live demonstrations
Knowledge graph explorer
QGIS joins and 5 km analysis

Next: review ambiguous identities and collect precise scene-level geographic evidence

Speaker notes: Open the packaged graph_explorer.html after extracting Dataset/knowledge_graph/knowledge_graph_1970_2025.zip. Open GIS/Good_Will_Mapping_1970_2025.qgz alongside its matching GeoPackage. Code and outputs prepared for the 14 October mid evaluation. External Google Slides deck remains unchanged.
