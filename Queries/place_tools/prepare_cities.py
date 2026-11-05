"""Build the compact settlement index from the official GeoNames cities15000.zip."""
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

with zipfile.ZipFile(sys.argv[1]) as archive, archive.open("cities15000.txt") as raw:
    rows = [[int(r[0]), r[1], float(r[4]), float(r[5]), r[8], int(r[14] or 0), r[17]]
            for r in csv.reader(io.TextIOWrapper(raw, encoding='utf8'), delimiter='\t', quoting=csv.QUOTE_NONE)]
Path(__file__).with_name('cities.json').write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
print(f'{len(rows)} settlements')
