# Requested upgrade coverage

Work stopped at the user's request before publication and a complete mobile/review
browser walkthrough. The implementation covers the product workflows below. This is a capability
audit, not a claim that every song/place has verified data or that pending web
discovery has finished. Film scope remains the team's Bollywood/Hindi-cinema
canonical list; filming locations can be anywhere in the world.

| Improvement | Implementation and evidence | Remaining data limit |
|---|---|---|
| 1. Better place names | Parent-qualified generic labels; original labels and correction CSV retained. Existing Chennai landmark registry distinguishes Fort St. George, the city and Mahabalipuram. | No historic name is guessed from a city label. |
| 2. Duplicate identities | Exact coordinate/source/country/type guard; conflicting IDs preserved; duplicate review CSV. | Similar names alone are insufficient for a merge. |
| 3. Song aliases/remakes | Film-scoped song IDs, sourced title aliases, possible version pairs exposed for review; alias regression test. | Unreviewed language/remix variants remain separate. |
| 4. Durable scraping | SQLite jobs, page batches, search pagination, leases, stop budgets, negative caches, explicit retry and offline reuse in `scrape_song_locations_v2.py`. | Pending searches remain pending; source access/recall is not guaranteed. |
| 5. Review dashboard | `review.html`: canonical choices, corrections, approve/reject/conflict, export/rebuild, optimistic versions and audit history. | Acceptance still requires an evidence review. |
| 6. Source confidence | Every edge retains assertions, method grade, source row/URL, available revision/retrieval and review date. | Multiple source records are not automatically independent confirmation. |
| 7. Scene evidence | Pending proposal form; scene seconds, video URL, coordinate uncertainty and separately sourced shooting coordinates exported as claim qualifiers. | No new exact camera positions or timestamps are invented. |
| 8. Geographic precision | Named-site/route/locality/region/country/unknown flags, hollow broad markers, precision filter and evidence cards. | A site reference is usually representative geometry. |
| 9. Broader discovery coverage | All canonical film/song pages and ranked recorded locations seed automatic bidirectional searches; configurable source editions and cross-language article links. | Bollywood film scope is preserved; native-script recall remains incomplete. |
| 10. Progressive loading | Indexed SQLite locally, compressed search assets and 256 film-prefix shards publicly; advanced chat/map assets load when used. | Power queries may load larger connection indexes. |
| 11. Map experience | Screen-grid clusters, stable-ID suggestions, corrected cards, radius circle, year/genre/site filters and GeoJSON export. | Basemap tiles need a network connection. |
| 12. Grounded questions | Film/song/place questions, nearby and regional genre/year filters, follow-ups, explicit interpretations and missing-data explanations. | Deterministic supported patterns; no unrestricted factual generation. |
| 13. Nearest and journeys | Heritage-first nearest filtering; exact 2–8 stop order with fixed start; existing road-route/corridor tool retained. | Straight-line itineraries are explicitly distinct from road travel. |
| 14. Regional/hotspot GIS | Actual QGIS counts, independently reconciled distinct IDs, projected quartic reference-density raster, PNG and portable project. | Exploratory reference density, not production activity/significance. |
| 15. Time and space | Release-year chart, keyboard controls, play/pause and linked map; stops when page hidden. | Release years are not shoot dates. |
| 16. Graph exploration | Typed filters, balanced categories, evidence inspection, complete relationship list and bounded shortest paths. | Diagram limits 50 visible neighbours; public non-film neighbourhoods disclose film-group limits. |
| 17. Coverage dashboard | Accepted links, missing geometry, unresolved identities, source records and saved discovery progress. | Jobs, candidate rows and unique accepted songs are different counts. |
| 18. Automated checks | Python and JavaScript regressions, orphan detection, identity/source/security/resume checks, RDF/CSV query reconciliation and CI. | Test and SHACL scope is explicitly reported. |
| 19. Mobile/accessibility | Responsive layout, labelled forms, skip links, keyboard graph/list/chart controls, live status and readable failure messages. | Mobile layout and the complete review editor have not had a browser walkthrough; automated checks cover their supporting logic. |
| 20. Reproducible release | `build_release.py`, file hashes, compressed RDF/claims, portable download, read-only hosting layout, guide and executed evaluation. | Public hosting was not enabled; review writes stay local. |

See [the runnable guide](ATLAS_GUIDE.md), `GIS/analysis/validation.json`,
`GIS/analysis/product_evaluation.json` and `GIS/screenshots/full-upgrade/`.
Earlier projects, screenshots and the user's separately modified
`GIS/Good_Will_Mapping.qgz` are preserved.
