#!/usr/bin/env python3
"""Build a standalone graph explorer (online posters) and reproducible query results."""
import argparse
import collections
import csv
import json
import math
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(directory, name):
    with (directory / name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def load_posters(path):
    """Join cached TMDB artwork by identifier, never by a guessed title match."""
    posters = {}
    if path.exists():
        with path.open(encoding='utf-8') as source:
            for line in source:
                if not line.strip():
                    continue
                movie = json.loads(line)
                poster = movie.get('poster_path')
                if movie.get('id') and isinstance(poster, str) and re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)', poster):
                    posters[str(movie['id'])] = 'https://image.tmdb.org/t/p/w500' + poster
    return posters


def build(directory, poster_source=ROOT / 'Queries' / 'tmdb_details.jsonl'):
    posters = load_posters(poster_source)
    nodes, index = [], {}
    tables = [('films.csv', 'film_id', 'title', 'Film'), ('songs.csv', 'song_id', 'title', 'Song'),
              ('people.csv', 'person_id', 'name', 'Person'), ('characters.csv', 'character_id', 'name', 'Character'),
              ('genres.csv', 'genre_id', 'name', 'Genre'), ('places.csv', 'place_id', 'place_name', 'Place')]
    for file, id_col, label_col, kind in tables:
        for row in read(directory, file):
            nid = row[id_col]
            actual = 'Heritage' if nid.startswith(('heritage:', 'heritage-component:')) else kind
            index[nid] = len(nodes)
            nodes.append([nid, row[label_col], actual, row.get('release_year', ''),
                          row.get('coordinate_scope', '') or row.get('identity_scope', ''),
                          posters.get(row.get('tmdb_id', ''), '') if kind == 'Film' else ''])
    claims = read(directory, 'claims.csv')
    edges, edge_index = [], {}
    for c in claims:
        signature = (c['subject_id'], c['relation'], c['object_id'])
        if signature not in edge_index:
            edge_index[signature] = len(edges)
            edges.append([index[c['subject_id']], c['relation'], index[c['object_id']], 0,
                          c['source_file'] + ':' + c['source_row'], c['source_url'], c['evidence'][:400]])
        edges[edge_index[signature]][3] += 1
    places = {p['place_id']: p for p in read(directory, 'places.csv')}
    geo = []
    for pid, p in places.items():
        try:
            lat, lon = float(p['latitude']), float(p['longitude'])
        except (ValueError, TypeError):
            continue
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            geo.append([index[pid], lat, lon, p['coordinate_scope'], p['country_names'], p['coordinate_source']])
    # One feature per movie-linked place for QGIS, avoiding repeated evidence counts.
    location_films = collections.defaultdict(set)
    for e in edges:
        if e[1] in ('filming', 'narrative') and nodes[e[0]][2] == 'Film':
            location_films[e[2]].add((e[0], e[1]))
    features = []
    for node, lat, lon, scope, country, source in geo:
        linked = location_films[node]
        if not linked:
            continue
        features.append(dict(type='Feature', geometry=dict(type='Point', coordinates=[lon, lat]),
                             properties=dict(place_id=nodes[node][0], place_name=nodes[node][1],
                                             coordinate_scope=scope, coordinate_source=source, country=country,
                                             film_count=len({f for f, _ in linked}),
                                             filming_movie_count=len({f for f, r in linked if r == 'filming'}),
                                             story_movie_count=len({f for f, r in linked if r == 'narrative'}),
                                             movies=' | '.join(sorted({nodes[f][1] + ' (' + nodes[f][3] + ')' for f, _ in linked})))))
    (directory / 'spatial_locations.geojson').write_text(
        json.dumps(dict(type='FeatureCollection', features=features), ensure_ascii=False), encoding='utf-8')
    for pid, p in places.items():
        if p['heritage_parent_id']:
            edges.append([index[pid], 'part_of_heritage', index[p['heritage_parent_id']], 1,
                          'whc001.csv (component metadata)', p['coordinate_source'], 'UNESCO component/property membership'])
    genres = collections.defaultdict(set)
    for e in edges:
        if e[1] == 'genre':
            genres[e[0]].add(nodes[e[2]][1])
    romance = collections.defaultdict(set)
    heritage = collections.defaultdict(lambda: {'films': set(), 'genres': set()})
    for e in edges:
        if e[1] not in ('filming', 'narrative'):
            continue
        if 'Romance' in genres[e[0]]:
            romance[(e[2], e[1])].add(e[0])
        if e[1] == 'filming' and nodes[e[2]][2] == 'Heritage':
            target = places[nodes[e[2]][0]]['heritage_parent_id'] or nodes[e[2]][0]
            heritage[target]['films'].add(e[0])
            heritage[target]['genres'].update(genres[e[0]])
    romance_rows = [dict(place_id=nodes[p][0], place=nodes[p][1], relation=r, film_count=len(fs))
                    for (p, r), fs in sorted(romance.items(), key=lambda item: (-len(item[1]), nodes[item[0][0]][1], item[0][1]))]
    heritage_rows = [dict(place_id=p, heritage_site=places[p]['place_name'], film_count=len(v['films']),
                         genre_count=len(v['genres']), genres='|'.join(sorted(v['genres'])))
                     for p, v in sorted(heritage.items(), key=lambda item: (-len(item[1]['genres']), item[0]))]
    for name, rows, fields in [('romance_places.csv', romance_rows, ['place_id', 'place', 'relation', 'film_count']),
                              ('heritage_genres.csv', heritage_rows, ['place_id', 'heritage_site', 'film_count', 'genre_count', 'genres'])]:
        with (directory / name).open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    summary = json.loads((directory / 'summary.json').read_text())
    payload = json.dumps(dict(nodes=nodes, edges=edges, summary={k: v for k, v in summary.items() if k != 'sources'},
                              romance=romance_rows[:30], heritage=heritage_rows, geo=geo), ensure_ascii=False, separators=(',', ':'))
    # Escaping '<' prevents source strings from ending the embedded script tag.
    payload = payload.replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = (ROOT / 'Queries' / 'graph_explorer.html').read_text(encoding='utf-8')
    webmap = ROOT / 'Queries' / 'webmap'
    template = template.replace('/*__WEBMAP_CSS__*/',
                                (webmap / 'vendor' / 'leaflet.css').read_text() + '\n' + (webmap / 'map.css').read_text())
    template = template.replace('<!--__WEBMAP_PANEL__-->', (webmap / 'map_panel.html').read_text())
    for name in ('india_regions.geojson', 'region_membership.json', 'boundary_sources.json'):
        shutil.copyfile(webmap / 'data' / name, directory / name)
    scripts = '\n'.join((webmap / file).read_text() for file in ('vendor/leaflet.js', 'vendor/turf.min.js', 'spatial_tools.js', 'spatial_engine.js', 'spatial_ui.js'))
    template = template.replace('<!--__WEBMAP_SCRIPTS__-->', '<script>\n' + scripts + '\n</script>')
    (directory / 'graph_explorer.html').write_text(template.replace('/*__GRAPH_DATA__*/', payload), encoding='utf-8')
    print(json.dumps(dict(nodes=len(nodes), edges=len(edges), films_with_posters=sum(bool(n[5]) for n in nodes), romance_query_rows=len(romance_rows),
                          linked_heritage_properties=len(heritage_rows), output=str(directory / 'graph_explorer.html')), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'Dataset' / 'integrated')
    parser.add_argument('--poster-source', type=Path, default=ROOT / 'Queries' / 'tmdb_details.jsonl',
                        help='Cached TMDB details; missing file leaves usable title-card fallbacks.')
    args = parser.parse_args()
    build(args.data_dir, args.poster_source)
