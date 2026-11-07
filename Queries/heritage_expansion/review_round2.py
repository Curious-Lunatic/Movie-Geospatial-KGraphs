"""Reproduce the manually reviewed November 7 additions; never fuzzy-match film titles."""
import csv,json
from pathlib import Path
W=Path(__file__).resolve().parent
D=W.parents[1]/'Dataset/integrated'
def read(p):return list(csv.DictReader(p.open()))
places=read(D/'places.csv');films=read(D/'films.csv');sites=read(W/'sites.csv')
def place(name):
 hits=[p for p in places if p['place_name']==name];assert len(hits)==1,name
 return hits[0]['place_id']
def source(key):return json.loads((W/'sources'/f'{key}.json').read_text())
if not (W/'round2_baseline.json').exists():
 claims=read(D/'claims.csv');ps={p['place_id']:p for p in places}
 pairs=sorted({(c['subject_id'],ps[c['object_id']]['heritage_parent_id'] or c['object_id']) for c in claims if c['relation']=='filming' and (ps[c['object_id']].get('heritage_kind') or c['object_id'].startswith(('heritage:','heritage-component:')))})
 (W/'round2_baseline.json').write_text(json.dumps(dict(pairs=pairs,geocoded_places=[p['place_id'] for p in places if p['latitude']]),indent=2))
entries=[
 ('Bandra Fort','bandra','A Portuguese coastal fort at Bandra’s Land’s End in Mumbai, built in 1640 to watch over Mahim Bay.'),
 ('Golden Temple','golden','The Harmandir Sahib gurdwara in Amritsar is a major Sikh sacred site, with a sanctuary surrounded by the Amrit Sarovar.'),
 ('Ramnagar Fort Palace','ramnagar','A sandstone fort and royal residence on the eastern bank of the Ganges at Varanasi, built in 1750.'),
 ('Hotel Fernhill Palace','fernhill','A former summer residence of the Mysore royal family in Ooty, originating as an 1851 bungalow and later used as a heritage hotel.'),
 ('City Palace, Jaipur','city_jaipur','The Jaipur royal palace complex was developed under Sawai Jai Singh II in the eighteenth century and includes courtyards, galleries and a museum.'),
 ('Afghan Church','afghan','The Church of St John the Evangelist in Colaba, Mumbai, was built in the nineteenth century as a memorial to the First Afghan War.'),
 ('Devigarh Fort Palace','devigarh','An eighteenth-century palace at Delwara near Udaipur, formerly the residence of its rulers and subsequently adapted as a heritage hotel.'),
 ('Thirumalai Nayak Palace','thirumalai','A seventeenth-century palace in Madurai associated with King Thirumalai Nayak, with a surviving courtyard and monumental arcades.'),
 ('Lalgarh Palace','lalgarh','A palace complex in Bikaner built for Maharaja Ganga Singh in the early twentieth century. Laxmi Niwas Palace forms part of the complex.'),
 ('Pari Mahal','pari','A terraced Mughal garden on the Zabarwan hills overlooking Srinagar and Dal Lake, associated with Dara Shikoh.'),
 ('Gloria Church','gloria','A Gothic Revival church in Byculla, Mumbai. The present building opened in 1913, replacing an earlier church in Mazagaon.'),
 ('Bidar Fort','bidar','A fortified complex in Bidar, Karnataka, developed as a Bahmani capital in the fifteenth century and containing numerous historic monuments.'),
 ('Hadimba Temple','hadimba','A temple dedicated to Hidimba in Manali’s cedar forest, with the present structure dating to 1553.'),
 ('Martand Sun Temple','martand','The remains of an eighth-century temple dedicated to Surya near Mattan in the Kashmir Valley.'),
 ('Fort Aguada','aguada','A Portuguese-era coastal fort in Goa built in 1612, with a later lighthouse overlooking the Arabian Sea.'),
 ('Umaid Bhawan Palace','umaid','A twentieth-century palace in Jodhpur, built between 1929 and 1943 and now containing a royal residence, museum and hotel.')]
