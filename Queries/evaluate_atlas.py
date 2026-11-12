"""Run the release regression suite and measure actual catalogue/asset coverage."""
import contextlib,hashlib,json,os,statistics,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from atlas_catalog import Catalog,ROOT,json_file
from atlas_questions import answer,resolve

def main():
    logs=ROOT/'outputs/upgrade-validation';logs.mkdir(parents=True,exist_ok=True)
    checks=[]
    environment=dict(os.environ)
    if (ROOT/'.validation-deps').exists():environment['PYTHONPATH']=str(ROOT/'.validation-deps')+os.pathsep+environment.get('PYTHONPATH','')
    commands=[('python_regressions',[sys.executable,'-m','unittest','discover','-s','Queries','-p','test_*.py']),('javascript_regressions',['node','--test',*[str(p.relative_to(ROOT)) for p in (ROOT/'Queries/webmap').glob('*.test.cjs')],'Queries/portal/model.test.cjs'])]
    for name,command in commands:
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',env=environment);(logs/(name+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8');checks.append(dict(check=name,passed=result.returncode==0));print(name+': '+('passed' if result.returncode==0 else 'FAILED'),flush=True)
    cat=Catalog();manifest=json.loads((cat.directory/'atlas-data/catalog.json').read_text(encoding='utf-8'));coverage=json.loads((cat.directory/'atlas-data/coverage.json').read_text(encoding='utf-8'))
    with contextlib.closing(cat.connect()) as con:
        node_counts=dict(con.execute('SELECT kind,COUNT(*) FROM nodes GROUP BY kind'));edge_count=con.execute('SELECT COUNT(*) FROM edges').fetchone()[0];orphans=con.execute('SELECT COUNT(*) FROM edges e LEFT JOIN nodes a ON e.subject=a.id LEFT JOIN nodes b ON e.object=b.id WHERE a.id IS NULL OR b.id IS NULL').fetchone()[0]
    checks.append(dict(check='no_orphan_edges',passed=orphans==0,count=orphans))
    timings=[]
    for _ in range(5):
        start=time.perf_counter();result=cat.search('Fanaa','Film');timings.append((time.perf_counter()-start)*1000)
    film=resolve(cat,'Fanaa 2006','Film');g=cat.graph(film['id']);categories={n['kind'] for n in g['nodes'].values()}
    checks.append(dict(check='Fanaa_six_relationship_categories',passed={'Song','Person','Character','Genre','Place','Heritage'}<=categories,categories=sorted(categories)))
    bismil=answer(cat,'Where was the song Bismil filmed?');checks.append(dict(check='song_specific_evidence',passed=bool(bismil.get('items')) and all(i['edge']['relation']=='song_filming' for i in bismil['items'])))
    initial_bytes=sum((cat.directory/p).stat().st_size for p in ['atlas.html','portal/atlas.js','portal/model.js','portal/atlas.css','portal/leaflet.js','portal/leaflet.css','atlas-data/catalog.json','atlas-data/coverage.json','atlas-data/search-core.json.gz'])
    checks.append(dict(check='initial_public_catalogue_budget',passed=initial_bytes<1500000,bytes=initial_bytes,budget_bytes=1500000,excludes_external_map_tiles=True))
    qgis=ROOT/'GIS/analysis/validation.json';native=json.loads(qgis.read_text(encoding='utf-8')) if qgis.exists() else {}
    checks.append(dict(check='native_QGIS_counts_and_portable_project',passed=native.get('native_counts_reconciled') is True and native.get('project_reopened') is True))
    report=dict(generated_at=datetime.now(timezone.utc).isoformat(),graph_sha256=manifest['graph_sha256'],checks=checks,all_passed=all(c['passed'] for c in checks),nodes=node_counts,distinct_relationships=edge_count,search_median_ms=round(statistics.median(timings),2),search_cold_ms=round(timings[0],2),song_location_links=coverage['summary']['song_filming_claims'],songs_with_location_evidence=coverage['summary']['songs_with_filming_locations'],qgis=native,limitations=coverage['limitations']+['Browser screenshots document exercised UI flows; unit tests do not prove every possible user interaction.','Search timings describe this machine and snapshot, not a universal performance guarantee.'])
    json_file(cat.directory/'evaluation.json',report);json_file(ROOT/'GIS/analysis/product_evaluation.json',report);json_file(cat.directory/'analysis/product_evaluation.json',report)
    print(json.dumps(report,indent=2));return 0 if report['all_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
