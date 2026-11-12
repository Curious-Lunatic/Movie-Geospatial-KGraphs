# Chat query exported to QGIS

Open `Chat_Query_Demo.qgz`, keeping both GeoJSON files beside it. The layers are
the actual search polygon and movie-location point exported by the browser's
Taj Mahal 5 km query followed by “Only heritage”. Both use EPSG:4326.

`validation.json` records QGIS engine import, valid geometry, relative paths and
successful reopening. This import does not rerun a native QGIS buffer or distance
calculation. The web result uses spherical reference-point distance; the original
projected QGIS benchmark is separately preserved in `GIS/qgis_report.json`.

To reproduce from a new browser export, use the installed QGIS Python interpreter:

```sh
python-qgis.bat Queries/prepare_chat_qgis_demo.py --input path/to/export.geojson
```
