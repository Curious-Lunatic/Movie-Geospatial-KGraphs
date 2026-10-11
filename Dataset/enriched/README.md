# Bollywood location enrichment

The original CSVs are preserved. This directory is a rebuildable enrichment layer
for the union of `bollywood_films_1970_2000.csv` and `bf_2K-25.csv`.
Auxiliary Wikidata files enrich matching films; they do not expand the corpus.

## Files

- `films_enriched.csv`: one row per resolved film. `filming_locations` and
  `narrative_locations` contain explicit Wikidata, Wikipedia category, and
  curated primary-source claims.
  `release_year` is the single earliest year used for ordering and decade
  summaries. `original_filming_coordinates` and
  `original_narrative_coordinates` preserve coordinate strings supplied by the
  original 1970–2000 CSV. `legacy_*` columns preserve the source location values;
  some contain comma-separated places and should not be split blindly.
- `location_assertions.csv`: individual claims with relation, method, status,
  source, supporting evidence, and revision/retrieval information where available.
- `places.csv`: place identities and coordinates where obtainable. A city or
  country point is a representative coordinate, never proof of an exact shooting
  spot. Missing coordinates remain missing.

## Interpretation

`source_supported` means the named source explicitly supplies that relationship;
it does not mean independently verified. `wikidata_existing_snapshot` imports
the supplied Wikidata CSVs, whose original retrieval dates and references were
not retained. Current `wikidata_statement` records retain claim references.
Wikipedia categories are editorial assertions, not necessarily primary evidence.
Newer category records come from explicit categories in article source; categories
generated exclusively by templates may not be captured.

`text_extracted_review_needed` assertions retain the exact supporting sentence
in `location_assertions.csv`; those review-only candidates are not repeated as
columns in the movie summary. The rules
distinguish plot sections from production sections, reject plans and negations,
and only match a place gazetteer built from explicit geographic sources. They
remain fallible; review before promoting these claims into the authoritative
graph. Original evidence snippets may also refer to another film.

Countries and broad regions count toward general location coverage. This is
not site-level coverage and is not sufficient evidence that a heritage site was
used. Neither production country nor an actor's birthplace is used as a film
location. Unknown places are not imputed. Missing evidence is not evidence of
absence. Present-day coordinates must not be assumed to represent historical
boundaries.

## Identity resolution

Wikidata IDs and Wikipedia page properties take priority. When online identity
is unavailable, only a unique normalized title-and-year match is used. Such
fallback matches still merit review; ambiguous matches remain separate. Films
with multiple release years retain all years and use the earliest available year
for decade summaries. Therefore these are corpus counts, not a claim to cover
every Bollywood release. A source film without an English Wikipedia article
remains in the corpus.

## Reproduce and continue

`../primary_location_evidence.json` is an editable source input containing
checked studio announcements, film-commission/production-partner releases,
and interviews with directors and line producers. Each claim records a film
identity, relation, place names, a paraphrased evidence note, source URL, and
speaker; the batch records its review date. The normal rebuild imports these
as `curated_*` methods with `source_supported` status. Add only claims actually
supported by an inspected source, and distinguish completed filming from
scouting, accommodation, publicity venues, and story settings. Credits alone
identify crew; they do not establish a filming location. DVD/streaming
commentaries require an accessible recording/transcript and timecode; none
were accessed for this batch. New places without a resolved geographic entity
retain blank coordinates. Notes such as Zakopane outskirts and a City Hall
library deliberately preserve the source's spatial scope.

From the project root, Python 3.9+ with the standard library is sufficient:

```sh
python Queries/enrich_locations.py --fetch
python Queries/enrich_locations.py --fetch --wikipedia-only
python Queries/enrich_locations.py --fetch --older-only
python Queries/enrich_locations.py --resolve-places
python Queries/enrich_locations.py --fetch-sparql --resolve-places
python Queries/enrich_locations.py
python -m unittest discover -s Queries -p 'test_location_text.py'
```

The first command refreshes missing Wikidata and Wikipedia cache entries and
prints coverage diagnostics to the console. It writes only the three CSV outputs. The
second skips Wikidata downloads. The third resolves older films using exact
Wikipedia page identities, trying title variants only for unresolved films.
The fourth resolves missing place coordinates. The fifth fetches a compact,
current Wikidata geographic-statement query, joins only corpus films, and resolves
places. The next command rebuilds outputs offline.
Successful downloads are cached in `Dataset/enrichment_cache` and reused.
Errors are reported; failed requests are not cached as empty data. Re-running
retries missing entries. Cache snapshots are intentionally not auto-refreshed;
archive selected cache entries before requesting newer versions.

`Queries/validate_enrichment.py` checks identifiers, claim provenance, coordinates,
and consistency between the movie and location CSVs. It prints results without
creating another output file.

Respect Wikimedia source attribution and applicable licences when redistributing
text or data. Retain the assertion provenance alongside graph exports.
