# Explicit song-location evidence

`reviewed.json` adds two source-supported assertions, separately from film-level
locations. It resolves canonical films by Wikidata ID and checks their year.
The place must already exist; the evidence snapshot must contain the reviewed
tokens. Source hashes are recorded in the integration manifest.

| Song | Film | Place | Precision | Evidence |
|---|---|---|---|---|
| Chaiyya Chaiyya | Dil Se.. (1998) | Nilgiri Mountain Railway | Route/component reference | Existing attributed railway article snapshot |
| Gerua | Dilwale (2015) | Iceland | Country reference | Official Film in Iceland production listing |

The railway evidence reuses the repository's October 12 Wikipedia snapshot and
its original attribution/retrieval metadata. Wikipedia contributors' text is
subject to its linked attribution/share-alike terms; our assertion description
is a paraphrase. `iceland_source.json` retains a short excerpt, our own summary,
URL, retrieval time and fetched-page hash, rather than redistributing the page.

Neither assertion provides a verified camera coordinate or scene timestamp.
Do not upgrade either to an exact site, or copy film locations to other songs.
No unsupported performer/composer credit was supplied for the added song.

Outputs under `Dataset/integrated/`:

- `song_locations.csv`: accepted, explicitly evidenced song-location records.
- `song_location_review.csv`: 48 supplied notes awaiting review.
- `claims.csv`/`graph.ttl`: typed `song_filming`/`gwm:songFilmedAt` assertions with
  source file/row/URL, evidence and assertion-specific coordinate precision.
- `song_location_query.json`: executed SPARQL results after graph verification.

The UI's proposal form exports JSON with status `proposed`; the Python validator
checks its schema without accepting it or changing the graph. Source review and
an explicit curated record are required before rebuilding accepted assertions.

See `Docs/ATLAS_IMPROVEMENTS_2026-11-12.md` for the complete demonstration.
