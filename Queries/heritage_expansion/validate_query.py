"""Reconcile the heritage aggregate against the relevant triples in the actual RDF export."""
import csv
import hashlib
import json
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'Dataset/integrated'


def validate():
    graph_file = DIRECTORY / 'graph.ttl'
    lines = []
    predicates = {'gwm:filmedAt', 'gwm:hasGenre', 'gwm:partOfHeritage'}
    with graph_file.open() as stream:
        for line in stream:
            words = line.split(' ', 2)
            if (line.startswith('@prefix') or 'rdfs:subClassOf' in line
                    or ' a gwm:Heritage' in line or ' a gwm:Genre ' in line
                    or (len(words) > 1 and words[1] in predicates)):
                lines.append(line)
    graph = Graph().parse(data=''.join(lines), format='turtle')
    query = (ROOT / 'Queries/knowledge_graph_queries/heritage.sparql').read_text()
    actual = {str(row.site): (int(row.filmCount), int(row.genreCount),
                              frozenset(str(row.genres).split(' | '))) for row in graph.query(query)}
    with (DIRECTORY / 'heritage_genres.csv').open() as stream:
        expected = {row['heritage_site']: (int(row['film_count']), int(row['genre_count']),
                                          frozenset(row['genres'].split('|')))
                    for row in csv.DictReader(stream) if int(row['genre_count']) > 1}
    if actual != expected:
        raise ValueError('RDF heritage query disagrees with the website table')
    result = dict(heritage_rdf_csv_match=True, matched_rows=len(actual),
                  relevant_rdf_triples=len(graph),
                  graph_sha256=hashlib.sha256(graph_file.read_bytes()).hexdigest(),
                  scope='Heritage aggregate reconciliation on projected actual RDF triples')
    Path(__file__).with_name('validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    validate()
