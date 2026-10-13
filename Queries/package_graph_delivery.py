#!/usr/bin/env python3
"""Package the fully validated graph, tables and offline explorer for GitHub.

Build the integration, explorer and full validation before running this script.
The ZIP uses fixed entry times and retains exact file bytes and hashes.
"""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'Dataset/integrated'
OUT = ROOT / 'Dataset/knowledge_graph'
FILES = ['graph.ttl','graph_explorer.html','films.csv','film_crosswalk.csv','film_attributes.csv',
         'places.csv','places.geojson','people.csv','characters.csv','genres.csv','songs.csv',
         'claims.csv','location_review.csv','issues.csv','summary.json','validation.json',
         'sparql_demo.csv','romance_places.csv','heritage_genres.csv','graph_verification.json']


def main():
    summary = json.loads((DATA / 'summary.json').read_text(encoding='utf-8'))
    validation = json.loads((DATA / 'validation.json').read_text(encoding='utf-8'))
    if not validation['shacl_conforms'] or not validation['counts_match_csv'] or not validation['rdf_csv_query_results_match']:
        raise ValueError('The graph has not passed full validation and query reconciliation')
    hashes = {name: hashlib.sha256((DATA / name).read_bytes()).hexdigest() for name in FILES}
    if hashes['graph.ttl'] != validation['graph_sha256']:
        raise ValueError('Graph changed after validation')
    OUT.mkdir(exist_ok=True)
    archive = OUT / ('knowledge_graph_%d_%d.zip' % tuple(summary['year_range']))
    manifest = dict(year_range=summary['year_range'], files=hashes,
                    summary={k:v for k,v in summary.items() if k!='sources'}, validation=validation)
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as delivery:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            delivery.writestr(info, (DATA / name).read_bytes())
        info = zipfile.ZipInfo('manifest.json', date_time=(1980,1,1,0,0,0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        delivery.writestr(info, json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(archive) as delivery:
        for name, expected in hashes.items():
            if hashlib.sha256(delivery.read(name)).hexdigest() != expected:
                raise ValueError('ZIP round-trip mismatch: ' + name)
    manifest['archive'] = archive.name
    manifest['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest['zip_round_trip_hashes_match'] = True
    (OUT / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(FILES),'graph_sha256':hashes['graph.ttl']},indent=2))


if __name__ == '__main__':
    main()
