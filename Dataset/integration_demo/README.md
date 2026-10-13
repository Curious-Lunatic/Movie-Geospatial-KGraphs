# Executed integration demo — 13 October 2026

Scope: supplied source corpus, 1970–2025. This is not a verified Bollywood census.

| Measure | Result |
|---|---:|
| Resolved films | 9,509 |
| Film-linked songs | 10,708 |
| Person / credit entities | 33,524 |
| Film-specific credited roles | 44,416 |
| Genres | 19 |
| Places | 8,579 |
| Sourced assertions | 218,993 |
| Distinct sourced relationships | 211,297 |
| RDF triples | 2,706,799 |

Eight regression tests passed. Full RDF parsing, SHACL and RDF/CSV entity counts
passed. Aggregate SPARQL results match exported CSVs: 944 romance rows, eight
multi-genre heritage rows and 15 character rows. Both validation reports record
the same graph hash. The aggregate verifier checks direct accepted edges; the
full validator separately checks the complete provenance-rich graph.

QGIS was executed and its new portable project reopened with 22 valid layers,
nine relations and two layouts. Jodhaa Akbar (2008), Agra Fort, Filmapia logical
row 76 is 2,144.978 metres from the Taj Mahal reference point in EPSG:32644.
The independent spherical query gives 2.140626 km. These are representative
point distances, not camera positions. GeoSPARQL distance execution remains
future work. Review items and missing coordinates remain visible.

The full snapshot is in `../knowledge_graph/knowledge_graph_1970_2025.zip`.
