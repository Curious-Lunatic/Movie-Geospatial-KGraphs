# Executed conversational demo snapshot — 11 November 2026

`results.json` records questions and answers from a fresh 1970–2025 build of
upstream `1094d0a` plus the chat contribution. It includes Fanaa's six categories,
nearby and region results, contextual refinements and missing-film responses.

`taj_mahal_heritage_analysis.geojson` is the **actual browser download** after
“Movies within 5 km of Taj Mahal” followed by “Only heritage”. It contains one
search polygon and one Jodhaa Akbar / Agra Fort result with source reference.
The exported geometry uses WGS 84 longitude/latitude. `GIS/chat_demo/` splits
the geometry types into QGIS layers and records import verification.

`graph_verification.json` is tied to the current RDF SHA-256. It parses direct
relationships and a provenance sample, reconciles counts and compares queries
with CSVs. Its explicit flags state that this verifier does **not** parse the
complete provenance-rich RDF or execute SHACL. Historical October validation
and graph archives describe their own earlier hashes and should not be used as
proof of full validation of this November build.

Reproduce the UI with the commands in `Docs/FINAL_DEMO.md`. Run the JavaScript
tests and integration tests listed in `Queries/webmap/README.md`. Results are
dataset snapshots, not complete cinema coverage or precise filming addresses.
