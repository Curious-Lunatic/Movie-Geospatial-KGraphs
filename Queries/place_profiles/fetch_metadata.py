#!/usr/bin/env python3
"""Refresh bounded public Wikidata metadata for existing geocoded place IDs.

Run explicitly; normal builds use the committed snapshot without network access.
Existing geometry and movie claims are not replaced by these classifications.
"""
import csv,hashlib,json,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
API='https://www.wikidata.org/w/api.php'


def entities(ids,props):
    result={}
    ids=sorted(set(ids))
    for start in range(0,len(ids),40):
        batch=ids[start:start+40]
        params=dict(action='wbgetentities',ids='|'.join(batch),props=props,languages='en|ta|hi',format='json')
        req=urllib.request.Request(API+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'GoodWillMapping/1.0 (https://github.com/Curious-Lunatic/Movie-Geospatial-KGraphs)'})
        with urllib.request.urlopen(req,timeout=45) as response: payload=json.load(response)
        if 'entities' not in payload: raise ValueError('Wikidata did not return entities')
        result.update(payload['entities'])
        print('Fetched',start+len(batch),'of',len(ids),'public place/type records',flush=True)
        time.sleep(.25)
    return result


def main():
    with (ROOT/'Dataset/integrated/places.csv').open(encoding='utf-8',newline='') as handle:
        ids=[r['place_id'] for r in csv.DictReader(handle) if r['place_id'].startswith('Q') and r['latitude']]
    ids.append('Q1438739')  # Fort St. George: named reference, no inferred film link.
    raw=entities(ids,'labels|aliases|descriptions|claims')
    def values(item,property):
        return [s['mainsnak']['datavalue']['value'] for s in item.get('claims',{}).get(property,[]) if s.get('rank')!='deprecated' and 'datavalue' in s.get('mainsnak',{})]
    related=set()
    for item in raw.values():
        for prop in ['P31','P17','P131']:
            related.update(v['id'] for v in values(item,prop) if isinstance(v,dict) and 'id' in v)
    labels=entities(related,'labels')
    label=lambda q:labels.get(q,{}).get('labels',{}).get('en',{}).get('value',q)
    records={}
    for q,item in sorted(raw.items()):
        if 'missing' in item: continue
        records[q]=dict(label=item.get('labels',{}).get('en',{}).get('value',''),
            aliases=sorted({r['value'] for r in item.get('labels',{}).values()}|{r['value'] for group in item.get('aliases',{}).values() for r in group}),
            description=item.get('descriptions',{}).get('en',{}).get('value',''),
            instance_of=[dict(id=v['id'],label=label(v['id'])) for v in values(item,'P31') if isinstance(v,dict) and 'id' in v],
            countries=[label(v['id']) for v in values(item,'P17') if isinstance(v,dict) and 'id' in v],
            localities=[label(v['id']) for v in values(item,'P131') if isinstance(v,dict) and 'id' in v],
            coordinates=[v for v in values(item,'P625') if isinstance(v,dict) and v.get('globe','').endswith('/Q2')],
            source='https://www.wikidata.org/wiki/'+q,revision=item.get('lastrevid'))
    output=Path(__file__).parent/'wikidata.json'
    output.write_text(json.dumps(dict(retrieved_at=datetime.now(timezone.utc).isoformat(),api=API,records=records),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Saved',len(records),'records; SHA-256',hashlib.sha256(output.read_bytes()).hexdigest(),flush=True)


if __name__=='__main__': main()
