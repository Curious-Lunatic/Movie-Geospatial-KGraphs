"""Reproducible read-only public/portable atlas. Never publishes review databases."""
import argparse,gzip,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
from atlas_catalog import ROOT,json_file

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skip-build',action='store_true');args=p.parse_args()
    if not args.skip_build:
        for script in ['build_integrated_graph.py','build_graph_explorer.py','build_atlas_product.py','evaluate_atlas.py']:
            subprocess.run([sys.executable,str(ROOT/'Queries'/script)],cwd=ROOT,check=True)
    source=ROOT/'Dataset/integrated';target=ROOT/'outputs/release-site';target.mkdir(parents=True,exist_ok=True)
    for name in ['portal','atlas-data','analysis']:shutil.copytree(source/name,target/name,dirs_exist_ok=True)
    for name in ['atlas.html','review.html','graph_explorer.html','india_regions.geojson','region_membership.json','boundary_sources.json','identity_changes.csv','identity_duplicates.csv','entity_aliases.csv','song_locations.csv','evaluation.json','summary.json','romance_places.csv','heritage_genres.csv','spatial_locations.geojson']:
        shutil.copyfile(source/name,target/name)
    for name in ['graph.ttl','claims.csv']:
        with (source/name).open('rb') as stream,(target/(name+'.gz')).open('wb') as output:
            with gzip.GzipFile(filename='',mode='wb',fileobj=output,mtime=0) as zipped:shutil.copyfileobj(stream,zipped)
    for name in ['atlas.html','graph_explorer.html']:
        path=target/name;s=path.read_text(encoding='utf-8')
        for raw in ['graph.ttl','claims.csv']:s=s.replace('href="'+raw+'"','href="'+raw+'.gz"')
        path.write_text(s,encoding='utf-8')
    (target/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=atlas.html"><title>Cinema atlas</title><a href="atlas.html">Open the cinema atlas</a></html>',encoding='utf-8')
    (target/'.nojekyll').write_text('')
    shutil.copyfile(ROOT/'Docs/ATLAS_GUIDE.md',target/'README.md')
    json_file(target/'release_manifest.json',dict(version=2,graph_sha256=json.loads((source/'atlas-data/catalog.json').read_text(encoding='utf-8'))['graph_sha256'],mode='read_only_public',source_repository='https://github.com/Curious-Lunatic/Movie-Geospatial-KGraphs',files={str(f.relative_to(target)).replace('\\','/'):dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in target.rglob('*') if f.is_file() and 'downloads' not in f.parts and f.name!='release_manifest.json'}))
    downloads=target/'downloads';downloads.mkdir(exist_ok=True)
    archive=downloads/'atlas-release.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for file in sorted(target.rglob('*')):
            if file.is_file() and 'downloads' not in file.relative_to(target).parts:output.write(file,str(file.relative_to(target)))
    assert all('.sqlite' not in p.suffix and '.jsonl' not in p.suffix for p in target.rglob('*') if p.is_file())
    assert all(p.stat().st_size<100000000 for p in target.rglob('*') if p.is_file()),'A public file exceeds GitHub upload limits'
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    shutil.copyfile(target/'release_manifest.json',source/'release_manifest.json');(source/'downloads').mkdir(exist_ok=True);shutil.copyfile(archive,source/'downloads/atlas-release.zip')
    print(json.dumps(dict(public_directory=str(target),portable_archive=str(archive),archive_bytes=archive.stat().st_size,private_review_database_included=False),indent=2))

if __name__=='__main__':main()
