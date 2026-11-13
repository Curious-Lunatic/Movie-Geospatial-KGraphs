"""Collect song-specific Wikipedia filming evidence for review, never inherited film locations.

Standard library only. Cached, sequential requests; no accepted graph mutation.
"""
import argparse,csv,hashlib,json,re,sys,time,urllib.error,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILMING=re.compile(r'\b(?:filmed|filming|shot|shooting|picturised|picturized)\b',re.I)
FIELDS='song_id,song,film_id,film,year,place_id,place,latitude,longitude,location_precision,identity_match,source_url,revision_id,retrieved_at,evidence,cache_file,status'.split(',')


def norm(text):
    return re.sub(r'[^\w]+',' ',str(text).casefold().replace('_',' '),flags=re.UNICODE).strip()


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))


def wiki_title(url):
    parts=urllib.parse.urlsplit(url)
    if parts.scheme not in ('http','https') or parts.hostname!='en.wikipedia.org' or not parts.path.startswith('/wiki/'):return None
    return urllib.parse.unquote(parts.path[6:]).replace('_',' ')


class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.blocks=[];self.parts=None;self.links=[];self.anchor=None;self.skip=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','sup'):self.skip.append(tag)
        if self.skip:return
        if tag=='p':self.finish();self.parts=[];self.links=[]
        if tag=='a' and self.parts is not None:
            attrs=dict(attrs);href=attrs.get('href','');title=wiki_title(urllib.parse.urljoin('https://en.wikipedia.org',href))
            self.anchor=dict(title=title or '',parts=[]) if title else None
    def handle_endtag(self,tag):
        if self.skip:
            if tag==self.skip[-1]:self.skip.pop()
            return
        if tag=='a' and self.anchor:
            self.links.append(dict(title=self.anchor['title'],label=''.join(self.anchor['parts'])));self.anchor=None
        if tag=='p':self.finish()
    def handle_data(self,text):
        if self.skip or self.parts is None:return
        self.parts.append(text)
        if self.anchor:self.anchor['parts'].append(text)
    def finish(self):
        if self.parts is not None:
            text=' '.join(''.join(self.parts).split())
            if FILMING.search(text):self.blocks.append(dict(text=text,links=self.links))
        self.parts=None;self.anchor=None;self.links=[]


def candidates(blocks,songs,places):
    """A same-sentence co-mention is a candidate, not an accepted filmed-at assertion."""
    place_index=defaultdict(dict)
    for p in places:
        for name in [p['place_name'],*json.loads(p.get('aliases') or '[]')]:
            if norm(name):place_index[norm(name)][p['place_id']]=p
    result=[];seen=set()
    for block in blocks:
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z“"])',block['text']):
            if not FILMING.search(sentence):continue
            text=norm(sentence)
            for song in songs:
                title=norm(song['title'])
                if not title or not re.search(r'(?<!\w)'+re.escape(title)+r'(?!\w)',text):continue
                # Very short song names need quoted or linked identity support.
                if len(title)<5 and not any(norm(a['label'])==title for a in block['links']) and not re.search(r'["“‘\']'+re.escape(song['title'])+r'["”’\']',sentence,re.I):continue
                matches={}
                for link in block['links']:
                    for name in [link['label'],link['title']]:
                        key=norm(name)
                        if key and re.search(r'(?<!\w)'+re.escape(key)+r'(?!\w)',text):matches.update(place_index.get(key,{}))
                # Unmatched locations are retained as evidence gaps for manual extraction.
                for p in list(matches.values()) or [None]:
                    dedup=(song['song_id'],p['place_id'] if p else '',sentence)
                    if dedup in seen:continue
                    seen.add(dedup)
                    result.append(dict(song_id=song['song_id'],song=song['title'],place_id=p['place_id'] if p else '',place=p['place_name'] if p else '',latitude=p.get('latitude','') if p else '',longitude=p.get('longitude','') if p else '',location_precision=p.get('location_precision','unknown_reference') if p else 'unknown_reference',identity_match='candidate_existing_place' if p else 'place_needs_identification',evidence=sentence,status='needs_review'))
    return result


