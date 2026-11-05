"""Fetch the reviewed heritage pages and retain text, coordinates and source hashes."""
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DIRECTORY = Path(__file__).resolve().parent
PAGES = {
    'madh': 'https://en.wikipedia.org/wiki/Madh_Fort',
    'mehrangarh': 'https://en.wikipedia.org/wiki/Mehrangarh',
    'nahargarh': 'https://en.wikipedia.org/wiki/Nahargarh_Fort',
    'chapora': 'https://goa-tourism.com/fort/chapora-fort/',
    'chapora_coordinates': 'https://en.wikipedia.org/wiki/Chapora_Fort',
    'tughlaqabad': 'https://en.wikipedia.org/wiki/Tughlaqabad_Fort',
    'pataudi': 'https://en.wikipedia.org/wiki/Pataudi_Palace',
    'prag': 'https://en.wikipedia.org/wiki/Prag_Mahal',
    'vijay': 'https://en.wikipedia.org/wiki/Vijay_Vilas_Palace',
    'gwalior': 'https://en.wikipedia.org/wiki/Gwalior_Fort',
    'junagarh': 'https://en.wikipedia.org/wiki/Junagarh_Fort',
    'jaigarh': 'https://en.wikipedia.org/wiki/Jaigarh_Fort',
    'naggar': 'https://en.wikipedia.org/wiki/Naggar_Castle',
    'chand': 'https://en.wikipedia.org/wiki/Chand_Baori',
    'vijay_official': 'https://gujarattourism.com/kutch-zone/kutch/vijay-vilas-palace.html',
    'pataudi_official': 'https://www.incredibleindia.gov.in/en/haryana/gurugram/pataudi-palace',
    'golconda': 'https://en.wikipedia.org/wiki/Golconda',
    'bagore': 'https://en.wikipedia.org/wiki/Bagore-ki-Haveli',
    'roopangarh': 'https://en.wikipedia.org/wiki/Roopangarh_Fort',
    'rajasthan_films': 'https://www.tourism.rajasthan.gov.in/film-tourism.html',
}
def fetch(item):
    name, url = item
    output = DIRECTORY / 'sources' / (name + '.json')
    if output.exists():
        return name, 'cached'
    response = requests.get(url, timeout=45, headers={'User-Agent': 'PlacesAndStories heritage research/1.0'})
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    geo = soup.select_one('.geo')
    main = soup.select_one('#mw-content-text') or soup
    for element in main.select('script,style,nav,footer'):
        element.decompose()
    text = main.get_text(' ', strip=True)
    if len(text) < 400:
        raise ValueError('Page too short: ' + name)
    data = dict(url=url, retrieved_at=datetime.now(timezone.utc).isoformat(),
                response_sha256=hashlib.sha256(response.content).hexdigest(),
                geo=geo.get_text(' ', strip=True) if geo else '',
                text=text)
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return name, data['geo']
if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for future in concurrent.futures.as_completed([pool.submit(fetch, item) for item in PAGES.items()]):
            try:
                print(future.result(), flush=True)
            except Exception as error:
                print(type(error).__name__, str(error), flush=True)
