# Validated 1970–2025 knowledge graph

The current November 12 atlas is in **`atlas_2026-11-12.zip`**, with a separate
hash manifest. It includes the new place-quality metadata, song-location evidence,
review list, chat/geotag UI and regional assets. Its direct RDF projection,
sampled provenance, both song claims, query reconciliation and all-song SongShape
checks passed. **Full-graph provenance SHACL was not rerun.** Rebuild it with
`python Queries/package_atlas_delivery.py` after graph verification.

The following instructions describe the preserved historical October archive.

Extract `knowledge_graph_1970_2025.zip` into one directory. Open
`graph_explorer.html` locally for the offline interactive viewer, or load
`graph.ttl` in an RDF application. Keep the CSV files alongside the viewer.

The archive contains 20 original-byte outputs plus an internal manifest.
`manifest.json` records individual SHA-256 hashes, the archive hash and the
validation evidence. The package builder verifies every file after extraction.
Rebuild with the integration builder, explorer builder, full validator and
`python Queries/package_graph_delivery.py`. Source CSVs are preserved.
