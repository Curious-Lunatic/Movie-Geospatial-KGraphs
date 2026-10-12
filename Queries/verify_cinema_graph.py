#!/usr/bin/env python3
"""Parse the direct RDF graph and sampled provenance, and reconcile queries.

Requires rdflib. This is not a SHACL validation; use the optional existing
validate_integrated_graph.py for full provenance/SHACL validation. Every
provenance statement is counted; every thousandth record is syntax-checked.
"""
import collections
import csv
import json
from pathlib import Path
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Dataset' / 'integrated'
GWM = Namespace('https://w3id.org/gwm/')


def read(name):
    return list(csv.DictReader((OUT / name).open(encoding='utf-8', newline='')))


print('Parsing direct RDF graph and a provenance sample...', flush=True)
lines, statements, sample_subjects = [], 0, set()
with (OUT / 'graph.ttl').open(encoding='utf-8') as stream:
    for line in stream:
        if '/entity/claim%3A' in line.split(' ', 1)[0]:
            if ' a rdf:Statement ; ' in line:
                statements += 1
                if statements % 1000 == 0:
                    sample_subjects.add(line.split(' ', 1)[0])
            if line.split(' ', 1)[0] in sample_subjects:
                lines.append(line)
        else:
            lines.append(line)
g = Graph().parse(data=''.join(lines), format='turtle')
del lines
print('RDF projection parsed; executing and reconciling queries...', flush=True)
summary = json.loads((OUT / 'summary.json').read_text())
for kind, metric in [('Film', 'films'), ('Song', 'songs'), ('Person', 'people'),
                     ('Character', 'characters'), ('Genre', 'genres'), ('HeritageSite', 'heritage_properties')]:
    assert len(set(g.subjects(RDF.type, GWM[kind]))) == summary[metric], kind
assert statements == summary['claims']
results = {}
for name in ('romance', 'heritage', 'characters'):
    print('Executing ' + name + ' query...', flush=True)
    query = (ROOT / 'Queries' / 'knowledge_graph_queries' / (name + '.sparql')).read_text()
    results[name] = [dict((str(k), str(v)) for k, v in row.asdict().items()) for row in g.query(query)]
    assert results[name], 'No demonstration results for ' + name
romance_csv = collections.Counter((r['place'], 'filmedAt' if r['relation'] == 'filming' else 'setIn', r['film_count']) for r in read('romance_places.csv'))
romance_rdf = collections.Counter((r['place'], r['relation'].split('/')[-1], r['filmCount']) for r in results['romance'])
assert romance_csv == romance_rdf, 'RDF and CSV romance query disagree'
expected = {r['heritage_site']: (r['film_count'], r['genre_count'], frozenset(r['genres'].split('|')))
            for r in read('heritage_genres.csv') if int(r['genre_count']) > 1}
actual = {r['site']: (r['filmCount'], r['genreCount'], frozenset(r['genres'].split(' | '))) for r in results['heritage']}
assert expected == actual, 'RDF and CSV heritage query disagree'
report = dict(full_rdf_syntax_parsed=False, direct_graph_syntax_parsed=True,
              query_projection_and_sample_triples=len(g), provenance_statements=statements,
              provenance_records_sampled=len(sample_subjects),
              entity_counts_match=True, rdf_csv_query_results_match=True,
              query_result_rows={k: len(v) for k, v in results.items()}, shacl_executed=False)
(OUT / 'graph_verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
