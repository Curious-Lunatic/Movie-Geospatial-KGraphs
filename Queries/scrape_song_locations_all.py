"""Global bidirectional song/location discovery; existing scraping runs stay read-only.

Scans known films and song articles, searches every recorded filming location
and every known song/film pair, and retains named-site/coordinate evidence.
"""
import argparse,csv,itertools,json,math,os,re,sys
from collections import defaultdict,deque
from pathlib import Path
from scrape_song_locations_fast import (ROOT,LEGACY,Client,AccessStopped,Matcher,decode_batch,digest,
    load_inputs,norm,read,stamp,write_json,write_csv,protect_output,tmdb_context,imdb_import,FIELDS as BASE_FIELDS)
from build_integrated_graph import key,norm as graph_norm

FAST=ROOT/'outputs/song-location-fast'
FIELDS=BASE_FIELDS+['song_identity','site_article','coordinate_source','coordinate_role','reported_latitude','reported_longitude','reported_coordinate_source']
SONG_TITLE=re.compile(r'\b(?:song|track|number)\s+(?:(?:titled|called|named)\s+)?["“‘\']([^"”’\'\n]{2,120})["”’\']',re.I)
COORDS=re.compile(r'(?<![\d.])([+-]?\d{1,2}(?:\.\d+)?)\s*°?\s*([NS])\s*[,;/ ]+\s*([+-]?\d{1,3}(?:\.\d+)?)\s*°?\s*([EW])\b',re.I)


def protect_all_output(path):
    protect_output(path)
    protect_output(path,FAST)


def extended_inputs():
    films,by_film,by_song,places,jobs,priority=load_inputs()
    with (ROOT/'Dataset/integrated/film_attributes.csv').open(encoding='utf-8-sig',newline='') as stream:
        from scrape_song_locations import wiki_title
        for row in csv.DictReader(stream):
            title=wiki_title(row['value']) if row['value'].startswith('https://en.wikipedia.org/wiki/') else None
            if title and row['film_id'] in films:jobs[title].add(row['film_id'])
    return films,by_film,by_song,places,jobs,priority


def location_ranking(places,claims):
    """Popularity means distinct recorded filming-film count, not invented tourism rank."""
    films=defaultdict(set);lookup={p['place_id']:p for p in places}
    for claim in claims:
        if claim['relation']=='filming' and claim['object_id'] in lookup:films[claim['object_id']].add(claim['subject_id'])
    result=[]
    for pid,movies in films.items():
        p=lookup[pid]
        if len(norm(p['place_name']))<3:continue
        aliases=[a for a in json.loads(p.get('aliases') or '[]') if a.isascii() and 3<=len(a)<=100]
        result.append(dict(place_id=pid,name=p['place_name'],film_count=len(movies),aliases=aliases[:2]))
    return sorted(result,key=lambda p:(-p['film_count'],p['name']))


def song_pages(by_song):
    pages=[];seen=set()
    for title,songs in by_song.items():
        display=songs[0]['title'].strip()
        if len(title)<3 or len(display)>180:continue
        # Ambiguous title pages remain identity-review material until a film link resolves them.
        for page in [display+' (song)',display]:
            if page not in seen:seen.add(page);pages.append(page)
    return pages


def query_tasks(ranked,by_song,films):
    places=[];songs=[];seen=set()
    for place in ranked:
        for label in [place['name'],*place['aliases']]:
            q='"'+label.replace('"','')+'" (song OR songs OR "music video") (filmed OR shot OR picturised OR picturized)'
            if q not in seen:seen.add(q);places.append(dict(direction='location_to_songs',query=q,label=label))
    for group in by_song.values():
        for song in group:
            f=films[song['film_id']];display=song['title'].replace('"','');film=re.sub(r'\s*\([^)]*film\)\s*',' ',f['title'],flags=re.I).strip().replace('"','')
            q='"'+display+'" "'+film+'" (filmed OR shot OR filming OR picturised OR picturized)'
            if q not in seen:seen.add(q);songs.append(dict(direction='song_to_locations',query=q,label=song['title'],song_id=song['song_id'],film_id=song['film_id']))
    # Both directions start immediately; no location or song has to be supplied by the user.
    return [task for pair in itertools.zip_longest(places,songs) for task in pair if task]


