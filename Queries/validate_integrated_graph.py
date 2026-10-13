#!/usr/bin/env python3
"""Validate the RDF projection with SHACL and execute the provenance SPARQL demo.

Optional dependencies: pip install -r Queries/requirements-integration.txt
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "Dataset" / "integrated")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF
    from pyshacl import validate
    directory = args.data_dir
    print("Parsing RDF graph...", flush=True)
    graph = Graph().parse(directory / "graph.ttl", format="turtle")
    print("Checking graph constraints...", flush=True)
    shapes = Graph().parse(ROOT / "Queries" / "integration_shapes.ttl", format="turtle")
    conforms, _, report_text = validate(graph, shacl_graph=shapes,
                                       inference="none", allow_warnings=False)
    if not conforms:
        raise SystemExit(report_text)
    gwm = Namespace("https://w3id.org/gwm/")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    for type_name, expected in [("Film", summary["films"]), ("Song", summary["songs"]),
                                ("Person", summary["people"]), ("HeritageSite", summary["heritage_properties"]),
                                ("HeritageComponent", summary["heritage_components"]),
                                ("Character", summary["characters"]), ("Genre", summary["genres"])]:
        actual = len(set(graph.subjects(RDF.type, gwm[type_name])))
        if actual != expected:
            raise SystemExit("RDF/CSV count disagreement: " + type_name)
    statements = len(set(graph.subjects(RDF.type, RDF.Statement)))
    if statements != summary["claims"]:
        raise SystemExit("RDF/CSV claim count disagreement")
    query = (ROOT / "Queries" / "integration_examples.sparql").read_text(encoding="utf-8")
    rows = [{str(k): str(v) for k, v in row.asdict().items()} for row in graph.query(query)]
    if not rows:
        raise SystemExit("Expected real-data SPARQL demonstration returned no rows")
    with (directory / "sparql_demo.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["title", "year", "place", "source", "sourceRow"])
        writer.writeheader()
        writer.writerows(rows)
    result = dict(shacl_conforms=bool(conforms), rdf_triples=len(graph), rdf_statements=statements,
                  sparql_demo_rows=len(rows), counts_match_csv=True,
                  graph_sha256=hashlib.sha256((directory / "graph.ttl").read_bytes()).hexdigest(),
                  geosparql_distance_executed=False)
    from validate_graph_queries import validate_queries
    result.update(validate_queries(graph, directory))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
