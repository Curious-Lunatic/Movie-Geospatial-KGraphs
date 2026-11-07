import csv,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=root/'Queries/heritage_expansion'
if (work/'round2_baseline.json').exists():
 raise SystemExit('The initial review recipe would overwrite the expanded registry. Use the accepted sites.csv/reviewed_claims.json for normal builds; review_round2.py records the later additions.')
sources={p.stem:json.loads(p.read_text()) for p in (work/'sources').glob('*.json')}
places=list(csv.DictReader((root/'Dataset/integrated/places.csv').open()))
films=list(csv.DictReader((root/'Dataset/integrated/films.csv').open()))
def place(name):
 hits=[p for p in places if p['place_name']==name]
 if not hits and name=='Bagore ki Haveli':
  return 'place:b6a6eb7aae9159be1fce9f42'
 assert len(hits)==1,(name,hits)
 return hits[0]['place_id']
registry=[]
for name,source in [
 ('Madh Fort','madh'),('Mehrangarh Fort','mehrangarh'),('Chapora Fort','chapora'),
 ('Tughlaqabad Fort','tughlaqabad'),('Pataudi Palace','pataudi_official'),
 ('Prag Mahal','prag'),('Vijay Vilas Palace','vijay_official'),('Gwalior Fort','gwalior'),
 ('Junagarh Fort','junagarh'),('Jaigarh Fort','jaigarh'),('Naggar Castle','naggar'),
 ('Chand Baori','chand'),('Golconda Fort','golconda'),
 ('Bagore-ki-Haveli','bagore'),('Roopangarh Palace','roopangarh'),
 ('Nahargarh Fort','nahargarh')]:
 coords={'chapora':'chapora_coordinates','pataudi_official':'pataudi','vijay_official':'vijay'}.get(source,source)
 latlon=sources[coords]['geo'].split(';')
 pid=place(name) if name!='Nahargarh Fort' else 'heritage-landmark:nahargarh'
 registry.append(dict(place_id=pid,place_name=name,latitude=latlon[0].strip() if len(latlon)==2 else '',
 longitude=latlon[1].strip() if len(latlon)==2 else '',heritage_source=sources[source]['url'],
 coordinate_source=sources[coords]['url'] if len(latlon)==2 else '',source_snapshot=source+'.json',
 heritage_parent_id='',canonical_id='',heritage_kind='historic_landmark'))
# Keep named features within a fort, and group them under that fort for site totals.
for name,parent in [
 ('Mehrangarh Fort - Sheesh Mahal','Mehrangarh Fort'),
 ('Mehrangarh Fort - Jhanki Mahal Courtyard','Mehrangarh Fort'),
 ('Mehrangarh Fort - Jay (Victory) Pol','Mehrangarh Fort'),
 ('Nahargarh Fort Stepwell','Nahargarh Fort')]:
 parentrow=next(r for r in registry if r['place_name']==parent)
 registry.append(dict(place_id=place(name),place_name=name,latitude='',longitude='',
 heritage_source=parentrow['heritage_source'],coordinate_source='',source_snapshot=parentrow['source_snapshot'],
 heritage_parent_id=parentrow['place_id'],canonical_id='',heritage_kind='historic_component'))
registry.append(dict(place_id=place('Bagore ki Haveli'),place_name='Bagore ki Haveli',latitude='',longitude='',
 heritage_source=sources['bagore']['url'],coordinate_source='',source_snapshot='bagore.json',
 heritage_parent_id='',canonical_id=place('Bagore-ki-Haveli'),heritage_kind='same_site_alias'))
with (work/'sites.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=registry[0]);w.writeheader();w.writerows(registry)
evidence=[]
def claim(title,pid,source,token,summary):
 matches=[f for f in films if f['title']==title]
 assert len(matches)==1,(title,len(matches))
 assert token in sources[source]['text'],(source,token)
 film=matches[0]
 evidence.append(dict(film_id=film['film_id'],title=title,wikidata_id=film['wikidata_id'],
 place_id=pid,source_url=sources[source]['url'],source_snapshot=source+'.json',verify_text=token,
 evidence=summary,retrieved_at=sources[source]['retrieved_at']))
for title,site,source,token,summary in [
 ('Shuddh Desi Romance','Nahargarh Fort','nahargarh','Shuddh Desi Romance','The site article identifies this film among productions shot at the fort.'),
 ('Rang De Basanti','Nahargarh Fort','rajasthan_films','Shot on the majestic Nahargarh fort','Rajasthan Tourism describes filming at Nahargarh Fort.'),
 ('Rang De Basanti','Pataudi Palace','pataudi','Rang De Basanti','The palace article lists the film among productions shot at the palace.'),
 ('Mere Brother Ki Dulhan','Pataudi Palace','pataudi','Mere Brother Ki Dulhan','The palace article lists the film among productions shot at the palace.'),
 ('Hum Dil De Chuke Sanam','Prag Mahal','prag','Hum Dil De Chuke Sanam','The palace article identifies scenes from this film as shot at Prag Mahal.'),
 ('Hum Dil De Chuke Sanam','Vijay Vilas Palace','vijay','Hum Dil De Chuke Sanam','The palace article identifies scenes from this film as shot at the palace.'),
 ('Bhoomi (2017 film)','Chand Baori','chand','Bhoomi','The stepwell article lists the film as a location credit. The linked film is the 2017 Hindi production.'),
 ('Bhool Bhulaiyaa','Chand Baori','chand','Bhool Bhulaiyaa','The stepwell article lists the film as a location credit.'),
 ('Thugs of Hindostan','Mehrangarh Fort','mehrangarh','In March 2018','The fort article records the film crew using the fort in March 2018.'),
 ('Dil Chahta Hai','Chapora Fort','chapora','filming of the Hindi blockbuster','Goa Tourism identifies the fort as a filming location for the 2001 film.'),
 ('Yeh Jawaani Hai Deewani','Bagore-ki-Haveli','rajasthan_films','Shot in the Bagore ki Haveli','Rajasthan Tourism identifies the haveli as a filming location.'),
 ('Awarapan','Mehrangarh Fort','mehrangarh','Awarapan was also shot here','The fort article records filming of Awarapan at the fort.')
]:
 pid=next(r['place_id'] for r in registry if r['place_name']==site)
 claim(title,pid,source,token,summary)
# Official source supports a further connection to an already represented heritage component.
claim('Bajirao Mastani','heritage-component:247rev-005','rajasthan_films',
      'Parts of Bajirao Mastani have been shot','Rajasthan Tourism identifies Amber Palace as a filming location for Bajirao Mastani.')
(work/'reviewed_claims.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
# Counts before this expansion, retained for reproducibility.
claims=list(csv.DictReader((root/'Dataset/integrated/claims.csv').open()))
by_id={p['place_id']:p for p in places}
baseline=sorted({(c['subject_id'],by_id[c['object_id']]['heritage_parent_id'] or c['object_id'])
 for c in claims if c['relation']=='filming' and c['object_id'].startswith(('heritage:','heritage-component:'))})
if not (work/'baseline.json').exists():
 (work/'baseline.json').write_text(json.dumps(dict(pairs=baseline),indent=2)+'\n')
print(len(registry),len(evidence))
