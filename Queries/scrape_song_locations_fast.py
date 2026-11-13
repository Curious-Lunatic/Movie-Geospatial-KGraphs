"""Separate, batch-based song-location evidence collector. Never writes legacy-run files.

Wikipedia: batch revision reads plus place-focused discovery. TMDB: cached film
metadata and optional authenticated refresh. IMDb: authorized evidence CSV import.
All location matches remain needs_review; no accepted graph mutations.
"""
import argparse,csv,gzip,hashlib,html,json,os,re,sys,time,urllib.error,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from scrape_song_locations import FILMING,norm,read,wiki_title

ROOT=Path(__file__).resolve().parents[1]
LEGACY=ROOT/'outputs/song-location-scrape'
UA='GoodWillMapping-SongEvidence/2.0 (https://github.com/Curious-Lunatic/Movie-Geospatial-KGraphs; academic evidence collection)'
FIELDS='song_id,song,film_id,film,year,place_id,place,latitude,longitude,location_precision,identity_match,source,source_url,revision_id,retrieved_at,evidence,cache_file,status'.split(',')


def stamp():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def write_csv(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    tmp.replace(path)


def protect_output(output,legacy=LEGACY):
    out,old=output.resolve(),legacy.resolve()
    if out==old or old in out.parents or out in old.parents:raise ValueError('Choose an output directory separate from the existing scraping directory.')


class AccessStopped(Exception):pass


class Client:
    def __init__(self,delay=1):self.delay=delay;self.last=0;self.requests=0
    def get(self,url,headers=None):
        time.sleep(max(0,self.delay-(time.monotonic()-self.last)));self.last=time.monotonic();self.requests+=1
        request=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json','Accept-Encoding':'gzip',**(headers or {})})
        try:
            with urllib.request.urlopen(request,timeout=40) as response:
                raw=response.read()
                if response.headers.get('Content-Encoding')=='gzip':raw=gzip.decompress(raw)
        except urllib.error.HTTPError as error:
            # Do not log request URLs: TMDB v3 API-key parameters may be present.
            if error.code in (401,403,429):raise AccessStopped('Provider returned HTTP '+str(error.code)+'; stopped without bypass or automatic retry.') from None
            raise ValueError('Provider returned HTTP '+str(error.code)) from None
        except (urllib.error.URLError,TimeoutError):raise ValueError('Provider connection failed or timed out.') from None
        body=json.loads(raw)
        if 'error' in body:
            code=str(body['error'].get('code','unknown'))
            if code in ('maxlag','ratelimited','readonly'):raise AccessStopped('Wikipedia requested a pause: '+code)
            raise ValueError('Wikipedia API error: '+code)
        return body,hashlib.sha256(raw).hexdigest()
    def wiki(self,**params):return self.get('https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode(dict(format='json',formatversion=2,maxlag=5,**params)))


def wikitext_blocks(text):
    """Extract prose/link candidates, without interpreting templates as evidence."""
    text=re.sub(r'<!--.*?-->|<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*/\s*>','',text,flags=re.S|re.I)
    text=re.sub(r'\{\|.*?\|\}','',text,flags=re.S)
    for _ in range(12):
        clean=re.sub(r'\{\{[^{}]*\}\}','',text)
        if clean==text:break
        text=clean
    blocks=[]
    for raw in re.split(r'\n\s*\n|^==+.*?==+\s*$',text,flags=re.M):
        if not FILMING.search(raw):continue
        links=[]
        def replace(match):
            pieces=match[1].split('|');title=pieces[0].split('#')[0].strip();label=pieces[-1].strip()
            if ':' in title:return ''
            links.append(dict(title=title.replace('_',' '),label=label));return label
        plain=re.sub(r'\[\[([^\[\]]+)\]\]',replace,raw)
        plain=re.sub(r'\[https?://\S+(?:\s+([^\]]*))?\]',lambda m:m[1] or '',plain)
        plain=' '.join(html.unescape(re.sub(r'<[^>]+>','',plain).replace("'''",'').replace("''",'')).split())
        if FILMING.search(plain):blocks.append(dict(text=plain,links=links))
    return blocks


def decode_batch(body,requested,response_hash):
    query=body.get('query',{});aliases={a['from']:a['to'] for a in query.get('normalized',[])+query.get('redirects',[])}
    pages={p['title']:p for p in query.get('pages',[])};result={}
    for title in requested:
        resolved=title;seen=set()
        while resolved in aliases and resolved not in seen:seen.add(resolved);resolved=aliases[resolved]
        page=pages.get(resolved)
        if not page or page.get('missing') or not page.get('revisions'):continue
        revision=page['revisions'][0];content=revision.get('slots',{}).get('main',{}).get('content')
        if content is None:continue
        result[title]=dict(title=page['title'],revision_id=revision.get('revid',''),source_url='https://en.wikipedia.org/wiki/'+urllib.parse.quote(page['title'].replace(' ','_'),safe=''),retrieved_at=stamp(),response_sha256=response_hash,blocks=wikitext_blocks(content),linked_pages=re.findall(r'\[\[([^\[\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]',content))
    return result


class Matcher:
    def __init__(self,places):
        self.places=defaultdict(dict)
        generic={'the','a','an','and','of','in','on','at','temple','monastery','cathedral','church','mosque','fort','palace','studio','studios','school','college','university'}
        for p in places:
            for name in [p['place_name'],*json.loads(p.get('aliases') or '[]')]:
                key=norm(name)
                if len(key)>2 and key not in generic:self.places[key][p['place_id']]=p
        names=sorted(self.places,key=lambda s:(-len(s),s))
        self.names=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(n) for n in names)+r')(?!\w)') if names else re.compile(r'(?!)')
        self.song_patterns={}
    def extract(self,blocks,songs):
        found=[];seen=set()
        for block in blocks:
            for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z“"])',block['text']):
                if not FILMING.search(sentence):continue
                text=norm(sentence);matched={}
                for match in self.names.finditer(text):
                    group=self.places[match[0]]
                    for pid,p in group.items():matched[pid]=(p,'ambiguous_alias' if len(group)>1 else 'candidate_existing_place')
                for song in songs:
                    title=norm(song['title'])
                    if not title:continue
                    pattern=self.song_patterns.setdefault(title,re.compile(r'(?<!\w)'+re.escape(title)+r'(?!\w)'))
                    song_match=pattern.search(text)
                    if not song_match:continue
                    outside=text[:song_match.start()]+' '+text[song_match.end():]
                    quoted=bool(re.search(r'["“‘\']\s*'+re.escape(song['title'].rstrip('., '))+r'[.,]?\s*["”’\']',sentence,re.I))
                    if not quoted and not re.search(r'\b(?:song|songs|track|number|music video)\b',outside,re.I):continue
                    if len(title)<5 and not any(norm(a.get('label',''))==title for a in block.get('links',[])) and not re.search(r'["“‘\']'+re.escape(song['title'])+r'["”’\']',sentence,re.I):continue
                    for p,identity in list(matched.values()) or [(None,'place_needs_identification')]:
                        # A place appearing only inside the song title is not filming evidence.
                        if p:
                            labels=[norm(p['place_name']),*[norm(a) for a in json.loads(p.get('aliases') or '[]')]]
                            if not any(label and re.search(r'(?<!\w)'+re.escape(label)+r'(?!\w)',outside) for label in labels):continue
                        key=(song['song_id'],p['place_id'] if p else '',sentence)
                        if key in seen:continue
                        seen.add(key)
                        found.append(dict(song_id=song['song_id'],song=song['title'],place_id=p['place_id'] if p else '',place=p['place_name'] if p else '',latitude=p.get('latitude','') if p else '',longitude=p.get('longitude','') if p else '',location_precision=p.get('location_precision','unknown_reference') if p else 'unknown_reference',identity_match=identity,evidence=sentence,status='needs_review'))
        return found


