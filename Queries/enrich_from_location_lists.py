#!/usr/bin/env python3
"""Join location-first Wikipedia lists/categories to the existing film corpus.

python Queries/enrich_from_location_lists.py --fetch
python Queries/enrich_from_location_lists.py --apply
Requires beautifulsoup4; successful HTML snapshots are reused for offline runs.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Queries/location_lists'
OUT = ROOT / 'Dataset/enriched'
METHODS = {'wikipedia_location_list', 'wikipedia_location_category'}


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    temporary.replace(path)


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def page_key(url):
    path = unquote(urlsplit(url).path)
    if '/wiki/' not in path:
        return ''
    return path.split('/wiki/', 1)[1].replace('_', ' ').strip()


def download(url, fetch):
    key = hashlib.sha256(url.encode()).hexdigest()
    path = WORK / 'snapshots' / (key + '.html')
    meta = path.with_suffix('.json')
    if not path.exists():
        if not fetch:
            raise RuntimeError('Missing snapshot; run with --fetch: ' + url)
        req = Request(url, headers={'User-Agent': 'MovieGeospatialResearch/1.0 (academic research)'})
        with urlopen(req, timeout=45) as response:
            body = response.read()
            final_url = response.url
        path.write_bytes(body)
        save(meta, {'url': url, 'final_url': final_url,
                    'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'sha256': hashlib.sha256(body).hexdigest()})
        time.sleep(0.5)
    return BeautifulSoup(path.read_bytes(), 'html.parser'), json.loads(meta.read_text())


def extract(soup, kind, section=''):
    """Only direct category members or bullet rows inside an explicit film section."""
    if kind == 'category':
        return [(a, a.get_text(' ', strip=True)) for a in soup.select('#mw-pages .mw-category-group li > a')]
    heading = soup.find(id=section)
    if heading is None:
        raise ValueError('Film-list section not found: ' + section)
    rows = []
    for node in heading.find_all_next():
        if node.name == 'h2':
            break
        if node.name != 'li' or node.find_parent('li'):
            continue
        a = node.find('a', href=lambda h: h and '/wiki/' in h and ':' not in page_key(h))
        if a:
            rows.append((a, node.get_text(' ', strip=True)))
    return rows


def revision(soup):
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True) == 'Permanent link':
            match = re.search(r'oldid=(\d+)', a['href'])
            if match:
                return match[1]
    match = re.search(r'"wgRevisionId"\s*:\s*(\d+)', str(soup))
    return match[1] if match else ''


def pair(row):
    return (row['film_id'], row.get('place_id') or row['place_name'].casefold())


def run(fetch=False, apply=False):
    WORK.mkdir(exist_ok=True)
    (WORK / 'snapshots').mkdir(exist_ok=True)
    films = read_csv(OUT / 'films_enriched.csv')
    assertions = read_csv(OUT / 'location_assertions.csv')
    places = read_csv(OUT / 'places.csv')
    by_page = defaultdict(list)
    for film in films:
        if film['release_year'].isdigit() and 1970 <= int(film['release_year']) <= 2025:
            by_page[page_key(film['wikipedia_url'])].append(film)
    by_name = defaultdict(list)
    for place in places:
        by_name[place['place_name'].casefold()].append(place)
    manifest = json.loads((WORK / 'sources.json').read_text())
    candidates, skipped, sources, failures = [], [], [], []
    for spec in manifest:
        place_matches = by_name[spec['place'].casefold()]
        # Prefer the already resolved QID when legacy unresolved aliases coexist.
        resolved = [p for p in place_matches if p['place_id'].startswith('Q')]
        if len(resolved) == 1:
            place = resolved[0]
        elif len(place_matches) == 1:
            place = place_matches[0]
        else:
            place = {'place_id': 'L_' + hashlib.sha256(spec['place'].casefold().encode()).hexdigest()[:16],
                     'place_name': spec['place'], 'coordinate_scope': 'unresolved',
                     'source_url': 'https://en.wikipedia.org/wiki/' + quote(spec.get('place_page', spec['place']).replace(' ', '_'))}
        if spec.get('place_page') and place.get('coordinate_scope') == 'unresolved':
            place['source_url'] = 'https://en.wikipedia.org/wiki/' + quote(spec['place_page'].replace(' ', '_'))
        url = 'https://en.wikipedia.org/wiki/' + quote(spec['page'].replace(' ', '_'), safe=':')
        visited = set()
        source_count = 0
        while url and url not in visited:
            visited.add(url)
            try:
                soup, meta = download(url, fetch)
                entries = extract(soup, spec['kind'], spec.get('section', ''))
                if not entries:
                    raise ValueError('No film entries found')
                rev = revision(soup)
                for link, evidence in entries:
                    if spec.get('entry_place_pages'):
                        row = link.find_parent('li')
                        targets = {page_key(a['href']) for a in row.select('a[href]')[1:]
                                   if 'redlink=1' not in a['href']}
                        if not targets.intersection(spec['entry_place_pages']):
                            continue
                    title = page_key(link['href'])
                    matches = by_page.get(title, [])
                    if len(matches) != 1:
                        skipped.append({'source_url': url, 'film_page': title,
                                        'reason': 'ambiguous_identity' if matches else 'no_exact_corpus_page_match'})
                        continue
                    film = matches[0]
                    candidates.append(dict(film_id=film['film_id'], relation='filming',
                        place_name=place['place_name'], place_id=place['place_id'],
                        method='wikipedia_location_' + spec['kind'], source_url=url,
                        evidence=f"{spec['page']}; entry: {evidence}", status='source_supported',
                        revision_id=rev, retrieved_at=meta['retrieved_at']))
                    source_count += 1
                sources.append(dict(meta, page=spec['page'], place=spec['place'],
                                    entries=len(entries), revision_id=rev))
                next_link = next((a for a in soup.select('#mw-pages a[href]')
                                  if a.get_text(strip=True) == 'next page'), None)
                url = urljoin(url, next_link['href']) if next_link else ''
            except Exception as exc:
                failures.append({'url': url, 'error': str(exc)})
                print('FAILED', url, str(exc), flush=True)
                break
        print(spec['place'], spec['kind'], source_count, 'corpus matches', flush=True)
        if source_count and not any(p['place_id'] == place['place_id'] for p in places):
            places.append(place)

    # Resolve only newly introduced places, from their own geographic article.
    for place in places:
        if place.get('coordinate_scope') != 'unresolved' or not any(
                c['place_id'] == place['place_id'] for c in candidates):
            continue
        try:
            soup, meta = download(place['source_url'], fetch)
            geo = soup.select_one('.geo')
            if geo:
                values = [v.strip() for v in geo.get_text().split(';')]
                if len(values) == 2:
                    lat, lon = map(float, values)
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        place.update(latitude=lat, longitude=lon, globe='earth',
                                     coordinate_scope='Place representative point; not the exact shooting spot')
        except Exception as exc:
            failures.append({'url': place['source_url'], 'error': 'Coordinate resolution: ' + str(exc)})

    # Preserve independent provenance; deduplicate repeated rows from the same page.
    unique = {}
    for row in candidates:
        unique[(row['film_id'], row['place_id'], row['source_url'])] = row
    candidates = list(unique.values())
    base = [a for a in assertions if a['method'] not in METHODS]
    base_pairs = {pair(a) for a in base if a['relation'] == 'filming' and a['status'] == 'source_supported'}
    baseline_path = WORK / 'baseline.json'
    if not baseline_path.exists():
        save(baseline_path, {'captured_at': datetime.now(timezone.utc).isoformat(),
            'filming_pairs': sorted(base_pairs),
            'place_ids': sorted({p['place_id'] for p in read_csv(OUT / 'places.csv')}),
            'input_sha256': {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
                             for name in ['films_enriched.csv', 'location_assertions.csv', 'places.csv']}})
    baseline = json.loads(baseline_path.read_text())
    original_pairs = {tuple(p) for p in baseline['filming_pairs']}
    batch_pairs = {pair(a) for a in candidates} - original_pairs
    new_place_ids = {a['place_id'] for a in candidates} - set(baseline['place_ids'])
    titles = {f['film_id']: f['title'] for f in films}
    additions = []
    already = set()
    for a in candidates:
        if pair(a) in batch_pairs and pair(a) not in already:
            additions.append(dict(a, title=titles[a['film_id']]))
            already.add(pair(a))
    fields = list(assertions[0])
    write_csv(WORK / 'assertions.csv', candidates, fields)
    write_csv(WORK / 'places.csv', [p for p in places if p['place_id'] in
              {a['place_id'] for a in candidates}], list(read_csv(OUT / 'places.csv')[0]))
    write_csv(WORK / 'added_film_locations.csv', additions, ['title'] + fields)
    write_csv(WORK / 'unmatched_films.csv', skipped, ['source_url', 'film_page', 'reason'])
    report = {'scope': 'Existing corpus, release years 1970–2025; exact Wikipedia film-page identity only',
              'source_pages_downloaded': len({s['url'] for s in sources}),
              'sources': list({s['url']: s for s in sources}.values()), 'failures': failures,
              'source_assertions': len(candidates),
              'new_film_location_pairs': len(batch_pairs),
              'films_with_new_locations': len({f for f, p in batch_pairs}),
              'films_gaining_first_supported_filming_location': len({f for f, p in batch_pairs} - {f for f, p in original_pairs}),
              'distinct_places_in_new_pairs': len({p for f, p in batch_pairs}),
              'new_place_entities': len(new_place_ids),
              'new_place_names': sorted({a['place_name'] for a in candidates if a['place_id'] in new_place_ids}),
              'before_supported_filming_pairs': len(original_pairs),
              'after_supported_filming_pairs': len(base_pairs | {pair(a) for a in candidates}),
              'additions_by_place': dict(Counter(a['place_name'] for a in additions)),
              'unmatched_entries': len(skipped),
              'note': 'Wikipedia editorial assertions, not independent verification. List scope supplies only the named city/state/country; no exact shooting coordinates inferred.'}
    if apply:
        # A failed refresh must never delete previously imported source assertions.
        retained = [a for a in assertions if a['method'] in METHODS]
        all_claims = {(a['film_id'], a['place_id'], a['source_url'], a['method']): a for a in retained}
        all_claims.update({(a['film_id'], a['place_id'], a['source_url'], a['method']): a for a in candidates})
        combined = base + list(all_claims.values())
        supported = defaultdict(set)
        for a in combined:
            if a['relation'] == 'filming' and a['status'] == 'source_supported':
                supported[a['film_id']].add(a['place_name'])
        for f in films:
            f['filming_locations'] = '|'.join(sorted(supported[f['film_id']]))
            if any(a['film_id'] == f['film_id'] for a in candidates):
                f['sources'] = '|'.join(sorted(set(f['sources'].split('|')) | {'Queries/location_lists/assertions.csv'}))
        write_csv(OUT / 'location_assertions.csv', combined, fields)
        write_csv(OUT / 'films_enriched.csv', films, list(films[0]))
        write_csv(OUT / 'places.csv', places, list(read_csv(OUT / 'places.csv')[0]))
    save(WORK / 'report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in {'sources', 'failures'}}, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    run(args.fetch, args.apply)