details=json.loads((W/'place_details.json').read_text()) if (W/'place_details.json').exists() else {}
for name,key,description in entries:
 s=source(key);pid=place(name);lat,lon=[v.strip() for v in s['geo'].split(';')]
 row=dict(place_id=pid,place_name=name,latitude=lat,longitude=lon,heritage_source=s['url'],coordinate_source=s['url'],source_snapshot=key+'.json',heritage_parent_id='',canonical_id='',heritage_kind='historic_landmark')
 if not any(r['place_id']==pid for r in sites):sites.append(row)
 details[pid]=dict(description=description,source_url=s['url'])
# Same-site spelling variants, not extra heritage sites.
alias='place:1412324ec6c0f9bad864f32e';canonical=place('City Palace, Jaipur')
if not any(r['place_id']==alias for r in sites):
 sites.append(dict(place_id=alias,place_name='Jaipur City Palace',latitude='',longitude='',heritage_source=source('city_jaipur')['url'],coordinate_source='',source_snapshot='city_jaipur.json',heritage_parent_id='',canonical_id=canonical,heritage_kind='same_site_alias'))
# Named component: keep its own point unresolved rather than inventing a courtyard position.
pid=place('Laxmi Niwas Palace Hotel')
if not any(r['place_id']==pid for r in sites):
 sites.append(dict(place_id=pid,place_name='Laxmi Niwas Palace Hotel',latitude='',longitude='',heritage_source=source('lalgarh')['url'],coordinate_source='',source_snapshot='lalgarh.json',heritage_parent_id=place('Lalgarh Palace'),canonical_id='',heritage_kind='historic_component'))
s=source('vijay_district');lat,lon=[v.strip() for v in s['geo'].split(';')]
for row in sites:
 if row['place_name']=='Vijay Vilas Palace':row.update(latitude=lat,longitude=lon,coordinate_source=s['url'])
claims=json.loads((W/'reviewed_claims.json').read_text())
reviews=[
 ('Q370313','Bandra Fort','bandra_official','Dil Chahta Hai','Official tourism page lists the film as filmed at Bandra Fort.'),
 ('Q2622347','Bandra Fort','bandra_official','Wanted','Official tourism page lists Wanted among films shot at Bandra Fort; joined to the 2009 film.'),
 ('Q1262452','Bandra Fort','bandra_official','Jane Tu Ya Jane Na','Official tourism page lists the film among Bandra Fort shoots.'),
 ('Q10975672','Bandra Fort','bandra_official','Buddha Mil Gaya','Official tourism page lists the film among Bandra Fort shoots.'),
 ('Q944949','Ramnagar Fort Palace','ramnagar','The film titled Banaras is one of the popular movies shot here.','Site article identifies Banaras as filmed at Ramnagar Fort.'),
 ('Q542698','Devigarh Fort Palace','devigarh','was set and extensively shot at Devigarh.','Site article describes Eklavya as extensively filmed at Devigarh.'),
 ('Q3090065','Bidar Fort','bidar','The Dirty Picture was shot in the Bidar Fort.','Site article locates the Ishq Sufiyaana song sequence at Bidar Fort.'),
 ('Q3633996','Pari Mahal','pari','including the Bollywood movie Lamhaa','Site article identifies Lamhaa among productions filmed at Pari Mahal.')]
for qid,name,key,token,evidence in reviews:
 hits=[f for f in films if f['wikidata_id']==qid];assert len(hits)==1,qid
 f=hits[0];s=source(key);assert token in s['text'],(key,token)
 record=dict(film_id=f['film_id'],title=f['title'],wikidata_id=qid,place_id=place(name),source_url=s['url'],source_snapshot=key+'.json',verify_text=token,evidence=evidence,retrieved_at=s['retrieved_at'])
 if not any(c['film_id']==record['film_id'] and c['place_id']==record['place_id'] and c['source_url']==record['source_url'] for c in claims):claims.append(record)
with (W/'sites.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=sites[0]);writer.writeheader();writer.writerows(sites)
(W/'reviewed_claims.json').write_text(json.dumps(claims,ensure_ascii=False,indent=2)+'\n')
(W/'place_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n')
print(len(entries),'reviewed sites;',len(reviews),'source assertions')
