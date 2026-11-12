# Executed atlas-quality and song-location snapshot

Date: November 12, 2026. These files describe the current rebuilt graph; they do
not overwrite historical October or November 11 reports.

`song-location-references.geojson` was downloaded from the actual browser chat.
It has two source-supported song reference points, with explicit route/country
precision, stable song/film/place IDs, source evidence and status. Import it as
a WGS 84 point layer in QGIS. No new native QGIS process is claimed for this task.

`song_locations.csv` contains accepted records; `song_location_review.csv` keeps
48 notes awaiting review. `example-proposed-geotag.json` is an illustrative draft
for the validator, not a new accepted assertion or a browser-download artifact.

`graph_verification.json` records the direct RDF projection, sampled provenance,
all song-claim evidence, aggregate reconciliation and SongShape checks. It is
not full-graph provenance/SHACL validation. `validation.json` records executed
tests and browser checks. Screenshots are in `GIS/screenshots/2026-11-12/`.

See `Docs/ATLAS_IMPROVEMENTS_2026-11-12.md` for commands, sources and limitations.
