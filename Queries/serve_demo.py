#!/usr/bin/env python3
"""Serve only the generated cinema demo on the local machine."""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from gemini_chat import chat as gemini_chat
from local_place_details import lookup
from atlas_api import handle_get,handle_post

ROOT = Path(__file__).resolve().parents[1]


class DemoHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        url=urlsplit(self.path)
        if handle_get(self,url.path,parse_qs(url.query)):return
        if url.path=='/' and (ROOT/'Dataset/integrated/atlas.html').exists():
            self.send_response(302);self.send_header('Location','/atlas.html');self.end_headers();return
        if url.path!='/api/places':
            return super().do_GET()
        try:
            status,body=lookup(parse_qs(url.query))
        except ValueError as error:
            status,body=400,dict(error=str(error))
        raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        url=urlsplit(self.path)
        if url.path!='/api/chat':
            self.send_error(404,'Not found')
            return
        try:
            length=int(self.headers.get('Content-Length') or 0)
            if length<=0 or length>1024*1024:
                raise ValueError('Invalid request size')
            payload=json.loads(self.rfile.read(length).decode('utf-8'))
            status,body=gemini_chat(payload)
        except ValueError as error:
            status,body=400,dict(error=str(error))
        except Exception as error:
            status,body=500,dict(error=str(error))
        raw=json.dumps(body,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)

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
    handler = partial(DemoHandler, directory=str(directory))
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as error:
        parser.error(f'Cannot open the local demo port: {error}. Try --port 8768.')
    print(f'Cinema atlas: http://127.0.0.1:{args.port}/atlas.html', flush=True)
    print('Local machine only. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
