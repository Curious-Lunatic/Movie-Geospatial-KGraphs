#!/usr/bin/env python3
"""Parse the direct RDF graph and sampled provenance, and reconcile queries.

Requires rdflib. This is not a SHACL validation; use the optional existing
validate_integrated_graph.py for full provenance/SHACL validation. Every
provenance statement is counted; every thousandth record is syntax-checked.
"""
import collections
import csv
import json
import hashlib
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
from validate_graph_queries import validate_queries
query_checks = validate_queries(g, OUT)
report = dict(full_rdf_syntax_parsed=False, direct_graph_syntax_parsed=True,
              query_projection_and_sample_triples=len(g), provenance_statements=statements,
              provenance_records_sampled=len(sample_subjects),
              entity_counts_match=True, rdf_csv_query_results_match=True,
              query_result_rows=query_checks['query_result_rows'], shacl_executed=False,
              graph_sha256=hashlib.sha256((OUT/'graph.ttl').read_bytes()).hexdigest(),
              query_sha256={name:hashlib.sha256((ROOT/'Queries/knowledge_graph_queries'/(name+'.sparql')).read_bytes()).hexdigest()
                            for name in ('romance','heritage','characters')})
(OUT / 'graph_verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
