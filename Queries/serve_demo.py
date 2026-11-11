#!/usr/bin/env python3
"""Serve only the generated cinema demo on the local machine."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Choose a port between 1 and 65535.')
    directory = ROOT / 'Dataset' / 'integrated'
    for name in ['graph_explorer.html', 'india_regions.geojson', 'region_membership.json']:
        if not (directory / name).is_file():
            parser.error('Build the data and explorer first: python Queries/build_integrated_graph.py, then python Queries/build_graph_explorer.py')
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as error:
        parser.error(f'Cannot open the local demo port: {error}. Try --port 8768.')
    print(f'Cinema chat demo: http://127.0.0.1:{args.port}/graph_explorer.html#chat', flush=True)
    print('Local machine only. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
