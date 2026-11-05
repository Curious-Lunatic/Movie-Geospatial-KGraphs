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