def new_song_mentions(blocks,fid,existing):
    known={norm(s['title']) for s in existing};new=[]
    for block in blocks:
        for match in SONG_TITLE.finditer(block['text']):
            title=match[1].strip()
            if norm(title) in known:continue
            known.add(norm(title));new.append(dict(song_id=key('song',fid,graph_norm(title)),title=title,film_id=fid,new_song=True))
    return new


def explicit_coordinates(text):
    match=COORDS.search(text)
    if not match:return None
    lat,lon=abs(float(match[1])),abs(float(match[3]))
    if lat>90 or lon>180:return None
    return (-lat if match[2].upper()=='S' else lat,-lon if match[4].upper()=='W' else lon)


def article_url(title):
    import urllib.parse
    return 'https://en.wikipedia.org/wiki/'+urllib.parse.quote(title.replace(' ','_'),safe='')


def row_marker(row):
    location=('article:'+norm(row['site_article'])) if row.get('site_article') else row['place_id']
    return row['song_id'],location,row['source_url'],row['evidence']


def decorate(row,places):
    p=places.get(row['place_id'],{})
    row.update(song_identity=row.get('song_identity','existing_song'),site_article=row.get('site_article',''),coordinate_source=p.get('coordinate_source',''),coordinate_role='place_representative_point' if row.get('latitude')!='' else 'coordinates_missing',reported_latitude='',reported_longitude='',reported_coordinate_source='')
    point=explicit_coordinates(row['evidence'])
    if point:
        row.update(reported_latitude=point[0],reported_longitude=point[1],reported_coordinate_source=row['source_url'])
    return row


def unknown_sites(rows,blocks):
    """Retain named linked sites missing from the local gazetteer for coordinate lookup."""
    extra=[];seen=set()
    for row in rows:
        sentence=norm(row['evidence'])
        for block in blocks:
            if norm(row['evidence']) not in norm(block['text']):continue
            for link in block.get('links',[]):
                label=link.get('label','').strip();target=link.get('title','').strip()
                if not target or ':' in target or len(label)<3 or norm(label)==norm(row['song']):continue
                if not re.search(r'\b(?:at|in|on|near)\s+(?:the\s+)?'+re.escape(norm(label))+r'(?!\w)',sentence):continue
                if row['place'] and norm(label)==norm(row['place']):continue
                marker=(row['song_id'],target,row['evidence'])
                if marker in seen:continue
                seen.add(marker);extra.append(dict(row,place_id='',place=label,latitude='',longitude='',location_precision='unknown_reference',identity_match='linked_place_needs_review',site_article=target,coordinate_source='',coordinate_role='coordinates_missing'))
    return extra


def resolve_page_films(title,snapshot,jobs,by_song,article_index=None,qid_index=None):
    qids=(qid_index or {}).get(snapshot.get('wikidata_id',''),set())
    if len(qids)==1:return qids
    bound=jobs.get(title,set())
    if len(bound)==1:return bound
    if len(bound)>1:return set()
    base=norm(re.sub(r'\s*\((?:song|soundtrack)\)\s*$','',title,flags=re.I))
    tracks=by_song.get(base,[])
    # A song title alone does not establish which film's song it is.
    linked={norm(t) for t in snapshot.get('linked_pages',[])}
    linked.update(norm(a.get('title','')) for b in snapshot.get('blocks',[]) for a in b.get('links',[]))
    if article_index is None:
        article_index=defaultdict(set)
        for page,fids in jobs.items():article_index[norm(page)].update(fids)
    linked_fids=set().union(*(article_index.get(page,set()) for page in linked)) if linked else set()
    matches={s['film_id'] for s in tracks if s['film_id'] in linked_fids}
    return matches if len(matches)==1 else set()


