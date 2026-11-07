"""Retain the official district tourism direction point, not a shooting position."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup
url='https://kachchh.nic.in/tourist-place/vijay-vilas-palace/'
r=requests.get(url,timeout=30);r.raise_for_status();s=BeautifulSoup(r.content,'html.parser')
a=next(a for a in s.select('a[href]') if a.get_text(strip=True)=='Direction' and '/maps/dir//' in a['href'])
lat,lon=map(float,a['href'].split('/maps/dir//')[1].split(','))
out=dict(url=url,retrieved_at=datetime.now(timezone.utc).isoformat(),response_sha256=hashlib.sha256(r.content).hexdigest(),geo=f'{lat}; {lon}',direction_url=a['href'],text=s.get_text(' ',strip=True))
Path(__file__).with_name('sources').joinpath('vijay_district.json').write_text(json.dumps(out,indent=2))
print(out['geo'])
