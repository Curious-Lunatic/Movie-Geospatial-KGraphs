"""Validate and report this batch against the saved November 7 baseline."""
import csv,json
from pathlib import Path
W=Path(__file__).resolve().parent;D=W.parents[1]/'Dataset/integrated'
def read(name):return list(csv.DictReader((D/name).open()))
places={p['place_id']:p for p in read('places.csv')};films={f['film_id']:f for f in read('films.csv')}
baseline=json.loads((W/'round2_baseline.json').read_text());old={tuple(x) for x in baseline['pairs']}
pairs={};existing=set()
for c in read('claims.csv'):
 if c['relation']!='filming':continue
 p=places[c['object_id']]
 if not (p.get('heritage_kind') or p['place_id'].startswith(('heritage:','heritage-component:'))):continue
 pair=(c['subject_id'],p['heritage_parent_id'] or p['place_id']);pairs.setdefault(pair,[]).append(c)
 if c['method']!='reviewed_heritage_expansion':existing.add(pair)
assert old<=pairs.keys(),'Previous connections lost'
added=pairs.keys()-old
geocoded=[p for p in places.values() if p['latitude'] and p['place_id'] not in baseline['geocoded_places']]
snapshots=[json.loads(p.read_text()) for p in (W/'sources').glob('*.json')]
for p in geocoded:
 matches=[s for s in snapshots if s['url']==p['coordinate_source'] and s.get('geo')]
 assert any([float(v.strip()) for v in s['geo'].split(';')]==[float(p['latitude']),float(p['longitude'])] for s in matches),p['place_name']
summary=dict(before_sites=len({p for f,p in old}),after_sites=len({p for f,p in pairs}),before_films=len({f for f,p in old}),after_films=len({f for f,p in pairs}),before_connections=len(old),after_connections=len(pairs),added_connections=len(added),recovered_existing_connections=len(added&existing),newly_sourced_connections=len(added-existing),added_coordinates=len(geocoded),coordinate_places=[p['place_name'] for p in geocoded],unresolved_historic_points=[p['place_name'] for p in places.values() if p.get('heritage_kind') and not p['latitude']])
(W/'round2_report.json').write_text(json.dumps(summary,indent=2)+'\n')
with (W/'round2_connections.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['film','site','addition_type','sources'])
 for film,site in sorted(added):w.writerow([films[film]['title'],places[site]['place_name'],'recovered_existing' if (film,site) in existing else 'newly_sourced',' | '.join(sorted({c['source_url'] or c['source_file'] for c in pairs[film,site]}))])
print(json.dumps(summary,indent=2))