def load_inputs():
    data=ROOT/'Dataset/integrated';songs=read(data/'songs.csv');films={f['film_id']:f for f in read(data/'films.csv')};places=read(data/'places.csv')
    by_film=defaultdict(list);by_song=defaultdict(list);jobs=defaultdict(set)
    for song in songs:by_film[song['film_id']].append(song);by_song[norm(song['title'])].append(song)
    with (data/'claims.csv').open(encoding='utf-8-sig',newline='') as stream:
        for claim in csv.DictReader(stream):
            if claim['relation']!='in_film' or claim['object_id'] not in films:continue
            title=wiki_title(claim['source_url'])
            if title:jobs[title].add(claim['object_id'])
    priority={r['film_id'] for r in read(data/'song_location_review.csv')} if (data/'song_location_review.csv').exists() else set()
    return films,by_film,by_song,places,jobs,priority


def tmdb_context(films,out,client,refresh=False,limit=1500):
    cache={};path=ROOT/'Queries/tmdb_details.jsonl'
    if path.exists():
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                try:d=json.loads(line);cache[str(d['id'])]=d
                except (ValueError,KeyError):continue
    token=os.getenv('TMDB_API_READ_ACCESS_TOKEN') or os.getenv('TMDB_READ_ACCESS_TOKEN');key=os.getenv('TMDB_API_KEY')
    if refresh and not (token or key):raise ValueError('Set TMDB_API_READ_ACCESS_TOKEN or TMDB_API_KEY before --fetch-tmdb; cached TMDB metadata works without a key.')
    rows=[];fetched=0
    for fid,f in films.items():
        mid=f.get('tmdb_id','')
        if not mid or not mid.isdigit():continue
        local=out/'tmdb-cache'/(mid+'.json');d=json.loads(local.read_text(encoding='utf-8')) if local.exists() else cache.get(mid)
        if refresh and not local.exists() and fetched<limit:
            params={'append_to_response':'external_ids,keywords'}
            if not token:params['api_key']=key
            d,_=client.get('https://api.themoviedb.org/3/movie/'+mid+'?'+urllib.parse.urlencode(params),{'Authorization':'Bearer '+token} if token else {})
            write_json(local,d);fetched+=1
        if not d:continue
        rows.append(dict(film_id=fid,tmdb_id=mid,imdb_id=(d.get('external_ids') or {}).get('imdb_id') or f.get('imdb_id',''),title=d.get('title',''),release_date=d.get('release_date',''),overview=d.get('overview',''),production_countries=' | '.join(c.get('name','') for c in d.get('production_countries',[])),keywords=' | '.join(k.get('name','') for k in (d.get('keywords') or {}).get('keywords',[])),scope='film_metadata_only',source_url='https://www.themoviedb.org/movie/'+mid))
    write_csv(out/'tmdb_context.csv',rows,'film_id,tmdb_id,imdb_id,title,release_date,overview,production_countries,keywords,scope,source_url'.split(','))
    return dict(cached_context_rows=len(rows),fetched=fetched,scope='Film identity/context only; not song filming evidence')


