"""Reconcile the presentation's aggregate queries with the complete RDF graph."""
import collections
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_queries(graph, directory):
    directory = Path(directory)
    results = {}
    for name in ('romance', 'heritage', 'characters'):
        print('Executing and reconciling ' + name + ' query...', flush=True)
        query = (ROOT / 'Queries/knowledge_graph_queries' / (name + '.sparql')).read_text(encoding='utf-8')
        results[name] = [{str(k): str(v) for k, v in row.asdict().items()} for row in graph.query(query)]
        if not results[name]:
            raise ValueError('Empty demonstration query: ' + name)
    def read(name):
        with (directory / name).open(encoding='utf-8', newline='') as stream:
            return list(csv.DictReader(stream))
    expected = collections.Counter((r['place'], 'filmedAt' if r['relation'] == 'filming' else 'setIn', r['film_count'])
                                   for r in read('romance_places.csv'))
    actual = collections.Counter((r['place'], r['relation'].split('/')[-1], r['filmCount']) for r in results['romance'])
    if expected != actual:
        raise ValueError('Romance counts differ between RDF and CSV')
    expected = {r['heritage_site']: (r['film_count'], r['genre_count'], frozenset(r['genres'].split('|')))
                for r in read('heritage_genres.csv') if int(r['genre_count']) > 1}
    actual = {r['site']: (r['filmCount'], r['genreCount'], frozenset(r['genres'].split(' | '))) for r in results['heritage']}
    if expected != actual:
        raise ValueError('Heritage counts differ between RDF and CSV')
    return {'rdf_csv_query_results_match': True,
            'query_result_rows': {name: len(rows) for name, rows in results.items()}}