def attach_coordinates(rows,body,place_lookup):
    query=body.get('query',{});pages={p['title']:p for p in query.get('pages',[])}
    aliases={a['from']:a['to'] for a in query.get('normalized',[])+query.get('redirects',[])}
    for row in rows:
        title=row.get('site_article')
        if not title or row.get('latitude')!='':continue
        resolved=title;seen=set()
        while resolved in aliases and resolved not in seen:seen.add(resolved);resolved=aliases[resolved]
        page=pages.get(resolved,{})
        points=[p for p in page.get('coordinates',[]) if p.get('globe','earth')=='earth']
        if not points:continue
        p=points[0];lat,lon=p.get('lat'),p.get('lon')
        if not isinstance(lat,(int,float)) or not isinstance(lon,(int,float)) or not math.isfinite(lat) or not math.isfinite(lon) or abs(lat)>90 or abs(lon)>180:continue
        qid=page.get('pageprops',{}).get('wikibase_item','');known=place_lookup.get(qid,{})
        row.update(latitude=lat,longitude=lon,place_id=qid,location_precision=known.get('location_precision','unknown_reference'),coordinate_source=article_url(page.get('title',title)),coordinate_role='linked_place_representative_point')


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--limit',type=int,default=50000,help='Ceiling on unique source pages across all directions')
    parser.add_argument('--batch-size',type=int,default=20);parser.add_argument('--delay',type=float,default=1)
    parser.add_argument('--search-pages',type=int,default=50,help='Results per automatic query, including pagination')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/song-location-all')
    parser.add_argument('--dry-run',action='store_true');parser.add_argument('--offline',action='store_true')
    parser.add_argument('--fetch-tmdb',action='store_true');parser.add_argument('--imdb-evidence',type=Path)
    args=parser.parse_args()
    if args.limit<1 or not 1<=args.batch_size<=20 or not 1<=args.delay<=60 or not 1<=args.search_pages<=500:parser.error('Use a positive limit, batch size 1-20, delay 1-60 and search pages 1-500.')
    if args.offline and args.fetch_tmdb:parser.error('--offline cannot fetch TMDB data')
    try:protect_all_output(args.output)
    except ValueError as error:parser.error(str(error))
    films,by_film,by_song,places,jobs,priority=extended_inputs();place_lookup={p['place_id']:p for p in places}
    article_index=defaultdict(set);qid_index=defaultdict(set)
    for page,fids in jobs.items():article_index[norm(page)].update(fids)
    for fid,film in films.items():
        if film.get('wikidata_id'):qid_index[film['wikidata_id']].add(fid)
    with (ROOT/'Dataset/integrated/claims.csv').open(encoding='utf-8-sig',newline='') as stream:ranked=location_ranking(places,csv.DictReader(stream))
    tasks=deque(query_tasks(ranked,by_song,films));initial=sorted(jobs,key=lambda t:(not bool(jobs[t]&priority),t))
    seeds=list(dict.fromkeys(initial+song_pages(by_song)))[:args.limit]
    if args.dry_run:
        print(json.dumps(dict(mode='all_locations_and_all_songs',known_songs=sum(map(len,by_song.values())),film_source_pages=len(initial),recorded_filming_locations=len(ranked),multiple_film_locations=sum(p['film_count']>=2 for p in ranked),reverse_song_queries=sum(t['direction']=='song_to_locations' for t in tasks),location_queries=sum(t['direction']=='location_to_songs' for t in tasks),initial_unique_pages=len(seeds),source_page_ceiling=args.limit,batch_size=args.batch_size,site_coordinate_lookup=True,existing_runs_modified=False,output=str(args.output)),indent=2));return
    out=args.output;out.mkdir(parents=True,exist_ok=True);lock=out/'.running'
    try:handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(handle)
    except FileExistsError:parser.error('This output is already in use. Leave that process running or use a different output directory.')
    rows=read(out/'candidates.csv') if args.resume and (out/'candidates.csv').exists() else []
    seen={row_marker(r) for r in rows}
    queue=deque(seeds);queued=set(seeds);handled=set();matcher=Matcher(places);client=Client(args.delay)
    cache=out/'wiki-cache';cache.mkdir(exist_ok=True);stats=dict(cached_pages=0,fetched_pages=0,processed_pages=0,location_queries_completed=0,song_queries_completed=0,accepted_graph_changed=False,existing_runs_modified=False);errors=[]
    def enqueue(title):
        if title and ':' not in title and title not in queued and len(queued)<args.limit:queue.append(title);queued.add(title)
    def save():
        normalized=[{field:r.get(field,'') for field in FIELDS} for r in rows];write_csv(out/'candidates.csv',normalized,FIELDS)
        write_csv(out/'named_site_candidates.csv',[r for r in normalized if r['site_article'] or r['location_precision']=='site_reference'],FIELDS)
        write_csv(out/'source_reported_coordinates.csv',[r for r in normalized if r['reported_latitude']!=''],FIELDS)
        write_json(out/'summary.json',dict(stats,candidates=len(rows),unique_songs_with_candidates=len({r['song_id'] for r in rows}),new_song_candidates=len({r['song_id'] for r in rows if r.get('song_identity')=='new_song_needs_review'}),queued_pages=len(queued),pending_queries=len(tasks),network_requests=client.requests,errors=errors))
    def add(found):
        for r in found:
            marker=row_marker(r)
            if marker not in seen:seen.add(marker);rows.append(r)
    def consume(title,snapshot,path):
        if snapshot.get('unavailable'):return
        bound=resolve_page_films(title,snapshot,jobs,by_song,article_index,qid_index)
        if not bound:
            with (out/'identity_review.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(page=title,cache_file=str(path),source_url=snapshot['source_url'],status='film_identity_needs_review'))+'\n')
            return
        for fid in bound:
            added=new_song_mentions(snapshot['blocks'],fid,by_film[fid]);song_list=by_film[fid]+added
            found=matcher.extract(snapshot['blocks'],song_list);new_ids={s['song_id'] for s in song_list if s.get('new_song')}
            for row in found:
                row.update(film_id=fid,film=films[fid]['title'],year=films[fid]['release_year'],source='Wikipedia',source_url=snapshot['source_url'],revision_id=snapshot.get('revision_id',''),retrieved_at=snapshot['retrieved_at'],cache_file=str(path),song_identity='new_song_needs_review' if row['song_id'] in new_ids else 'existing_song')
                decorate(row,place_lookup)
            found+=unknown_sites(found,snapshot['blocks']);add(found)
            by_film[fid].extend(added)
            for song in added:
                by_song[norm(song['title'])].append(song)
                film=films[fid]['title'].replace('"','');display=song['title'].replace('"','')
                tasks.append(dict(direction='song_to_locations',query='"'+display+'" "'+film+'" (filmed OR shot OR filming OR picturised OR picturized)',label=display,song_id=song['song_id'],film_id=fid))
                for page in [song['title']+' (song)',song['title']]:enqueue(page)
        stats['processed_pages']+=1
        # Follow known song links without imposing a small per-place song limit.
        for target in snapshot.get('linked_pages',[]):
            if norm(re.sub(r'\s*\((?:song|soundtrack)\)\s*$','',target,flags=re.I)) in by_song:enqueue(target)
    try:
        write_csv(out/'automatic_locations.csv',ranked,['place_id','name','film_count','aliases'])
        stats['tmdb']=tmdb_context(films,out,client,args.fetch_tmdb,args.limit)
        add([decorate(r,place_lookup) for r in imdb_import(args.imdb_evidence,films,by_film,places)])
        stats['imdb']='Authorized export only; automated website scraping unavailable.'
        print(f'Global scan: {sum(map(len,by_song.values()))} known songs; {len(ranked)} filming locations; {len(seeds)} initial source pages; {len(tasks)} automatic discovery queries.',flush=True)
        while queue or (tasks and not args.offline and len(queued)<args.limit):
            batch=[queue.popleft() for _ in range(min(args.batch_size,len(queue)))];pending=[]
            for title in batch:
                if title in handled:continue
                handled.add(title);own=cache/(digest(title)+'.json');old=LEGACY/'cache'/(digest(title)+'.json');fast=FAST/'wiki-cache'/(digest(title)+'.json')
                path=own if args.resume and own.exists() else fast if fast.exists() else old if old.exists() else None
                if path:
                    try:snapshot=json.loads(path.read_text(encoding='utf-8'))
                    except (ValueError,OSError):pending.append(title);continue
                    consume(title,snapshot,path);stats['cached_pages']+=1
                else:pending.append(title)
            if pending and not args.offline:
                body,h=client.wiki(action='query',prop='revisions|pageprops',ppprop='wikibase_item',titles='|'.join(pending),rvprop='ids|timestamp|content',rvslots='main',redirects=1)
                decoded=decode_batch(body,pending,h);page_qids={p['title']:p.get('pageprops',{}).get('wikibase_item','') for p in body.get('query',{}).get('pages',[])}
                for title in pending:
                    if title not in decoded:
                        write_json(cache/(digest(title)+'.json'),dict(unavailable=True,title=title,source_url=article_url(title),blocks=[],retrieved_at=stamp(),response_sha256=h))
                        continue
                    snapshot=decoded[title];snapshot['wikidata_id']=page_qids.get(snapshot['title'],'')
                    path=cache/(digest(title)+'.json');write_json(path,snapshot);consume(title,snapshot,path);stats['fetched_pages']+=1
            if tasks and not args.offline and len(queued)<args.limit:
                task=tasks.popleft();offset=0;remaining=args.search_pages
                while remaining:
                    search_path=out/'search-cache'/(digest(task['query']+'|'+str(offset))+'.json')
                    if args.resume and search_path.exists():result=json.loads(search_path.read_text(encoding='utf-8'))
                    else:
                        result,_=client.wiki(action='query',list='search',srsearch=task['query'],srnamespace=0,srlimit=min(50,remaining),sroffset=offset,srprop='');write_json(search_path,result)
                    hits=result.get('query',{}).get('search',[])
                    for hit in hits:enqueue(hit['title'])
                    remaining-=len(hits);continuation=result.get('continue',{}).get('sroffset')
                    if not hits or continuation is None:break
                    offset=continuation
                stats['location_queries_completed' if task['direction']=='location_to_songs' else 'song_queries_completed']+=1
            # Only look up primary coordinates of specifically linked location pages.
            targets=list(dict.fromkeys(r['site_article'] for r in rows if r.get('site_article') and r.get('latitude')==''))
            for start in range(0,len(targets),args.batch_size):
                names=targets[start:start+args.batch_size];geo_path=out/'coordinate-cache'/(digest('|'.join(names))+'.json')
                if geo_path.exists():geo=json.loads(geo_path.read_text(encoding='utf-8'))
                elif not args.offline:
                    geo,_=client.wiki(action='query',prop='coordinates|pageprops',titles='|'.join(names),coprimary='primary',coprop='type|name',ppprop='wikibase_item',redirects=1);write_json(geo_path,geo)
                else:continue
                attach_coordinates(rows,geo,place_lookup)
            save();print(f'Pages: {len(handled)}/{len(queued)} | songs with candidates: {len({r["song_id"] for r in rows})} | candidates: {len(rows)} | discovery queries left: {len(tasks)}',flush=True)
    except KeyboardInterrupt:stats['interrupted']=True;print('Progress saved. Use --resume to continue.',flush=True)
    except (AccessStopped,ValueError,OSError,KeyError) as error:
        stats['stopped']=True;errors.append(dict(error=str(error) if isinstance(error,(AccessStopped,ValueError)) else type(error).__name__));print('Provider or data error; progress saved. See summary.json.',flush=True)
    finally:
        try:save()
        finally:lock.unlink(missing_ok=True)
    print(json.dumps(dict(output=str(out/'candidates.csv'),candidates=len(rows),accepted_graph_changed=False,existing_runs_modified=False),indent=2))


if __name__=='__main__':main()
