"""Build the lightweight atlas, indexed catalogue, review summary and quality assets."""
import hashlib,json,shutil
from pathlib import Path
from atlas_catalog import ROOT,build,rows,json_file


def main():
    directory=ROOT/'Dataset/integrated';coverage=build(directory)
    source=ROOT/'Queries/portal';target=directory/'portal';target.mkdir(exist_ok=True)
    for path in source.iterdir():
        if path.is_file():shutil.copyfile(path,directory/path.name if path.suffix=='.html' else target/path.name)
    for file in ['leaflet.js','leaflet.css']:shutil.copyfile(ROOT/'Queries/webmap/vendor'/file,target/file)
    for file in ['spatial_tools.js','spatial_engine.js','song_geo.js','chat_engine.js']:shutil.copyfile(ROOT/'Queries/webmap'/file,target/file)
    shutil.copyfile(ROOT/'Queries/webmap/vendor/turf.min.js',target/'turf.min.js')
    for name in ['LEAFLET-LICENSE','TURF-LICENSE']:shutil.copyfile(ROOT/'Queries/webmap/vendor'/name,target/name)
    html=directory/'atlas.html';text=html.read_text(encoding='utf-8').replace('<script defer src="portal/atlas.js">','<script defer src="portal/model.js"></script><script defer src="portal/atlas.js">');html.write_text(text,encoding='utf-8')
    decisions=rows(ROOT/'Dataset/song_review/decisions.csv');items=[];counts={}
    for row in decisions:
        counts[row['status']]=counts.get(row['status'],0)+1;items.append(dict(id='historic-'+row['candidate_csv_row'],status=row['status'],version=1,payload=dict(song=row['song'],film=row['film'],place=row['place'],source_url=row['source_url']),note=row['reason'],batch='reviewed-437'))
    json_file(directory/'atlas-data/review-summary.json',dict(counts=counts,items=items,read_only=True))
    snapshot=ROOT/'Dataset/discovery_snapshot'
    if (snapshot/'review-summary.json').exists():shutil.copyfile(snapshot/'review-summary.json',directory/'atlas-data/review-summary.json')
    progress=[]
    for folder in ['song-location-all','discovery-v2']:
        path=ROOT/'outputs'/folder/'summary.json'
        if path.exists():
            r=json.loads(path.read_text(encoding='utf-8'));progress.append(dict(run=folder,completed=r.get('completed',r.get('processed_pages',r.get('processed',0))),pending=r.get('pending',r.get('pending_queries',0)),candidates=r.get('candidates',0),requests_this_run=r.get('network_requests_this_run',r.get('network_requests',r.get('requests',0)))))
    if progress:json_file(directory/'atlas-data/discovery-progress.json',dict(runs=progress,note='Search/page jobs are not unique songs. Candidates require source review before acceptance.'))
    elif (snapshot/'progress.json').exists():shutil.copyfile(snapshot/'progress.json',directory/'atlas-data/discovery-progress.json')
    else:json_file(directory/'atlas-data/discovery-progress.json',dict(runs=[],note='No retained discovery execution is available in this checkout.'))
    analysis=ROOT/'GIS/analysis'
    if analysis.exists():shutil.copytree(analysis,directory/'analysis',dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.qgz~','*.gpkg-wal','*.gpkg-shm'))
    for name in ['identity_changes.csv','identity_duplicates.csv','entity_aliases.csv']:assert (directory/name).exists()
    print('Built atlas.html, review.html, compressed on-demand assets and indexed catalogue.')


if __name__=='__main__':main()
