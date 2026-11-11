#!/usr/bin/env python3
"""Open an actual chat/map GeoJSON export as two portable QGIS layers.

Run with QGIS's Python interpreter. This verifies import and geometry; it does
not claim a second execution of the web buffer inside QGIS.
"""
import argparse
import json
from pathlib import Path


def main():
    from qgis.core import (Qgis, QgsApplication, QgsCoordinateReferenceSystem,
                           QgsProject, QgsReferencedRectangle, QgsVectorLayer)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'GIS/chat_demo')
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding='utf-8'))
    areas = [f for f in payload['features'] if f['properties'].get('role') == 'search_area']
    points = [f for f in payload['features'] if f['properties'].get('role') == 'movie_location']
    if not areas or not points:
        raise ValueError('The exported query must include a search area and at least one movie-location point.')
    assert all(f['geometry']['type'] in ['Polygon', 'MultiPolygon'] for f in areas)
    assert all(f['geometry']['type'] == 'Point' for f in points)
    args.output.mkdir(parents=True, exist_ok=True)
    app = QgsApplication([], False)
    app.initQgis()
    project = QgsProject.instance()
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    project.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    counts = {}
    for name, features, label in [('search_area', areas, 'Chat query: search area'),
                                   ('movie_locations', points, 'Recorded film-location results')]:
        path = args.output / (name + '.geojson')
        path.write_text(json.dumps(dict(type='FeatureCollection', features=features), ensure_ascii=False), encoding='utf-8')
        layer = QgsVectorLayer(str(path), label, 'ogr')
        assert layer.isValid(), name
        assert layer.crs().authid() == 'EPSG:4326', layer.crs().authid()
        assert layer.featureCount() == len(features)
        assert all(f.geometry().isGeosValid() for f in layer.getFeatures())
        if name == 'search_area':
            layer.renderer().symbol().setOpacity(.2)
        project.addMapLayer(layer)
        counts[name] = layer.featureCount()
    project.setTitle('Cinema atlas: exported heritage chat query')
    project.setFileName(str(args.output / 'Chat_Query_Demo.qgz'))
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(project.mapLayersByName('Chat query: search area')[0].extent(), project.crs()))
    assert project.write()
    reopened = QgsProject()
    assert reopened.read(project.fileName())
    assert len(reopened.mapLayers()) == 2 and all(l.isValid() for l in reopened.mapLayers().values())
    report = dict(qgis_version=Qgis.QGIS_VERSION, input_file=args.input.name,
                  layers=counts, layer_crs='EPSG:4326', relative_paths=True,
                  reopened_with_valid_layers=True, all_geometries_valid=True,
                  native_qgis_buffer_reexecuted=False,
                  method='Imported actual web chat export; split polygon and point roles for QGIS. Web radius uses spherical reference-point distances.')
    (args.output / 'validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    # Release project-owned providers before shutting down the QGIS runtime.
    reopened.clear()
    project.clear()
    del layer, reopened
    app.exitQgis()


if __name__ == '__main__':
    main()
