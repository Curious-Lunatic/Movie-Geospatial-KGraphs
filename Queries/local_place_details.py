"""Local settlement context for the demo; selected heritage identity stays separate."""
from functools import lru_cache
import json,math
from pathlib import Path


@lru_cache(maxsize=1)
def cities():
    return json.loads((Path(__file__).parent/'place_tools/cities.json').read_text(encoding='utf-8'))


def lookup(query,records=None):
    def value(key,minimum,maximum):
        try: result=float(query.get(key,[''])[0])
        except (TypeError,ValueError): raise ValueError('Invalid '+key)
        if not math.isfinite(result) or not minimum<=result<=maximum: raise ValueError('Invalid '+key)
        return result
    action=query.get('action',[''])[0]
    if action not in ['profile','nearby','articles']: raise ValueError('Unknown place operation')
    lat=value('lat',-90,90);lon=value('lng',-180,180)
    radius=value('radius',1,10)
    if radius not in [1,5,10]: raise ValueError('Invalid radius')
    category=query.get('category',['towns'])[0]
    if category not in ['towns','landmarks','water','terrain','areas']: raise ValueError('Invalid category')
    if action=='articles' or (action=='nearby' and category!='towns'):
        return 503,dict(error='Live articles and landmark lookups require the hosted service. The selected site identity and recorded film links remain available locally.')
    limit=30 if action=='profile' else radius;items=[]
    for uid,name,y,x,country,population,zone in records if records is not None else cities():
        if abs(y-lat)>limit/110: continue
        r=math.pi/180
        h=math.sin((y-lat)*r/2)**2+math.cos(lat*r)*math.cos(y*r)*math.sin((x-lon)*r/2)**2
        km=12742*math.asin(math.sqrt(min(1,h)))
        if km<=limit: items.append(dict(id=uid,name=name,lat=y,lng=x,region=country,population=population,timezone=zone,kind='Settlement context',distanceKm=km,url='https://www.geonames.org/'+str(uid)))
    items.sort(key=lambda i:i['distanceKm'])
    return 200,dict(version=1,action=action,source='Bundled GeoNames settlement index; not the selected heritage identity',items=items[:1 if action=='profile' else 12])
