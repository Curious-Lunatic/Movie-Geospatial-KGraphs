#!/usr/bin/env python3
"""Apply inspected site-level evidence using exact film IDs and UNESCO site IDs."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
from enrich_from_location_lists import read_csv, write_csv, page_key, revision

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Queries/heritage_enrichment'
OUT = ROOT / 'Dataset/enriched'
METHODS = {'heritage_site_article', 'heritage_tourism_publication'}


def main(apply=False):
    films = read_csv(OUT / 'films_enriched.csv')
    by_id = {f['film_id']: f for f in films}
    assertions = read_csv(OUT / 'location_assertions.csv')
    places = read_csv(OUT / 'places.csv')
    heritage = {p['place_id']: p for p in read_csv(ROOT / 'Dataset/integrated/places.csv')
                if p['place_id'].startswith(('heritage:', 'heritage-component:'))}
    candidates = []
    for evidence in json.loads((WORK / 'reviewed_evidence.json').read_text()):
        film = by_id[evidence['film_id']]
        if page_key(film['wikipedia_url']) != evidence['film_page']:
            raise ValueError('Film identity mismatch: ' + evidence['film_id'])
        site = heritage[evidence['heritage_id']]
        snapshot = WORK / 'snapshots' / evidence['snapshot']
        meta = json.loads(snapshot.with_suffix(snapshot.suffix + '.json').read_text())
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == meta['sha256']
        rev = ''
        if snapshot.suffix == '.html':
            soup = BeautifulSoup(snapshot.read_bytes(), 'html.parser')
            rev = revision(soup) if 'wikipedia.org' in meta['url'] else ''
            text = soup.get_text(' ', strip=True)
            for token in evidence['verify_tokens']:
                if token not in text:
                    raise ValueError('Evidence token missing: ' + token)
        elif snapshot.suffix == '.json':
            extract = json.loads(snapshot.read_text())
            raw_pdf = snapshot.parent / extract['original_pdf']
            assert hashlib.sha256(raw_pdf.read_bytes()).hexdigest() == extract['original_pdf_sha256']
            page = next(p for p in extract['pages'] if p['pdf_page'] == evidence['pdf_page'])
            if evidence['source_film_label'] not in page['films'] or page['site'] != evidence['source_site_label']:
                raise ValueError('Reviewed PDF extract does not support claim')
        else:
            raise ValueError('Unsupported evidence snapshot: ' + str(snapshot))
        candidates.append(dict(film_id=film['film_id'], relation='filming',
            place_name=site['place_name'], place_id=site['place_id'],
            method=evidence['method'], source_url=meta['url'],
            evidence=evidence['locator'] + '; Paraphrase: ' + evidence['summary'],
            status='source_supported', revision_id=rev, retrieved_at=meta['retrieved_at']))
        if not any(p['place_id'] == site['place_id'] for p in places):
            places.append(dict(place_id=site['place_id'], place_name=site['place_name'],
                latitude=site['latitude'], longitude=site['longitude'], coordinate_precision='',
                globe='earth', coordinate_scope=site['coordinate_scope'],
                source_url=site['coordinate_source']))
    keys = [(a['film_id'], a['place_id'], a['source_url']) for a in candidates]
    assert len(keys) == len(set(keys)), 'Duplicate evidence'
    fields = list(assertions[0])
    write_csv(WORK / 'assertions.csv', candidates, fields)
    pids = {a['place_id'] for a in candidates}
    write_csv(WORK / 'places.csv', [p for p in places if p['place_id'] in pids], list(places[0]))
    if apply:
        combined = [a for a in assertions if a['method'] not in METHODS] + candidates
        supported = defaultdict(set)
        for a in combined:
            if a['relation'] == 'filming' and a['status'] == 'source_supported':
                supported[a['film_id']].add(a['place_name'])
        affected = {a['film_id'] for a in candidates}
        for film in films:
            film['filming_locations'] = '|'.join(sorted(supported[film['film_id']]))
            if film['film_id'] in affected:
                film['sources'] = '|'.join(sorted(set(film['sources'].split('|')) |
                    {'Queries/heritage_enrichment/assertions.csv'}))
        write_csv(OUT / 'location_assertions.csv', combined, fields)
        write_csv(OUT / 'films_enriched.csv', films, list(films[0]))
        write_csv(OUT / 'places.csv', places, list(places[0]))
    print(json.dumps(dict(accepted_source_assertions=len(candidates),
                         films=len({a['film_id'] for a in candidates}),
                         heritage_entities=len(pids)), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    main(parser.parse_args().apply)
