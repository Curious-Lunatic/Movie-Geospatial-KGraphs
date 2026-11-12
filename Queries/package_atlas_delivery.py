"""Package the current atlas with explicit projection-level validation metadata.

This separate archive preserves the older fully SHACL-validated October package.
Run integration, explorer and verify_cinema_graph.py first.
"""
import hashlib,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'Dataset/integrated'
OUTPUT=ROOT/'Dataset/knowledge_graph/atlas_2026-11-12.zip'
FILES=['graph.ttl','graph_explorer.html','films.csv','film_crosswalk.csv','film_attributes.csv',
       'places.csv','places.geojson','people.csv','characters.csv','genres.csv','songs.csv',
       'claims.csv','location_review.csv','issues.csv','summary.json','romance_places.csv',
       'heritage_genres.csv','graph_verification.json','place_quality.json','song_locations.csv',
       'song_location_review.csv','song_location_query.json','spatial_locations.geojson',
       'india_regions.geojson','region_membership.json','boundary_sources.json']


def main():
    verification=json.loads((DATA/'graph_verification.json').read_text(encoding='utf-8'))
    hashes={name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in FILES}
    if hashes['graph.ttl']!=verification['graph_sha256']:raise ValueError('Graph changed after verification')
    if not all(verification.get(k) for k in ['direct_graph_syntax_parsed','entity_counts_match','rdf_csv_query_results_match','song_shape_conforms']):raise ValueError('Required projection/song checks have not passed')
    if verification['query_result_rows']['song_locations']!=2:raise ValueError('Unexpected curated song coverage')
    manifest=dict(snapshot='2026-11-12',files=hashes,verification=verification,
                  validation_scope='Direct RDF projection; sampled provenance plus both song claims; aggregate reconciliation; all songs checked with SongShape. Full-graph provenance SHACL not rerun.')
    note='''Current atlas snapshot: 12 November 2026

Extract all files into Dataset/integrated/ in the repository (or serve this
directory with a local HTTP server). Open graph_explorer.html. Static film,
song and radius operations work locally; HTTP is needed for region-layer fetches.
The repository launcher also provides local settlement context.

There are 10,709 songs and TWO explicit source-supported song-location links.
These are railway/country reference points, not verified camera coordinates.
48 supplied song-location notes remain for review. Film locations are not
inherited by songs. Proposal JSON downloads remain proposed until source review.

See manifest.json for hashes and exact validation scope. The direct RDF
projection and sampled provenance were checked, both song claims were parsed,
queries reconciled and every song passed SongShape. Full-graph provenance
SHACL was NOT rerun. No old validation.json is included in this archive.
The separate knowledge_graph_1970_2025.zip retains its historical validation.
'''
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        entries={name:(DATA/name).read_bytes() for name in FILES}
        entries.update({'manifest.json':(json.dumps(manifest,indent=2)+'\n').encode(),'README.txt':note.encode()})
        for name,content in entries.items():
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            archive.writestr(info,content)
    with zipfile.ZipFile(OUTPUT) as archive:
        for name,expected in hashes.items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:raise ValueError('Archive mismatch: '+name)
    manifest.update(archive=OUTPUT.name,archive_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),zip_round_trip_hashes_match=True)
    (OUTPUT.parent/'atlas_2026-11-12_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(archive=str(OUTPUT),bytes=OUTPUT.stat().st_size,files=len(entries),round_trip_verified=True),indent=2))


if __name__=='__main__':main()
