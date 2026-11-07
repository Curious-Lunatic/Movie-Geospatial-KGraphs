# Expanded heritage collection

The website has one heritage collection covering documented historic buildings, forts, palaces, stepwells and monuments alongside the existing World Heritage records. Historic landmark is a reviewed project classification, not a claim that every place has statutory protection or UNESCO inscription.

The November 5, 2026 build increases film-linked parent sites from 9 to 25, distinct films from 22 to 60, and distinct film–site pairs from 25 to 72. Of 47 added pairs, 39 recover existing filming evidence through heritage recognition and 8 come from newly reviewed evidence. Thirteen new source assertions include corroboration of existing pairs. A courtyard, gate or stepwell inside a fort rolls up to its parent for the site count. The duplicate Bagore ki Haveli identity is merged.

Sources include Wikipedia site articles, Rajasthan Tourism, Goa Tourism, Gujarat Tourism and Incredible India. Official palace descriptions corroborate heritage identity, while filming evidence has its own source. Existing Filmapia and Wikipedia film credits retain their original provenance. Sources are recorded in sources/*.json with retrieval time, original-response hash, text and available coordinates. Wikipedia text remains attributable to the linked page and its contributors.

sites.csv is the reviewed identity and coordinate registry. reviewed_claims.json records exact film IDs, source text checks and short paraphrases. apply.py runs automatically during the integrated build, checks evidence and joins films by identifier. It never adds a film merely from proximity. Filming claims outside the selected film corpus are omitted. The Dark Knight Rises at Chand Baori is excluded because the source describes set inspiration. The missing Chail Palace source was excluded from this batch.

Fourteen additional site coordinates now support map and district queries. Vijay Vilas Palace and named fort components with unresolved coordinates still appear in the graph and heritage table. Coordinates describe representative site points. Existing GIS project screenshots and the saved QGIS benchmark are historical outputs.

report.json and added_connections.csv give the final counts and additions, including recovered versus newly sourced evidence. baseline.json preserves the earlier 25 pairs. Scripts and review inputs are kept in Queries.

Rebuild using the project's integration and webmap dependencies installed.

    python Queries/build_integrated_graph.py --start-year 1970 --end-year 2025
    python Queries/heritage_expansion/report.py
    python Queries/prepare_spatial_boundaries.py --membership-only
    python Queries/prepare_vercel_site.py

To refetch absent source snapshots, use python Queries/heritage_expansion/fetch_sources.py. Review new text before editing the accepted evidence. prepare_review.py records the reviewed selections used to generate this batch.

## November 7 expansion

The second reviewed batch increases film-linked sites from 25 to 41, films from 60 to 81, and distinct film–parent-site connections from 72 to 101. Of the 29 additional pairs, 25 recover existing filming evidence and 4 are newly sourced. Eight added assertions include corroboration. Sources include Wikipedia site histories and Incredible India’s Bandra Fort page. Film identities are matched by Wikidata ID; similar titles (such as different films named Guru or Bombay) are not interchangeable. No film outside the current corpus is silently added.

Sixteen missing coordinates are filled. Vijay Vilas Palace uses the direction point published by Kachchh district tourism; this represents the site, not a shooting position. The Jaipur City Palace spelling variant is merged; Laxmi Niwas Palace is recorded as a component of Lalgarh Palace. Five named components still have no independently accepted point and are not placed at invented coordinates. Region memberships are regenerated against the existing boundary layer (320 joined places).

`expand_round2.py` fetches candidate source snapshots; pages returning 404 are excluded. `fetch_palace_point.py` retains the official direction URL and its point. `review_round2.py` records the reviewed selections and authored source-based summaries. `round2_baseline.json` preserves the state before this batch; `report_round2.py` checks coordinate evidence and emits `round2_report.json` plus `round2_connections.csv`. The original `report.json` continues to show cumulative growth from the original nine sites.

The location notebook uses `place_details.json` for the new historic sites and the existing UNESCO CSV for attributed descriptions. Its local structured context includes direct film/story evidence and documented components; nearby GeoNames settlements are explicitly separate. No AI service is used. Rebuild normally, then run `python Queries/heritage_expansion/report_round2.py` and `python Queries/heritage_expansion/validate_query.py` for batch and RDF reconciliation checks.