def fetch_page(title,cache,delay,resume):
    cache_file=cache/(hashlib.sha256(title.encode()).hexdigest()+'.json')
    if resume and cache_file.exists():return json.loads(cache_file.read_text(encoding='utf-8')),cache_file
    time.sleep(delay)
    params=urllib.parse.urlencode(dict(action='parse',page=title,prop='text|revid',redirects=1,format='json',formatversion=2,maxlag=5))
    request=urllib.request.Request('https://en.wikipedia.org/w/api.php?'+params,headers={'User-Agent':'GoodWillMapping-SongEvidence/1.0 (https://github.com/Curious-Lunatic/Movie-Geospatial-KGraphs; research evidence collection)','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=35) as response:raw=response.read()
    body=json.loads(raw)
    if 'error' in body:raise ValueError('Wikipedia API: '+body['error'].get('code','unknown'))
    parsed=body['parse'];parser=Paragraphs();parser.feed(parsed['text']);parser.finish()
    snapshot=dict(title=parsed['title'],revision_id=parsed.get('revid',''),source_url='https://en.wikipedia.org/wiki/'+urllib.parse.quote(parsed['title'].replace(' ','_'),safe=''),retrieved_at=datetime.now(timezone.utc).isoformat(),response_sha256=hashlib.sha256(raw).hexdigest(),blocks=parser.blocks)
    temporary=cache_file.with_suffix('.tmp');temporary.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(cache_file)
    return snapshot,cache_file


def main():
    # RTK expects UTF-8 bytes even when Windows selects a legacy console encoding.
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit',type=int,default=1500,help='Maximum film/source-page jobs; not a promised result count')
    parser.add_argument('--delay',type=float,default=1.5,help='Minimum seconds between sequential requests')
    parser.add_argument('--resume',action='store_true',help='Reuse successful page caches and merge/deduplicate prior candidates')
    parser.add_argument('--dry-run',action='store_true',help='Show available work without downloading pages')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/song-location-scrape')
    args=parser.parse_args()
    if args.limit<1 or not 1<=args.delay<=60:parser.error('Limit must be a positive integer and delay must be 1-60 seconds')
    data=ROOT/'Dataset/integrated'
    if not (data/'songs.csv').exists():parser.error('Build first: python Queries/build_integrated_graph.py')
    songs=read(data/'songs.csv');song_index={s['song_id']:s for s in songs};films={f['film_id']:f for f in read(data/'films.csv')};places=read(data/'places.csv')
    by_film=defaultdict(list)
    for song in songs:by_film[song['film_id']].append(song)
    jobs=set()
    with (data/'claims.csv').open(encoding='utf-8-sig',newline='') as stream:
        for claim in csv.DictReader(stream):
            if claim['relation']!='in_film' or claim['subject_id'] not in song_index:continue
            title=wiki_title(claim['source_url'])
            if title and claim['object_id'] in films:jobs.add((claim['object_id'],title))
    priority={r['film_id'] for r in read(data/'song_location_review.csv')} if (data/'song_location_review.csv').exists() else set()
    jobs=sorted(jobs,key=lambda j:(j[0] not in priority,films[j[0]]['title'],j[1]))[:args.limit]
    if args.dry_run:
        print(json.dumps(dict(requested_limit=args.limit,available_page_jobs=len(jobs),known_songs=len(songs),network_requests=0,output=str(args.output/'candidates.csv')),indent=2))
        return
    cache=args.output/'cache';cache.mkdir(parents=True,exist_ok=True)
    output=args.output/'candidates.csv';error_file=args.output/'errors.jsonl'
    rows=read(output) if args.resume and output.exists() else [];seen={(r['song_id'],r['place_id'],r['source_url'],r['evidence']) for r in rows}
    def save():
        temporary=output.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
        temporary.replace(output)
    print(f'Scanning {len(jobs)} film/source pages; {len(songs)} known songs. Accepted graph stays unchanged.',flush=True)
    failures=0;completed=0
    try:
        for index,(fid,title) in enumerate(jobs,1):
            try:
                snapshot,path=fetch_page(title,cache,args.delay,args.resume)
                found=candidates(snapshot['blocks'],by_film[fid],places)
                for row in found:
                    row.update(film_id=fid,film=films[fid]['title'],year=films[fid]['release_year'],source_url=snapshot['source_url'],revision_id=snapshot['revision_id'],retrieved_at=snapshot['retrieved_at'],cache_file=str(path))
                    key=(row['song_id'],row['place_id'],row['source_url'],row['evidence'])
                    if key not in seen:rows.append(row);seen.add(key)
                completed+=1;failures=0;save()
                print(f'[{index}/{len(jobs)}] {title.encode("ascii","backslashreplace").decode()}: {len(found)} candidates; {len(rows)} total',flush=True)
            except (urllib.error.URLError,TimeoutError,ValueError,KeyError,OSError) as error:
                failures+=1
                with error_file.open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(page=title,error=str(error),time=datetime.now(timezone.utc).isoformat()))+'\n')
                print(f'[{index}/{len(jobs)}] Request/extraction failed; recorded in errors.jsonl.',flush=True)
                if isinstance(error,urllib.error.HTTPError) and error.code in (401,403,429):
                    print('Access denied or rate limited. Stopping; no access-control bypass. Retry with --resume after resolving access or waiting.',flush=True);break
                if failures>=3:print('Three consecutive failures. Stopping; successful work is cached.',flush=True);break
    except KeyboardInterrupt:print('\nInterrupted; successful pages are cached. Run the same command with --resume.',flush=True)
    finally:save()
    print(json.dumps(dict(successful_pages=completed,review_candidates=len(rows),output=str(output),accepted_graph_changed=False),indent=2),flush=True)


if __name__=='__main__':main()
