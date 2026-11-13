"""Global, multilingual discovery with durable checkpoints and a per-run request budget.

Original scrape directories/processes are never modified. All extracted records
remain review candidates. A request budget leaves pending SQLite jobs intact.
"""
import argparse,hashlib,json,re,sys,urllib.parse
from pathlib import Path
from collections import defaultdict
from discovery_queue import Queue
from scrape_song_locations_all import (ROOT,LEGACY,FAST,FIELDS,extended_inputs,location_ranking,song_pages,query_tasks,resolve_page_films,new_song_mentions,decorate,unknown_sites,row_marker,article_url)
from scrape_song_locations_fast import Client,Matcher,AccessStopped,decode_batch,digest,write_csv,write_json,norm,read

import scrape_song_locations_fast as fast
# Only this new process receives the extended filming vocabulary. Earlier runs keep their own code/state.
fast.FILMING=re.compile(fast.FILMING.pattern+r'|फिल्माय|फ़िल्माय|फिल्मांकन|शूट|पिक्चराइज|படமாக்க|படப்பிடிப்பு|ചിത്രീകര|చిత్రీకర|চিত্রী|ಶೂಟಿಂಗ್',re.I)
LANGUAGES={'en','hi','ta','te','ml','bn','mr','kn'}


def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='replace')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--max-jobs',type=int,default=10000);p.add_argument('--retry-blocked',action='store_true');p.add_argument('--languages',default='en,hi');p.add_argument('--max-requests',type=int,default=2000);p.add_argument('--batch-size',type=int,default=20);p.add_argument('--delay',type=float,default=1);p.add_argument('--resume',action='store_true');p.add_argument('--offline',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--output',type=Path,default=ROOT/'outputs/discovery-v2');args=p.parse_args()
    langs=list(dict.fromkeys(args.languages.split(',')))
    if not set(langs)<=LANGUAGES or not langs or not 1<=args.batch_size<=20 or args.max_requests<1 or args.max_jobs<1 or not 1<=args.delay<=60:p.error('Choose supported languages, a positive request budget, batch size 1–20 and delay 1–60 seconds')
    out=args.output.resolve()
    for old in [LEGACY,FAST,ROOT/'outputs/song-location-all']:
        old=old.resolve()
        if old==out or old in out.parents or out in old.parents:p.error('Use a separate output directory; earlier scraping outputs are read-only')
    films,by_film,by_song,places,bindings,priority=extended_inputs();place_lookup={x['place_id']:x for x in places};article_index=defaultdict(set);qid_index=defaultdict(set)
    for title,ids in bindings.items():article_index[norm(title)].update(ids)
    for fid,f in films.items():
        if f['wikidata_id']:qid_index[f['wikidata_id']].add(fid)
    from atlas_catalog import rows
    ranked=location_ranking(places,rows(ROOT/'Dataset/integrated/claims.csv'));tasks=query_tasks(ranked,by_song,films);titles=list(dict.fromkeys(list(bindings)+song_pages(by_song)))
    if args.dry_run:
        print(json.dumps(dict(film_and_song_pages=len(titles),automatic_queries_per_language=len(tasks),languages=langs,request_budget_this_run=args.max_requests,durable_pending_jobs=True,old_runs_modified=False,output=str(out)),indent=2));return
    queue=Queue(out/'queue.sqlite')
    if args.retry_blocked:queue.retry('blocked')
    queue.retry('waiting');queue.add_many([('page','en',dict(title=t)) for t in titles]+[('search',lang,t) for lang in langs for t in tasks]);matcher=Matcher(places);client=Client(args.delay);processed=0
    def wiki(language,**params):return client.get('https://'+language+'.wikipedia.org/w/api.php?'+urllib.parse.urlencode(dict(format='json',formatversion=2,maxlag=5,**params)))
    def consume(title,snapshot,path,language):
        bound=resolve_page_films(title,snapshot,bindings,by_song,article_index,qid_index)
        if len(bound)!=1:return
        for fid in bound:
            added=new_song_mentions(snapshot.get('blocks',[]),fid,by_film[fid]);songs=by_film[fid]+added
            new_ids={s['song_id'] for s in songs if s.get('new_song')};found=matcher.extract(snapshot.get('blocks',[]),songs)
            for row in found:
                row.update(film_id=fid,film=films[fid]['title'],year=films[fid]['release_year'],source='Wikipedia',source_url=snapshot['source_url'],revision_id=snapshot.get('revision_id',''),retrieved_at=snapshot['retrieved_at'],cache_file=str(path),song_identity='new_song_needs_review' if row['song_id'] in new_ids else 'existing_song');decorate(row,place_lookup)
            found+=unknown_sites(found,snapshot.get('blocks',[]))
            for row in found:
                row['language']=language;identity=hashlib.sha256(json.dumps(row_marker(row),ensure_ascii=False).encode()).hexdigest();queue.candidate(identity,row)
            by_film[fid].extend(added)
            for song in added:by_song[norm(song['title'])].append(song);queue.add('page',language,dict(title=song['title']+' (song)'))
    def save():
        summary=queue.summary();summary.update(network_requests_this_run=client.requests,request_budget_this_run=args.max_requests,accepted_graph_changed=False,old_runs_modified=False)
        write_json(out/'summary.json',summary);write_csv(out/'candidates.csv',[{k:r.get(k,'') for k in FIELDS+['language']} for r in queue.candidates()],FIELDS+['language'])
        print(json.dumps(dict(completed=summary['completed'],pending=summary['pending'],candidates=summary['candidates'],requests=client.requests)),flush=True)
    try:
        print('Durable global discovery started. Pending searches survive budgets and restarts.',flush=True)
        while client.requests<args.max_requests and processed<args.max_jobs:
            jobs=queue.claim('page',min(args.batch_size,args.max_jobs-processed),include_waiting=not args.offline);search_jobs=[] if args.offline else queue.claim('search',1)
            if not jobs and not search_jobs:break
            pending=[]
            for job in jobs:
                title=job['payload']['title'];lang=job['language'];own=out/'cache'/lang/(digest(title)+'.json');candidates=[own]
                if lang=='en':candidates.extend([ROOT/'outputs/song-location-all/wiki-cache'/(digest(title)+'.json'),FAST/'wiki-cache'/(digest(title)+'.json'),LEGACY/'cache'/(digest(title)+'.json')])
                path=next((v for v in candidates if v.exists()),None)
                if path:
                    snapshot=json.loads(path.read_text(encoding='utf-8'))
                    if not snapshot.get('unavailable'):consume(title,snapshot,path,lang)
                    queue.finish(job['id'])
                else:pending.append(job)
            if pending:
                if args.offline:
                    for job in pending:queue.finish(job['id'],'waiting')
                    # Do not repeatedly claim the same uncached jobs in offline mode.
                    # Waiting jobs are excluded during this offline pass; inspect later cached pages too.
                else:
                    lang=pending[0]['language'];wanted=[j['payload']['title'] for j in pending]
                    body,h=wiki(lang,action='query',prop='revisions|pageprops|langlinks',lllimit=500,ppprop='wikibase_item',titles='|'.join(wanted),rvprop='ids|timestamp|content',rvslots='main',redirects=1);decoded=decode_batch(body,wanted,h);qids={v['title']:v.get('pageprops',{}).get('wikibase_item','') for v in body.get('query',{}).get('pages',[])}
                    for page in body.get('query',{}).get('pages',[]):
                        for entry in page.get('langlinks',[]):
                            if entry.get('lang') in langs:queue.add('page',entry['lang'],dict(title=entry['title']))
                    for job in pending:
                        title=job['payload']['title'];snapshot=decoded.get(title,dict(unavailable=True,title=title,blocks=[],source_url=article_url(title),retrieved_at=''))
                        snapshot['source_url']=snapshot['source_url'].replace('https://en.wikipedia.org/','https://'+lang+'.wikipedia.org/');snapshot['wikidata_id']=qids.get(snapshot['title'],'');path=out/'cache'/lang/(digest(title)+'.json');write_json(path,snapshot)
                        if not snapshot.get('unavailable'):consume(title,snapshot,path,lang)
                        queue.finish(job['id'])
            for job in search_jobs:
                if client.requests>=args.max_requests:queue.finish(job['id'],'queued');continue
                task=job['payload'];cache=out/'search-cache'/job['language']/(digest(task['query']+'|'+str(task.get('offset',0)))+'.json')
                if args.resume and cache.exists():body=json.loads(cache.read_text(encoding='utf-8'))
                else:body,_=wiki(job['language'],action='query',list='search',srsearch=task['query'],srnamespace=0,srlimit=50,sroffset=task.get('offset',0),srprop='');write_json(cache,body)
                queue.add_many([('page',job['language'],dict(title=hit['title'])) for hit in body.get('query',{}).get('search',[])])
                continuation=body.get('continue',{}).get('sroffset')
                if continuation is not None:queue.add('search',job['language'],dict(task,offset=continuation))
                queue.finish(job['id'])
            processed+=len(jobs)+len(search_jobs)
            if processed%100<args.batch_size or not jobs:save()
        save()
    except KeyboardInterrupt:print('Paused. Completed work is saved; use --resume to continue.',flush=True)
    except (AccessStopped,ValueError,OSError,KeyError) as error:
        if isinstance(error,AccessStopped):queue.block_owned(str(error))
        write_json(out/'last-error.json',dict(error=str(error),provider_access_bypassed=False));print('Provider/data issue. Work is saved; see last-error.json.',flush=True)
    finally:queue.release();save()


if __name__=='__main__':main()
