#!/usr/bin/env python3
"""Evidence-preserving cinema location enrichment; stdlib only, restartable caches.

python Queries/enrich_locations.py --fetch
python Queries/enrich_locations.py             # rebuild from cached/source data
"""
import argparse
import collections
import csv
import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'Dataset'
CACHE = DATA / 'enrichment_cache'
OUT = DATA / 'enriched'
UA = 'BollywoodGeoGraphResearch/1.0 (academic film-location enrichment)'

def save_json(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False))
    temporary.replace(path)

def read(name):
    with (DATA / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write(name, rows, fields):
    OUT.mkdir(exist_ok=True)
    with (OUT / name).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

def norm(s):
    s = re.sub(r'\s*\([^)]*film[^)]*\)', '', s, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower())

def title_url(title):
    return 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))

def page_title(url):
    return urllib.parse.unquote(url.split('/wiki/')[-1]).replace('_', ' ')

def request(api, params):
    params = dict(params, format='json', maxlag=15)
    url = api + '?' + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
            with urllib.request.urlopen(req, timeout=90) as response:
                data = response.read()
                if response.headers.get('Content-Encoding') == 'gzip':
                    import gzip
                    data = gzip.decompress(data)
            result = json.loads(data)
            if 'error' in result:
                raise RuntimeError(str(result['error']))
            return result
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry = exc.headers.get('Retry-After','60')
                print('Rate limit; Retry-After='+retry+'; pausing before retry',flush=True)
                if attempt == 2:
                    raise RuntimeError('RATE_LIMITED: '+api+'; Retry-After='+retry) from exc
                time.sleep(max(5, int(retry) if retry.isdigit() else 60))
                continue
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def entity_batch(ids):
    result = request('https://www.wikidata.org/w/api.php', {
        'action': 'wbgetentities', 'ids': '|'.join(ids),
        'props': 'sitelinks|claims|labels', 'sitefilter': 'enwiki', 'languages': 'en'})
    for qid, entity in result.get('entities', {}).items():
        # Keep only the information needed for the research; retain claim references.
        entity['claims'] = {k:v for k,v in entity.get('claims', {}).items()
                            if k in ('P915','P840','P625','P31','P17','P131')}
        entity['retrieved_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_json(CACHE / 'entities' / (qid + '.json'),entity)

def wiki_batch(titles):
    params = {'action':'query', 'titles':'|'.join(titles), 'redirects':1,
              'prop':'pageprops|revisions|info',
              'rvprop':'content|ids', 'rvslots':'main', 'inprop':'url'}
    pages = {}
    redirects = {}
    while True:
        result = request('https://en.wikipedia.org/w/api.php', params)
        q = result.get('query', {})
        for item in q.get('normalized', []) + q.get('redirects', []):
            redirects[item['from']] = item['to']
        for key, page in q.get('pages', {}).items():
            if key not in pages:
                pages[key] = page
            else:
                pages[key].setdefault('categories', []).extend(page.get('categories', []))
                if page.get('extract'):
                    pages[key]['extract'] = page['extract']
        if 'continue' not in result:
            break
        params.update(result['continue'])
        time.sleep(8)
    by_title = {p['title']:p for p in pages.values()}
    for title in titles:
        dest = title
        visited = set()
        while dest in redirects and dest not in visited:
            visited.add(dest)
            dest = redirects[dest]
        if dest not in by_title:
            raise RuntimeError('Page absent from API response: ' + title)
        page = dict(by_title[dest], requested_title=title,
                    retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        revisions = page.get('revisions', [])
        if revisions:
            page['lastrevid'] = revisions[0]['revid']
            page['wikitext'] = revisions[0].get('slots',{}).get('main',{}).get('*','')
            page['extract'] = plain_wikitext(page['wikitext'])
            # Explicit page categories avoid the expensive categories continuation API.
            page['categories'] = [{'title':'Category:'+c.strip()} for c in re.findall(
                r'\[\[Category:([^]|]+)(?:\|[^]]*)?\]\]',page['wikitext'])]
        path = CACHE / 'pages' / (hashlib.sha256(title.encode()).hexdigest() + '.json')
        save_json(path,page)

def plain_wikitext(text):
    text=re.sub(r'<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>', '', text, flags=re.S|re.I)
    text=re.sub(r'<!--.*?-->', '', text, flags=re.S)
    # Remove nested templates, including infoboxes, rather than interpreting fields as prose.
    while re.search(r'\{\{[^{}]*\}\}',text):
        text=re.sub(r'\{\{[^{}]*\}\}', '', text)
    text=re.sub(r'\[\[(?:Category|File|Image):[^\]]*\]\]', '', text,flags=re.I)
    text=re.sub(r'\[\[([^]|]+)\|([^]]+)\]\]',r'\2',text)
    text=re.sub(r'\[\[([^]]+)\]\]',r'\1',text)
    text=re.sub(r'\[https?://\S+\s+([^]]*)\]',r'\1',text)
    text=re.sub(r'<[^>]+>', '', text)
    return html.unescape(text.replace("''",''))

def place_batch(names):
    requested={name:name.removeprefix('the ') for name in names}
    result=request('https://en.wikipedia.org/w/api.php',{
        'action':'query','titles':'|'.join(dict.fromkeys(requested.values())),'redirects':1,
        'prop':'pageprops|coordinates|info','coprimary':'primary','colimit':'max','inprop':'url'})
    q=result.get('query',{})
    redirects={r['from']:r['to'] for r in q.get('normalized',[])+q.get('redirects',[])}
    pages={p['title']:p for p in q.get('pages',{}).values()}
    for name in names:
        dest=requested[name]
        seen=set()
        while dest in redirects and dest not in seen:
            seen.add(dest)
            dest=redirects[dest]
        page=dict(pages.get(dest,{}),requested_title=name,
                  retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        path=CACHE/'place_pages'/(hashlib.sha256(name.encode()).hexdigest()+'.json')
        save_json(path,page)

def fetch_location_query():
    """Fetch only geographic statements for Hindi-language works, then join locally.

    This avoids downloading every unrelated claim for each film. Non-corpus
    works returned by the query are discarded during the local join.
    """
    query='''SELECT DISTINCT ?film ?relation ?place ?placeLabel ?coordinate WHERE {
      ?film wdt:P364 wd:Q1568 .
      VALUES ?relation { wdt:P915 wdt:P840 }
      ?film ?relation ?place .
      OPTIONAL { ?place wdt:P625 ?coordinate . }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }'''
    result=request('https://query.wikidata.org/sparql',{'query':query})
    result['retrieved_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_json(CACHE/'wikidata_location_statements.json',result)
    print('Fresh Wikidata geographic statements:',len(result.get('results',{}).get('bindings',[])),flush=True)

def fetch_batches(values, folder, batch_size, worker):
    pending = []
    for value in sorted(set(values)):
        key = value if folder == 'entities' else hashlib.sha256(value.encode()).hexdigest()
        if not (CACHE / folder / (key + '.json')).exists():
            pending.append(value)
    batches = [pending[i:i+batch_size] for i in range(0, len(pending), batch_size)]
    print(f'{folder}: {len(pending)} pending / {len(set(values))} total', flush=True)
    errors = []
    for i, batch in enumerate(batches, 1):
        try:
            worker(batch)
        except Exception as exc:
            errors.append({'items':batch, 'error':str(exc)})
            print(f'ERROR {folder}: {str(exc)[:180]}', flush=True)
            if 'RATE_LIMITED' in str(exc):
                break
        if i % 5 == 0 or i == len(batches):
            print(f'{folder}: {i}/{len(batches)} batches complete', flush=True)
        time.sleep(6)
    return errors

def load_cache(folder, key):
    data = {obj[key]:obj for path in (CACHE / folder).glob('*.json')
            if (obj := json.loads(path.read_text())) and key in obj}
    if folder=='pages':
        for obj in list(data.values()):
            data.setdefault(obj['title'],obj)
    return data

def claim_values(entity, prop):
    for claim in entity.get('claims', {}).get(prop, []):
        if claim.get('rank') != 'deprecated':
            value = claim.get('mainsnak', {}).get('datavalue', {}).get('value')
            if value is not None:
                yield value, claim

def main(fetch=False, wikipedia_only=False, older_only=False, resolve_places=False, fetch_sparql=False):
    for folder in ('entities','pages','place_pages'):
        (CACHE / folder).mkdir(parents=True, exist_ok=True)
    old = read('bollywood_films_1970_2000.csv')
    newer = read('bf_2K-25.csv')
    aux = read('wikidata_movies.csv') + read('master_bollywood_data_with_imdb.csv')
    errors = []
    if fetch_sparql:
        try:
            fetch_location_query()
        except Exception as exc:
            errors.append({'source':'Wikidata geographic query','error':str(exc)})
    qids = {r['wikidata_id'] for r in old + aux if r['wikidata_id']}
    if fetch and not wikipedia_only and not older_only:
        errors += fetch_batches(qids, 'entities', 50, entity_batch)
    entities = load_cache('entities', 'id')
    titles = {page_title(r['wikipedia_url']) for r in newer if r['wikipedia_url']}
    titles |= {e['sitelinks']['enwiki']['title'] for e in entities.values() if 'enwiki' in e.get('sitelinks', {})}
    if older_only:
        titles=set()
        for row in old:
            title=row['title']
            if re.fullmatch(r'Q\d+',title):
                continue
            enwiki=entities.get(row['wikidata_id'],{}).get('sitelinks',{}).get('enwiki',{}).get('title')
            if enwiki:
                titles.add(enwiki)
            else:
                titles.add(title)
    if fetch:
        errors += fetch_batches(titles, 'pages', 50, wiki_batch)
    pages = load_cache('pages', 'requested_title')
    qid_pages = {p.get('pageprops',{}).get('wikibase_item'):p for p in pages.values() if p.get('pageprops',{}).get('wikibase_item')}
    if fetch and older_only:
        fallback=set()
        for row in old:
            if row['wikidata_id'] not in qid_pages and not re.fullmatch(r'Q\d+',row['title']):
                fallback.update([row['title']+' (film)',row['title']+' ('+row['release_date'][:4]+' film)'])
        errors += fetch_batches(fallback,'pages',50,wiki_batch)
        pages=load_cache('pages','requested_title')
        qid_pages={p.get('pageprops',{}).get('wikibase_item'):p for p in pages.values() if p.get('pageprops',{}).get('wikibase_item')}
    # Resolve newer source rows using Wikipedia's authoritative item mapping.
    films = {}
    source_map = []
    ambiguous = []
    def add_film(fid, row, source, match):
        year = row.get('release_year', row.get('release_date','')[:4])
        film = films.setdefault(fid, {'film_id':fid, 'title':row['title'], 'years':set(),
                                     'wikidata_id':fid if fid.startswith('Q') else '',
                                     'wikipedia_url':'', 'imdb_id':'', 'sources':set()})
        if year:
            film['years'].add(year)
        film['sources'].add(source)
        if row.get('wikipedia_url'):
            film['wikipedia_url'] = row['wikipedia_url']
        if row.get('imdb_id'):
            film['imdb_id'] = row['imdb_id']
        source_map.append((fid, row, source, match))
    for row in old:
        add_film(row['wikidata_id'], row, 'bollywood_films_1970_2000.csv', 'wikidata_id')
    # Only use unambiguous title/year matches when no page identity is available.
    index = collections.defaultdict(set)
    for row in old + aux:
        index[(norm(row['title']),row['release_date'][:4])].add(row['wikidata_id'])
    for row in newer:
        page = pages.get(page_title(row['wikipedia_url']), {})
        qid = page.get('pageprops', {}).get('wikibase_item')
        matches = index.get((norm(row['title']),row['release_year']),set())
        if qid:
            fid, method = qid, 'wikipedia_pageprops'
        elif len(matches) == 1:
            fid, method = next(iter(matches)), 'unique_normalized_title_year'
        else:
            fid, method = 'WP_' + hashlib.sha256(row['wikipedia_url'].encode()).hexdigest()[:16], 'wikipedia_url'
            if len(matches) > 1:
                ambiguous.append({'title':row['title'],'year':row['release_year'],'candidates':'|'.join(sorted(matches))})
        add_film(fid,row,'bf_2K-25.csv',method)
    for row in aux:
        if row['wikidata_id'] in films:
            add_film(row['wikidata_id'],row,'wikidata_movies.csv' if 'imdb_id' not in row else 'master_bollywood_data_with_imdb.csv','wikidata_id')
    for fid, film in films.items():
        enwiki = entities.get(fid,{}).get('sitelinks',{}).get('enwiki',{}).get('title')
        if enwiki:
            film['wikipedia_url'] = title_url(enwiki)
        elif fid in qid_pages:
            film['wikipedia_url'] = qid_pages[fid].get('fullurl',title_url(qid_pages[fid]['title']))

    identity_conflicts=[]
    def film_page(fid,film):
        page=pages.get(page_title(film['wikipedia_url']),{}) if film['wikipedia_url'] else {}
        page_qid=page.get('pageprops',{}).get('wikibase_item')
        if fid.startswith('Q') and page_qid and fid!=page_qid:
            conflict={'film_id':fid,'page_qid':page_qid,'wikipedia_url':film['wikipedia_url']}
            if conflict not in identity_conflicts:
                identity_conflicts.append(conflict)
            return {}
        return page

    assertions = []
    seen = set()
    def add(fid,relation,place,method,source,evidence='',place_id='',status='source_supported',revision='',retrieved=''):
        place = place.strip(' ;|\n')
        if not place or re.fullmatch(r'Q\d+',place):
            return
        if place in {'Indian independence movement'}:
            status='non_geographic_review_needed'
        key = (fid,relation,place.casefold(),method,source,evidence)
        if key in seen:
            return
        seen.add(key)
        assertions.append({'film_id':fid,'relation':relation,'place_name':place,'place_id':place_id,
                           'method':method,'source_url':source,'evidence':evidence,'status':status,
                           'revision_id':revision,'retrieved_at':retrieved})

    for fid,row,source,match in source_map:
        for relation in ('filming','narrative'):
            value = row.get(relation+'_locations',row.get(relation+'_location',''))
            # Comma-separated legacy values can mix places and administrative context;
            # preserve them as verbatim candidates rather than inventing individual places.
            for place in re.split(r'\s*\|\s*',value):
                is_structured = source!='bf_2K-25.csv'
                add(fid,relation,place,'wikidata_existing_snapshot' if is_structured else 'legacy_import',row.get('wikipedia_url','') or 'https://www.wikidata.org/wiki/'+fid,
                    row.get('location_evidence','') or f'Imported from {source}; identity match: {match}',status='source_supported' if is_structured else 'legacy_unreviewed')

    needed_places = set()
    for fid in films:
        for prop in ('P915','P840'):
            needed_places.update(v['id'] for v,c in claim_values(entities.get(fid,{}),prop) if isinstance(v,dict) and 'id' in v)
    if fetch and not wikipedia_only and not older_only:
        errors += fetch_batches(needed_places, 'entities', 50, entity_batch)
        entities = load_cache('entities','id')
    place_rows = []
    for qid in sorted(needed_places):
        entity = entities.get(qid,{})
        label = entity.get('labels',{}).get('en',{}).get('value',qid)
        coords = [v for v,c in claim_values(entity,'P625') if isinstance(v,dict)]
        coord = coords[0] if coords else {}
        place_rows.append({'place_id':qid,'place_name':label,'latitude':coord.get('latitude',''),
                           'longitude':coord.get('longitude',''),'coordinate_precision':coord.get('precision',''),
                           'globe':coord.get('globe',''),'source_url':'https://www.wikidata.org/wiki/'+qid})
    labels = {p['place_id']:p['place_name'] for p in place_rows}
    for fid in films:
        for prop,relation in [('P915','filming'),('P840','narrative')]:
            for value,claim in claim_values(entities.get(fid,{}),prop):
                if isinstance(value,dict) and 'id' in value:
                    qid = value['id']
                    add(fid,relation,labels.get(qid,qid),'wikidata_statement','https://www.wikidata.org/wiki/'+fid,
                        json.dumps({'property':prop,'claim_id':claim.get('id'),'references':claim.get('references',[])},ensure_ascii=False),qid)

    query_path=CACHE/'wikidata_location_statements.json'
    if query_path.exists():
        query_data=json.loads(query_path.read_text())
        for binding in query_data.get('results',{}).get('bindings',[]):
            fid=binding['film']['value'].rsplit('/',1)[-1]
            if fid not in films:
                continue
            qid=binding['place']['value'].rsplit('/',1)[-1]
            prop=binding['relation']['value'].rsplit('/',1)[-1]
            relation={'P915':'filming','P840':'narrative'}[prop]
            name=binding['placeLabel']['value']
            add(fid,relation,name,'wikidata_geographic_query','https://www.wikidata.org/wiki/'+fid,
                f'{fid} {prop} {qid}; truthy Wikidata statement',qid,retrieved=query_data.get('retrieved_at',''))
            coord=re.fullmatch(r'Point\(([-\d.]+) ([-\d.]+)\)',binding.get('coordinate',{}).get('value',''))
            place_rows.append({'place_id':qid,'place_name':name,'latitude':coord[2] if coord else '',
                               'longitude':coord[1] if coord else '', 'coordinate_precision':'',
                               'globe':'',
                               'coordinate_scope':'Place representative point; not the exact shooting spot' if coord else 'unresolved',
                               'source_url':'https://www.wikidata.org/wiki/'+qid})
            labels[qid]=name

    for fid, film in films.items():
        if not film['wikipedia_url']:
            continue
        page = film_page(fid,film)
        for category in page.get('categories',[]):
            cat = category['title']
            for prefix,relation in [('Category:Films shot in ','filming'),('Category:Films set in ','narrative')]:
                if cat.startswith(prefix):
                    place = cat[len(prefix):]
                    # Exclude temporal, generic and fictional-setting categories.
                    if re.match(r'(?:the )?(?:\d|future|past|fictional|prehistory|precolonial|ancient times)',place,re.I):
                        continue
                    if place in ('outer space','space','the Middle Ages') or not re.match(r'(?:the )?[A-ZÀ-Ý]',place):
                        continue
                    add(fid,relation,place,'wikipedia_category',page.get('fullurl',film['wikipedia_url']),cat,
                        revision=page.get('lastrevid',''),retrieved=page.get('retrieved_at',''))

    from location_text import extract
    gazetteer = set(labels.values())
    for row in old + aux:
        for relation in ('filming','narrative'):
            gazetteer.update(p.strip() for p in row.get(relation+'_location','').split('|') if p.strip())
    gazetteer.update(a['place_name'] for a in assertions if a['method']=='wikipedia_category')
    gazetteer -= {'Indian independence movement'}
    # Preserve historical territory wording found in source prose rather than
    # matching the modern country as a substring of its name.
    gazetteer.update({'British India','East Pakistan','West Pakistan','British Burma'})
    for fid,film in films.items():
        page = film_page(fid,film)
        for result in extract(page.get('extract',''),gazetteer):
            add(fid,result['relation'],result['place_name'],'wikipedia_text_rule',
                page.get('fullurl',film['wikipedia_url']),result['evidence'],
                status='text_extracted_review_needed',revision=page.get('lastrevid',''),retrieved=page.get('retrieved_at',''))
    for fid,row,source,match in source_map:
        if source != 'bf_2K-25.csv':
            continue
        for result in extract(row.get('location_evidence',''),gazetteer,evidence_only=True):
            add(fid,result['relation'],result['place_name'],'saved_evidence_rule',row['wikipedia_url'],
                result['evidence'],status='text_extracted_review_needed')

    # Curated primary-source notes are persistent inputs, so rebuilds retain
    # the verified press-note and interview claims without re-extracting prose.
    primary_path = DATA / 'primary_location_evidence.json'
    if primary_path.exists():
        primary = json.loads(primary_path.read_text(encoding='utf-8'))
        for source in primary['sources']:
            if not source['source_url'].startswith('https://'):
                raise ValueError('Primary evidence requires an HTTPS source URL')
            for claim in source['claims']:
                fid = claim['film_id']
                if fid not in films or norm(films[fid]['title']) != norm(claim['title']):
                    raise ValueError('Primary evidence film identity mismatch: ' + fid)
                if claim['relation'] not in ('filming', 'narrative') or not claim['evidence_summary']:
                    raise ValueError('Invalid primary location claim: ' + fid)
                for place in claim['places']:
                    add(fid, claim['relation'], place, 'curated_' + source['source_type'],
                        source['source_url'],
                        'Paraphrase; ' + source['speaker'] + ': ' + claim['evidence_summary'],
                        retrieved=primary['reviewed_at'])
                films[fid]['sources'].add('primary_location_evidence.json')

    # Retain the separately reviewed location-first and heritage evidence on rebuild.
    for batch_directory, methods in [
            ('location_lists', {'wikipedia_location_list', 'wikipedia_location_category'}),
            ('heritage_enrichment', {'heritage_site_article', 'heritage_tourism_publication'})]:
        location_lists_path = ROOT / 'Queries' / batch_directory / 'assertions.csv'
        if not location_lists_path.exists():
            continue
        with location_lists_path.open(encoding='utf-8', newline='') as handle:
            for claim in csv.DictReader(handle):
                fid = claim['film_id']
                if fid not in films:
                    raise ValueError('Location-list film missing from corpus: ' + fid)
                if claim['relation'] != 'filming' or claim['method'] not in methods:
                    raise ValueError('Invalid location-list claim: ' + fid)
                add(fid, 'filming', claim['place_name'], claim['method'],
                    claim['source_url'], claim['evidence'], place_id=claim['place_id'],
                    status=claim['status'], revision=claim['revision_id'],
                    retrieved=claim['retrieved_at'])
                films[fid]['sources'].add('Queries/' + batch_directory + '/assertions.csv')
        list_places_path = location_lists_path.with_name('places.csv')
        if list_places_path.exists():
            known_ids = {p['place_id'] for p in place_rows}
            with list_places_path.open(encoding='utf-8', newline='') as handle:
                for place in csv.DictReader(handle):
                    if place['place_id'] not in known_ids:
                        place_rows.append(place)
                        known_ids.add(place['place_id'])

    place_names={a['place_name'] for a in assertions if a['status']!='legacy_unreviewed'}
    if resolve_places:
        errors+=fetch_batches(place_names,'place_pages',50,place_batch)
    place_pages=load_cache('place_pages','requested_title')
    known_places={p['place_id']:p for p in place_rows}
    for a in assertions:
        if a['status']=='legacy_unreviewed':
            continue
        name=a['place_name']
        page=place_pages.get(name,{})
        props=page.get('pageprops',{})
        coordinate=page.get('coordinates',[{}])[0]
        # A place label is resolved only with a primary geographic coordinate.
        # Disambiguation pages and unlocated fictional/historical concepts stay unresolved.
        resolved=bool(coordinate) and 'disambiguation' not in props
        pid=a['place_id'] or (props.get('wikibase_item') if resolved else '') or 'L_'+hashlib.sha256(name.casefold().encode()).hexdigest()[:16]
        a['place_id']=pid
        resolved_record={'place_id':pid,'place_name':name,
            'latitude':coordinate.get('lat','') if resolved else '',
            'longitude':coordinate.get('lon','') if resolved else '',
            'coordinate_precision':'','globe':coordinate.get('globe','') if resolved else '',
            'source_url':page.get('fullurl','') if resolved else '',
            'coordinate_scope':'Place representative point; not the exact shooting spot' if resolved else 'unresolved'}
        if pid not in known_places or (known_places[pid].get('latitude','')=='' and resolved):
            known_places[pid]=resolved_record
    place_rows=list(known_places.values())

    # Export distinct broad legacy and source-supported coverage, never claiming human verification.
    by_film = collections.defaultdict(list)
    for a in assertions:
        by_film[a['film_id']].append(a)
    original_coords_by_film = collections.defaultdict(lambda: {'filming': set(), 'narrative': set()})
    for source_fid, source_row, _, _ in source_map:
        for relation in ('filming', 'narrative'):
            value = source_row.get(relation + '_coordinates', '').strip()
            if value:
                original_coords_by_film[source_fid][relation].add(value)
    rows = []
    for fid,film in sorted(films.items(),key=lambda kv:(min(kv[1]['years'] or {'9999'}),kv[1]['title'])):
        # Preserve the original per-film coordinate strings (currently supplied
        # by the 1970–2000 file). These are distinct from place representative
        # coordinates in places.csv.
        row = dict(film,release_year=min(film['years'] or {''}),sources='|'.join(sorted(film['sources'])))
        row['original_filming_coordinates'] = '|'.join(sorted(original_coords_by_film[fid]['filming']))
        row['original_narrative_coordinates'] = '|'.join(sorted(original_coords_by_film[fid]['narrative']))
        for relation in ('filming','narrative'):
            claims = [a for a in by_film[fid] if a['relation']==relation]
            row[relation+'_locations'] = '|'.join(sorted({a['place_name'] for a in claims if a['status']=='source_supported'}))
            row['legacy_'+relation+'_locations'] = '|'.join(sorted({a['place_name'] for a in claims if a['status']=='legacy_unreviewed'}))
            # Internal coverage-only fields; omitted from films_enriched.csv.
            row['candidate_'+relation+'_locations'] = '|'.join(sorted({a['place_name'] for a in claims if a['status']=='text_extracted_review_needed'}))
        rows.append(row)
    fields = ['film_id','title','release_year','wikidata_id','imdb_id','wikipedia_url','filming_locations','narrative_locations','original_filming_coordinates','original_narrative_coordinates','legacy_filming_locations','legacy_narrative_locations','sources']
    write('films_enriched.csv',rows,fields)
    write('location_assertions.csv',assertions,['film_id','relation','place_name','place_id','method','source_url','evidence','status','revision_id','retrieved_at'])
    write('places.csv',place_rows,['place_id','place_name','latitude','longitude','coordinate_precision','globe','coordinate_scope','source_url'])
    def coverage(subset, prefix=''):
        f=sum(bool(r[prefix+'filming_locations']) for r in subset)
        n=sum(bool(r[prefix+'narrative_locations']) for r in subset)
        either=sum(bool(r[prefix+'filming_locations'] or r[prefix+'narrative_locations']) for r in subset)
        return dict(films=len(subset),filming=f,narrative=n,either=either,both=f+n-either,either_percent=round(either/len(subset)*100,2) if subset else 0)
    baseline={fid:{'filming_locations':'','narrative_locations':''} for fid in films}
    merged_baseline={fid:{'filming_locations':'','narrative_locations':''} for fid in films}
    for fid,row,source,match in source_map:
        for relation in ('filming','narrative'):
            value=row.get(relation+'_locations',row.get(relation+'_location',''))
            if value:
                merged_baseline[fid][relation+'_locations']='present'
                if source in ('bollywood_films_1970_2000.csv','bf_2K-25.csv'):
                    baseline[fid][relation+'_locations']='present'
    expanded=[dict(r,filming_locations=r['filming_locations'] or r['candidate_filming_locations'],
                   narrative_locations=r['narrative_locations'] or r['candidate_narrative_locations']) for r in rows]
    report={'scope':'Union of original 1970–2000 and bf_2K-25 files; auxiliary files enrich matched films only',
            'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_supported':coverage(rows),'legacy_imported':coverage(rows,'legacy_'),
            'text_candidates':coverage(rows,'candidate_'),
            'original_two_files':coverage(list(baseline.values())),
            'all_existing_files_merged':coverage(list(merged_baseline.values())),
            'supported_plus_text_candidates':coverage(expanded),
            'films_with_downloaded_wikipedia':sum(bool(film_page(r['film_id'],r)) and 'missing' not in film_page(r['film_id'],r) for r in rows),
            'places_with_coordinates':sum(p.get('latitude','')!='' and p.get('longitude','')!='' for p in place_rows),
            'distinct_place_records':len(place_rows),
            'by_decade':{str(y):coverage([r for r in rows if r['release_year'].isdigit() and y<=int(r['release_year'])<y+10]) for y in range(1970,2030,10)},
            'including_candidates_by_decade':{str(y):coverage([r for r in expanded if r['release_year'].isdigit() and y<=int(r['release_year'])<y+10]) for y in range(1970,2030,10)},
            'assertions_by_method':dict(collections.Counter(a['method'] for a in assertions)),
            'ambiguous_identity_matches':ambiguous,'fetch_errors':errors,
            'identity_conflicts_excluded':identity_conflicts,
            'note':'Source-supported does not mean manually verified. Legacy values are isolated and excluded from primary coverage. Country-level categories count; precision must be considered in analysis.'}
    # Print run diagnostics without creating extra derived files.
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--wikipedia-only',action='store_true')
    parser.add_argument('--older-only',action='store_true')
    parser.add_argument('--resolve-places',action='store_true')
    parser.add_argument('--fetch-sparql',action='store_true')
    args=parser.parse_args()
    main(args.fetch,args.wikipedia_only,args.older_only,args.resolve_places,args.fetch_sparql)
