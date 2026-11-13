# More song-location evidence without interrupting the existing scraper

## Global discovery in both directions (current command)

```powershell
rtk proxy python Queries/scrape_song_locations_all.py --resume
```

This command requires **no place input**. It automatically covers the full current
catalogue: 10,709 known songs, 5,690 film source pages, 1,569 recorded filming
locations ranked by distinct film count, and direct song article lookups. It
interleaves 2,035 location/alias searches with 10,709 reverse song/film searches.
The initial article queue has 25,717 unique pages, including song-title variants;
many variants may not have an article. Missing responses are cached too.

All recorded filming places are included, with the 374 places connected to
multiple films ranked first. The ordering is based on supplied filming data,
not a claim to a worldwide tourism popularity ranking. New articles and explicitly
named songs can extend the queue up to the default 50,000 unique source-page
ceiling (`--limit` can change it). Search continuation is supported with
`--search-pages`, default 50 results per automatic query. Broader searches do
not guarantee a location record for every song.

This run writes **`outputs/song-location-all/`**. Both earlier scripts/output
directories are protected and their finalized caches are only read. No existing
process is stopped or reconfigured. Add `--dry-run` for the complete plan or
`--offline` for completed-cache processing only.

It captures specific named sites from song evidence and can retrieve primary
coordinates for their linked Wikipedia place articles. These are **place reference
points**, not verified camera positions. Decimal hemisphere coordinates explicitly
present in the song evidence are retained separately with that source URL.
Coordinates are never guessed from a city name or copied from a different source
as an exact filming claim. These outputs keep all records pending review:

- `candidates.csv`: broad source-linked song/location matches.
- `named_site_candidates.csv`: named-site candidates for closer inspection.
- `source_reported_coordinates.csv`: coordinates explicitly present in song evidence.
- `automatic_locations.csv`: the automatically generated location search scope.
- `summary.json`: progress, distinct candidate-song count and errors.

The TMDB and authorized IMDb support described below also applies to this command.
Fresh TMDB metadata is optional; neither production countries nor plot summaries
are treated as song-filming evidence. No accepted RDF is changed by scraping.

The older commands below remain available for existing runs.

The original `Queries/scrape_song_locations.py` and its running process remain
unchanged. Its output is `outputs/song-location-scrape/`. The separate fast script
only **reads** finalized `.json` caches there; it never writes to that directory.
Its own candidates, progress, metadata and caches use `outputs/song-location-fast/`.

## Faster run

From the repository root:

```powershell
rtk proxy python Queries/scrape_song_locations_fast.py --resume --limit 11000 --place Shimla
```

You can leave the current run to finish and use this command afterwards. Completed
pages are reused; new Wikipedia revision reads request up to 20 pages per batch.
The location-name index is built once and CSVs are checkpointed once per batch.
This reduces request/checkpoint overhead; actual speed depends on the provider,
cache coverage and article sizes. No fixed speed multiplier is promised.

`--place Shimla` adds focused full-text discovery for Shimla and recorded aliases,
including Simla. Repeated options, e.g. `--place Shimla --place Manali`, add places.
Known linked song pages can extend coverage beyond film articles (up to 500 extra
song pages by default). The overall page limit is a ceiling, not a result target.

To inspect the plan without writes/requests, add `--dry-run`. To process completed
caches without any network activity, add `--offline`; place-focused online
discovery is skipped in that mode. `--offline` preserves current-run activity.
The script refuses to use the legacy output tree and prevents concurrent fast
processes from writing the same new output folder.

## Sources

- **Wikipedia:** batch revision content plus article/alias searches. Source page,
  revision, retrieval time, response hash and evidence are retained. Old cached
  rendered paragraphs and new revision prose use the same canonical film/song
  identities. Unknown discovery-page identities go to a separate review log.
- **TMDB:** the default reads existing `Queries/tmdb_details.jsonl`, writes
  `tmdb_context.csv`, and makes no TMDB requests. To fetch fresh movie details,
  set `TMDB_API_READ_ACCESS_TOKEN` or `TMDB_API_KEY` in your terminal environment
  and add `--fetch-tmdb`. No key is written into source, output or error messages.
  TMDB production countries, plot summaries and keywords remain **film metadata**;
  they are not converted into song-filming assertions.
- **IMDb:** direct website scraping is not enabled. IMDb's published robots
  policy disallows automated scraping without permission, and the public dataset
  schema has no filming-location field. The script supports an authorized CSV
  export with `--imdb-evidence C:\path\authorized.csv`. Required columns are
  `imdb_id,song,place,source_url,evidence`. It requires an exact unique canonical
  film ID/song match and an IMDb source URL for that title. Film locations without
  an explicit song are not inherited. Imports remain review candidates.

Primary documentation:
[Wikipedia revision API](https://www.mediawiki.org/wiki/API:Revisions),
[search API](https://www.mediawiki.org/wiki/API:Search),
[API etiquette](https://www.mediawiki.org/wiki/API:Etiquette),
[TMDB movie details](https://developer.themoviedb.org/reference/movie-details),
[IMDb access policy](https://www.imdb.com/robots.txt),
[IMDb public dataset schema](https://developer.imdb.com/non-commercial-datasets/).

## Outputs and verification

- `candidates.csv`: deduplicated source-linked song/location candidates.
- `focused_candidates.csv`: candidates mentioning the requested places/aliases.
- `tmdb_context.csv`: separate metadata for film identity/context.
- `summary.json`: cache/fetch counts, source status and errors.
- `discovery_identity_review.jsonl`: discovered pages without resolved identity.

All candidates have `needs_review` status. A co-mention in a filming sentence may
still be wrong, so it must be checked before graph import. Shimla city coordinates
remain locality references; an unclassified location does not gain site precision.
Sources with denied/rate-limited access stop rather than being bypassed. Successful
work stays cached for a later `--resume` run. Neither script changes accepted RDF.

```powershell
rtk proxy python -m unittest discover -s Queries -p test_song_scraper_fast.py -v
```
