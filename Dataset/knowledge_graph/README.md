# Validated 1970–2025 knowledge graph

Extract `knowledge_graph_1970_2025.zip` into one directory. Open
`graph_explorer.html` locally for the offline interactive viewer, or load
`graph.ttl` in an RDF application. Keep the CSV files alongside the viewer.

The archive contains 20 original-byte outputs plus an internal manifest.
`manifest.json` records individual SHA-256 hashes, the archive hash and the
validation evidence. The package builder verifies every file after extraction.
Rebuild with the integration builder, explorer builder, full validator and
`python Queries/package_graph_delivery.py`. Source CSVs are preserved.
