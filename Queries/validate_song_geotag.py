"""Validate a proposed song geotag. Validation never promotes it into accepted RDF."""
import argparse,csv,json,math,re
from pathlib import Path
from urllib.parse import urlsplit

PRECISION={'site_reference','route_reference','locality_reference','country_reference','unknown_reference'}


def validate(value,song_ids):
    if not isinstance(value,dict):raise ValueError('Expected a geotag object')
    if value.get('status','proposed')!='proposed':raise ValueError('New geotags must remain proposed until evidence review')
    if value.get('song_id') not in song_ids:raise ValueError('Unknown song identifier')
    if not isinstance(value.get('place_name'),str) or not 1<=len(value['place_name'].strip())<=200:raise ValueError('Invalid place name')
    for key,limit in [('latitude',90),('longitude',180)]:
        n=value.get(key)
        if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or abs(n)>limit:raise ValueError('Invalid '+key)
    if not isinstance(value.get('source_url'),str) or len(value['source_url'])>2048:raise ValueError('Invalid evidence URL')
    source=urlsplit(value['source_url'])
    if source.scheme not in ['http','https'] or not source.hostname or source.username or source.password:raise ValueError('Invalid evidence URL')
    if not isinstance(value.get('evidence'),str) or not 20<=len(value['evidence'].strip())<=2000:raise ValueError('Explain the song-specific evidence')
    if value.get('location_precision') not in PRECISION:raise ValueError('Invalid location precision')
    timestamp=value.get('scene_timestamp','')
    if not isinstance(timestamp,str) or (timestamp and not re.fullmatch(r'(?:\d{1,2}:[0-5]\d:[0-5]\d|\d{1,2}:[0-5]\d)',timestamp)):raise ValueError('Invalid scene timestamp')
    return dict(value,status='proposed')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('proposal',type=Path);args=parser.parse_args()
    with (Path(__file__).resolve().parents[1]/'Dataset/integrated/songs.csv').open(encoding='utf-8',newline='') as handle:ids={r['song_id'] for r in csv.DictReader(handle)}
    result=validate(json.loads(args.proposal.read_text(encoding='utf-8')),ids)
    print(json.dumps(dict(schema_valid=True,status=result['status'],accepted_graph_changed=False),indent=2))


if __name__=='__main__':main()
