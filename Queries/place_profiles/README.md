# Place identity profiles

`wikidata.json` is a bounded snapshot of public labels, aliases, direct instance-of
types, countries, administrative parents and coordinates for 431 geocoded place
IDs. Each record has its original Wikidata URL and revision. Wikidata structured
data is CC0; the source summary and hashes are retained for reproducibility.

`reviewed.json` resolves Chennai/Madras, the UNESCO Mahabalipuram identity and
Fort St. George. Only the Fort reference is newly created, using its separate
Wikidata identity/geometry. It has no inferred movie connection. District/UNESCO
descriptions in this file are our paraphrases linked to the official sources.

Normal integration builds are offline. `apply.py` retains existing geometry,
classifies supported types using an exact allowlist, and marks other types
unknown. It adds provenance, precision and aliases; it does not infer filming.

An explicit refresh requires network access:

```sh
python Queries/place_profiles/fetch_metadata.py
python Queries/build_integrated_graph.py
python Queries/build_graph_explorer.py
```

Review changes before committing the refreshed snapshot. A public identity or
coordinate does not establish that a film or song was made there.
