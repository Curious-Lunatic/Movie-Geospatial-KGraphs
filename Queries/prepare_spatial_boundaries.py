#!/usr/bin/env python3
"""Prepare versioned India boundaries and spatial joins for the web/QGIS explorer.
Requires Shapely. Downloads are optional; --cache can reuse downloaded source files.
"""
import argparse
import csv
import hashlib
import json
import unicodedata
import urllib.request
from pathlib import Path
from shapely import make_valid, set_precision
from shapely.geometry import shape, mapping, Point
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
REVISION = '9469f09'
OUT = ROOT / 'Queries/webmap/data'


def prepare(cache, download=False):
    cache.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for level in ('ADM1', 'ADM2'):
        path = cache / (level + '.geojson')
        meta = cache / (level + '-meta.json')
        if download or not path.exists():
            url = f'https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/{REVISION}/releaseData/gbOpen/IND/{level}/geoBoundaries-IND-{level}_simplified.geojson'
            urllib.request.urlretrieve(url, path)
        if not meta.exists():
            snapshot = OUT / 'boundary_sources.json'
            if snapshot.exists():
                meta.write_text(json.dumps(json.loads(snapshot.read_text())[level]))
            else:
                urllib.request.urlretrieve(f'https://www.geoboundaries.org/api/current/gbOpen/IND/{level}/', meta)
        metadata[level] = json.loads(meta.read_text())
        if REVISION not in metadata[level]['gjDownloadURL']:
            raise ValueError('Metadata revision does not match pinned geometry; update both together.')
        metadata[level]['download_revision'] = REVISION
        metadata[level]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    layers = {}
    for level in ('ADM1', 'ADM2'):
        layers[level] = []
        source = json.loads((cache / (level + '.geojson')).read_text())
        for feature in source['features']:
            g = set_precision(make_valid(shape(feature['geometry'])).simplify(.001, preserve_topology=True), .00001)
            if g.geom_type not in ('Polygon', 'MultiPolygon'):
                raise ValueError('Unexpected geometry: ' + g.geom_type)
            p = feature['properties']
            name = ''.join(c for c in unicodedata.normalize('NFKD', p['shapeName']) if not unicodedata.combining(c))
            props = dict(id=p['shapeID'], name=name, level=level, source_name=p['shapeName'], year=metadata[level]['boundaryYearRepresented'])
            layers[level].append(dict(type='Feature', geometry=mapping(g), properties=props))
    states = [shape(f['geometry']) for f in layers['ADM1']]
    tree = STRtree(states)
    for district in layers['ADM2']:
        g = shape(district['geometry'])
        overlaps = [(states[int(i)].intersection(g).area, int(i)) for i in tree.query(g)]
        if not overlaps or max(overlaps)[0] == 0:
            raise ValueError('District has no state overlap: ' + district['properties']['name'])
        parent = max(overlaps)[1]
        district['properties']['state_id'] = layers['ADM1'][parent]['properties']['id']
    features = layers['ADM1'] + layers['ADM2']
    geometries = [shape(f['geometry']) for f in features]
    index = STRtree(geometries)
    membership = {}
    with (ROOT / 'Dataset/integrated/places.csv').open() as stream:
        for row in csv.DictReader(stream):
            try:
                point = Point(float(row['longitude']), float(row['latitude']))
            except (ValueError, TypeError):
                continue
            ids = [features[int(i)]['properties']['id'] for i in index.query(point) if geometries[int(i)].covers(point)]
            if ids:
                membership[row['place_id']] = ids
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'india_regions.geojson').write_text(json.dumps(dict(type='FeatureCollection', features=features), separators=(',', ':')))
    (OUT / 'region_membership.json').write_text(json.dumps(membership, separators=(',', ':')))
    metadata['processing'] = 'Shapely make_valid; topology-preserving simplification 0.001 degrees; coordinate precision grid 0.00001 degrees; districts assigned by largest polygon overlap; point-in-polygon covers join on published output geometry.'
    metadata['counts'] = {k: len(v) for k, v in layers.items()}
    metadata['notice'] = 'Source metadata reports state year 2011 and district year 2021. Boundaries may not reflect current administrative divisions. These are research layers, not an authoritative boundary statement.'
    (OUT / 'boundary_sources.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(dict(counts=metadata['counts'], joined_places=len(membership), bytes=(OUT / 'india_regions.geojson').stat().st_size)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=ROOT / 'outputs/boundary-sources')
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    prepare(args.cache, args.download)
