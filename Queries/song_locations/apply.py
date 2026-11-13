"""Add explicit song-level location evidence, separately from film locations."""
import collections,hashlib,json
from pathlib import Path


def apply_places(graph,path):
    """Import reviewed reference identities; existing geometry is retained."""
    if not path.exists():return
    raw=path.read_bytes();records=json.loads(raw)['records']
    graph.inputs['../Queries/song_locations/reviewed_places.json']=dict(rows=len(records),sha256=hashlib.sha256(raw).hexdigest())
    from build_integrated_graph import coordinates
    for pid,record in records.items():
        if record['kind'] not in {'city','region','country','venue'}:raise ValueError('Invalid reviewed place kind')
        if record['precision'] not in {'locality_reference','region_reference','country_reference','site_reference'}:raise ValueError('Invalid reviewed place precision')
        if pid not in graph.places:
            point=None
            if record.get('latitude') is not None or record.get('longitude') is not None:
                point=coordinates(record.get('latitude'),record.get('longitude'))
                if not point:raise ValueError('Invalid reviewed reference coordinate')
            graph.add_place(pid,record['name'],point,'place_representative_point',record['coordinate_source'])
        p=graph.places[pid]
        p.update(place_type=record['kind'],location_precision=record['precision'],identity_source=record['identity_source'],classification_source='../Queries/song_locations/reviewed_places.json',description=record['review_note'])
        for field in ['aliases','locality','wikidata_revision']:p.setdefault(field,'[]' if field=='aliases' else '')
        if not p['country_names'] and record.get('country'):p['country_names']=record['country']
    quality=getattr(graph,'place_quality',{})
    quality.update(types=dict(collections.Counter(p.get('place_type','unknown') for p in graph.places.values())),precision=dict(collections.Counter(p.get('location_precision','unknown_reference') for p in graph.places.values())),reviewed_song_place_records=len(records))
    graph.place_quality=quality


def apply(graph):
    source='../Queries/song_locations/reviewed.json'
    path=graph.data/source
    graph.song_locations=[]
    if not path.exists():return
    from build_integrated_graph import key,norm
    apply_places(graph,path.parent/'reviewed_places.json')
    raw=path.read_bytes();records=json.loads(raw)
    graph.inputs[source]=dict(rows=len(records),sha256=hashlib.sha256(raw).hexdigest())
    for number,record in enumerate(records,1):
        fid=graph.lookup('wikidata',record['film_wikidata_id'])
        if not fid or record['place_id'] not in graph.places:continue
        if graph.films[fid]['release_year']!=record['film_year']:raise ValueError('Song filming source year mismatch')
        snapshot=path.parent/record['source_snapshot']
        evidence=snapshot.read_bytes();text=evidence.decode('utf-8')
        if not all(token.casefold() in text.casefold() for token in record['verify_tokens']):raise ValueError('Song evidence snapshot does not match')
        graph.inputs['../Queries/song_locations/'+record['source_snapshot']]=dict(rows=1,sha256=hashlib.sha256(evidence).hexdigest())
        sid=key('song',fid,norm(record['song']))
        if sid not in graph.songs:
            graph.songs[sid]=dict(song_id=sid,title=record['song'],film_id=fid,singers='',music='',lyrics='')
            graph.claim(sid,'in_film',fid,source,number,'reviewed_song_membership',record['source_url'],evidence=record['evidence'])
        graph.claim(sid,'song_filming',record['place_id'],source,number,'reviewed_song_location',record['source_url'],evidence=record['evidence'],precision=record['location_precision'])
        graph.song_locations.append(dict(song_id=sid,film_id=fid,place_id=record['place_id'],location_precision=record['location_precision'],source_url=record['source_url'],source_file=source,source_row=number,evidence=record['evidence'],scene_timestamp='',status='source_supported'))
