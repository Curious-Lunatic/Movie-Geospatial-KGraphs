"""Add explicit song-level location evidence, separately from film locations."""
import hashlib,json
from pathlib import Path


def apply(graph):
    source='../Queries/song_locations/reviewed.json'
    path=graph.data/source
    graph.song_locations=[]
    if not path.exists():return
    from build_integrated_graph import key,norm
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
