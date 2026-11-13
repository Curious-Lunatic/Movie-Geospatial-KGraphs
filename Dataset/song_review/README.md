# Adjudicated song-location scrape

All 437 input candidate rows were reviewed: 52 source-supported links imported,
294 unsupported rows rejected, 72 duplicates/wrong identities/context excluded,
and 19 rows retained for further review. The graph now has 54 links for 49 songs.

`decisions.csv` records every row's outcome and reason. `song_locations.csv` and
`song_location_query.json` show accepted graph/query results. `review.json`
records source hashes, validation scope and actual browser screenshots.

Verification means review against saved source statements and coordinate
responses; it is not independent filming/camera-position confirmation. Full
provenance SHACL was not rerun. See `Docs/SONG_CANDIDATE_REVIEW.md` for details.
The source scrape hit its page ceiling; discovery was not exhausted.
