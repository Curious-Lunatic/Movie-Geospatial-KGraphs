#!/usr/bin/env python3
"""Prepare only the public explorer and its downloads for Vercel."""
import gzip
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Dataset' / 'integrated'
OUTPUT = ROOT / 'outputs' / 'vercel-site'


def prepare():
    subprocess.run([sys.executable, str(ROOT / 'Queries' / 'build_graph_explorer.py')], check=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    html = (SOURCE / 'graph_explorer.html').read_text(encoding='utf-8')
    # Keep the first page small and serve its large graph script precompressed.
    # Vercel's response header below makes browsers decompress it transparently.
    start = html.index('const DATA=') + len('const DATA=')
    end = html.index(';\nif(!DATA', start)
    script = ('const GRAPH_DATA=' + html[start:end] + ';\n').encode('utf-8')
    (OUTPUT / 'graph-data.js').write_bytes(gzip.compress(script, mtime=0))
    html = html[:start] + 'GRAPH_DATA' + html[end:]
    html = html.replace('<script>\n(()=>{\nconst toggle=',
                        '<script src="graph-data.js"></script>\n<script>\n(()=>{\nconst toggle=', 1)
    for name in ('graph.ttl', 'claims.csv'):
        with (SOURCE / name).open('rb') as source, (OUTPUT / (name + '.gz')).open('wb') as target:
            with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as compressed:
                shutil.copyfileobj(source, compressed)
        html = html.replace('href="' + name + '"', 'href="' + name + '.gz"')
    html = html.replace('Download RDF knowledge graph</a>', 'Download RDF knowledge graph (.gz)</a>')
    html = html.replace('Relationship evidence</a>', 'Relationship evidence (.csv.gz)</a>')
    (OUTPUT / 'index.html').write_text(html, encoding='utf-8')
    for name in ('romance_places.csv', 'heritage_genres.csv', 'summary.json', 'spatial_locations.geojson', 'india_regions.geojson', 'region_membership.json', 'boundary_sources.json'):
        shutil.copyfile(SOURCE / name, OUTPUT / name)
    # The region layer is fetched only when the Regions tool is opened.
    boundary = OUTPUT / 'india_regions.geojson'
    boundary.write_bytes(gzip.compress(boundary.read_bytes(), mtime=0))
    api = OUTPUT / 'api'
    api.mkdir(exist_ok=True)
    for filename in ('places.js', 'cities.json'):
        shutil.copyfile(ROOT / 'Queries' / 'place_tools' / filename, api / filename)
    config = {
        'framework': None,
        'buildCommand': '',
        'installCommand': '',
        'outputDirectory': '.',
        'headers': [{
            'source': '/graph-data.js',
            'headers': [
                {'key': 'Content-Encoding', 'value': 'gzip'},
                {'key': 'Content-Type', 'value': 'application/javascript; charset=utf-8'},
            ],
        }, {
            'source': '/india_regions.geojson',
            'headers': [
                {'key': 'Content-Encoding', 'value': 'gzip'},
                {'key': 'Content-Type', 'value': 'application/geo+json; charset=utf-8'},
            ],
        }, {
            'source': '/(.*)',
            'headers': [
                {'key': 'X-Content-Type-Options', 'value': 'nosniff'},
                {'key': 'Referrer-Policy', 'value': 'strict-origin-when-cross-origin'},
            ],
        }],
    }
    (OUTPUT / 'vercel.json').write_text(json.dumps(config, indent=2) + '\n')
    files = [p for p in OUTPUT.iterdir() if p.is_file()]
    size = sum(p.stat().st_size for p in files)
    if size > 100_000_000:
        raise ValueError('Public deployment exceeds the Vercel Hobby 100 MB upload limit.')
    print(f'Prepared {len(files)} public files ({size / 1_000_000:.1f} MB) in {OUTPUT}')


if __name__ == '__main__':
    prepare()
