#!/usr/bin/env python3
"""Cache public site-first heritage sources; retain timestamps and hashes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import time
from urllib.request import Request, urlopen

WORK = Path(__file__).resolve().parent / 'heritage_enrichment'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--only', help='Fetch only this snapshot filename')
    args = parser.parse_args()
    for source in json.loads((WORK / 'sources.json').read_text()):
        if args.only and source['file'] != args.only:
            continue
        path = WORK / 'snapshots' / source['file']
        if path.exists():
            continue
        if not args.fetch:
            raise RuntimeError('Missing snapshot: ' + source['url'])
        try:
            def timed_out(signum, frame):
                raise TimeoutError('Total download time limit reached')
            signal.signal(signal.SIGALRM, timed_out)
            signal.alarm(180 if path.suffix == '.pdf' else 90)
            with urlopen(Request(source['url'], headers={'User-Agent': 'MovieGeospatialResearch/1.0'}), timeout=50) as response:
                body = response.read()
                final_url = response.url
            signal.alarm(0)
            path.write_bytes(body)
            path.with_suffix(path.suffix + '.json').write_text(json.dumps(dict(
                url=source['url'], final_url=final_url,
                retrieved_at=datetime.now(timezone.utc).isoformat(),
                sha256=hashlib.sha256(body).hexdigest()), indent=2) + '\n')
            print(source['file'], len(body), flush=True)
            time.sleep(0.5)
        except Exception as exc:
            signal.alarm(0)
            print('FAILED', source['url'], str(exc), flush=True)


if __name__ == '__main__':
    main()