def imdb_import(path,films,by_film,places):
    if not path:return []
    imdb=defaultdict(list);place_map=defaultdict(dict)
    for fid,f in films.items():
        if f.get('imdb_id'):imdb[f['imdb_id']].append(fid)
    for p in places:
        for label in [p['place_name'],*json.loads(p.get('aliases') or '[]')]:place_map[norm(label)][p['place_id']]=p
    rows=[]
    for supplied in read(path):
        ids=imdb.get(supplied.get('imdb_id',''),[])
        if len(ids)!=1:continue
        fid=ids[0];songs=[s for s in by_film[fid] if norm(s['title'])==norm(supplied.get('song',''))]
        if len(songs)!=1 or len(supplied.get('evidence','').strip())<20:continue
        url=urllib.parse.urlsplit(supplied.get('source_url',''))
        if url.scheme not in ('http','https') or url.hostname not in ('imdb.com','www.imdb.com') or url.username or url.password or not re.search(r'/title/'+re.escape(supplied['imdb_id'])+r'(?:/|$)',url.path):continue
        matches=list(place_map.get(norm(supplied.get('place','')),{}).values());p=matches[0] if len(matches)==1 else None
        rows.append(dict(song_id=songs[0]['song_id'],song=songs[0]['title'],film_id=fid,film=films[fid]['title'],year=films[fid]['release_year'],place_id=p['place_id'] if p else '',place=supplied.get('place',''),latitude=p.get('latitude','') if p else '',longitude=p.get('longitude','') if p else '',location_precision=p.get('location_precision','unknown_reference') if p else 'unknown_reference',identity_match='candidate_existing_place' if p else 'place_needs_identification',source='IMDb authorized export',source_url=supplied['source_url'],revision_id='',retrieved_at=stamp(),evidence=supplied['evidence'],cache_file=str(path),status='needs_review'))
    return rows


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=11000);parser.add_argument('--batch-size',type=int,default=20)
    parser.add_argument('--delay',type=float,default=1);parser.add_argument('--resume',action='store_true')
    parser.add_argument('--place',action='append',default=[],help='Add a place-focused search, e.g. Shimla; repeat for other places')
    parser.add_argument('--search-pages',type=int,default=20);parser.add_argument('--extra-song-pages',type=int,default=500)
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/song-location-fast')
    parser.add_argument('--offline',action='store_true',help='Process completed caches only; zero network requests')
    parser.add_argument('--dry-run',action='store_true',help='Print the plan only; zero writes or requests')
    parser.add_argument('--fetch-tmdb',action='store_true');parser.add_argument('--imdb-evidence',type=Path,help='Authorized CSV: imdb_id,song,place,source_url,evidence')
    args=parser.parse_args()
    if args.limit<1 or not 1<=args.batch_size<=20 or not 1<=args.delay<=60 or not 1<=args.search_pages<=50 or args.extra_song_pages<0:parser.error('Use a positive limit, batch size 1-20, delay 1-60 and search pages 1-50.')
    if args.offline and args.fetch_tmdb:parser.error('--offline cannot be combined with --fetch-tmdb')
    try:protect_output(args.output)
    except ValueError as error:parser.error(str(error))
    films,by_film,by_song,places,jobs,priority=load_inputs();matcher=Matcher(places)
    titles=sorted(jobs,key=lambda t:(not bool(jobs[t]&priority),t))[:args.limit]
    old_count=sum((LEGACY/'cache'/(digest(t)+'.json')).exists() for t in titles)
    if args.dry_run:
        print(json.dumps(dict(known_film_pages=len(titles),completed_legacy_caches_available=old_count,batch_size=args.batch_size,uncached_batches_upper_bound=(len(titles)-old_count+args.batch_size-1)//args.batch_size,place_searches=args.place,extra_song_pages_limit=args.extra_song_pages,output=str(args.output),current_run_modified=False),indent=2));return
    out=args.output;out.mkdir(parents=True,exist_ok=True);lock=out/'.running'
    try:handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(handle)
    except FileExistsError:parser.error('A fast scraper already uses this output folder. Use another output or remove its .running file only after that process has stopped.')
    rows=read(out/'candidates.csv') if args.resume and (out/'candidates.csv').exists() else [];seen={(r['song_id'],r['place_id'],r['source_url'],r['evidence']) for r in rows}
    focus_aliases={norm(p) for p in args.place}
    for p in places:
        if norm(p['place_name']) in focus_aliases:focus_aliases.update(norm(a) for a in json.loads(p.get('aliases') or '[]'))
    client=Client(args.delay);cache=out/'wiki-cache';cache.mkdir(exist_ok=True);errors=[];stats=dict(cached_pages=0,fetched_pages=0,processed_pages=0,source='Wikipedia',accepted_graph_changed=False,current_run_modified=False)
    def save():
        write_csv(out/'candidates.csv',rows,FIELDS)
        focused=[r for r in rows if any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',norm(r['place']+' '+r['evidence'])) for a in focus_aliases)]
        write_csv(out/'focused_candidates.csv',focused,FIELDS)
        write_json(out/'summary.json',dict(stats,total_candidates=len(rows),focused_candidates=len(focused),network_requests=client.requests,errors=errors))
    def add(new):
        for row in new:
            key=(row['song_id'],row['place_id'],row['source_url'],row['evidence'])
            if key not in seen:seen.add(key);rows.append(row)
    def consume(title,snapshot,path):
        fids=jobs.get(title,set())
        if not fids:
            tracks=by_song.get(norm(re.sub(r'\s*\((?:song|soundtrack)\)\s*$','',title,flags=re.I)),[])
            if len(tracks)==1:fids={tracks[0]['film_id']}
        if not fids:
            with (out/'discovery_identity_review.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(page=title,source_url=snapshot['source_url'],cache_file=str(path),status='film_identity_needs_review'))+'\n')
            return
        for fid in fids:
            found=matcher.extract(snapshot['blocks'],by_film[fid])
            for row in found:row.update(film_id=fid,film=films[fid]['title'],year=films[fid]['release_year'],source='Wikipedia',source_url=snapshot['source_url'],revision_id=snapshot.get('revision_id',''),retrieved_at=snapshot['retrieved_at'],cache_file=str(path))
            add(found)
        stats['processed_pages']+=1
    try:
        stats['tmdb']=tmdb_context(films,out,client,args.fetch_tmdb,min(args.limit,1500))
        add(imdb_import(args.imdb_evidence,films,by_film,places));stats['imdb']='Authorized export imported' if args.imdb_evidence else 'Website scraping disabled; authorized export supported. Public IMDb datasets have no filming-location field.'
        # Place search adds sources to the queue; a search result alone is not evidence.
        if not args.offline:
            for place in sorted(focus_aliases):
                if not place or len(place)>100:continue
                search_file=out/'search-cache'/(digest(place)+'.json')
                if args.resume and search_file.exists():result=json.loads(search_file.read_text(encoding='utf-8'))
                else:
                    result,_=client.wiki(action='query',list='search',srsearch='"'+place+'" song (filmed OR shot OR picturised OR picturized)',srnamespace=0,srlimit=args.search_pages,srprop='');write_json(search_file,result)
                for hit in result.get('query',{}).get('search',[]):
                    title=hit['title']
                    if title not in titles and len(titles)<args.limit:titles.insert(0,title)
        print(f'Fast collector: {len(titles)} initial pages, batches of {args.batch_size}; legacy files are read-only.',flush=True)
        cursor=0;discovered=0;handled=set()
        while cursor<len(titles):
            batch=titles[cursor:cursor+args.batch_size];cursor+=len(batch);pending=[]
            for title in batch:
                if title in handled:continue
                handled.add(title);own=cache/(digest(title)+'.json');old=LEGACY/'cache'/(digest(title)+'.json')
                path=own if args.resume and own.exists() else old if old.exists() else None
                if path:
                    try:snapshot=json.loads(path.read_text(encoding='utf-8'))
                    except (ValueError,OSError):pending.append(title);continue
                    consume(title,snapshot,path);stats['cached_pages']+=1
                else:pending.append(title)
            if pending and not args.offline:
                body,response_hash=client.wiki(action='query',prop='revisions',titles='|'.join(pending),rvprop='ids|timestamp|content',rvslots='main',redirects=1)
                decoded=decode_batch(body,pending,response_hash)
                for title in pending:
                    if title not in decoded:errors.append(dict(page=title,error='Missing page or accessible revision'));continue
                    snapshot=decoded[title];path=cache/(digest(title)+'.json');write_json(path,snapshot);consume(title,snapshot,path);stats['fetched_pages']+=1
                    for target in snapshot.get('linked_pages',[]):
                        base=norm(re.sub(r'\s*\((?:song|soundtrack)\)\s*$','',target,flags=re.I))
                        if discovered<args.extra_song_pages and base in by_song and target not in handled and target not in titles and len(titles)<args.limit:
                            titles.append(target);discovered+=1
            save();print(f'[{min(cursor,len(titles))}/{len(titles)}] {len(rows)} review candidates; {stats["cached_pages"]} cached / {stats["fetched_pages"]} fetched pages',flush=True)
    except KeyboardInterrupt:stats['interrupted']=True;print('Interrupted. Resume this separate output with --resume.',flush=True)
    except (AccessStopped,ValueError,OSError,KeyError) as error:
        stats['stopped']=True;errors.append(dict(error=str(error) if isinstance(error,(AccessStopped,ValueError)) else type(error).__name__));print('Stopped; completed evidence is saved. See summary.json for the reason.',flush=True)
    finally:
        try:save()
        finally:lock.unlink(missing_ok=True)
    print(json.dumps(dict(output=str(out/'candidates.csv'),total_candidates=len(rows),accepted_graph_changed=False,current_run_modified=False),indent=2),flush=True)


if __name__=='__main__':main()
