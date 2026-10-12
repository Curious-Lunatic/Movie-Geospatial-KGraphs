"""Open reproducible QGIS GUI dialogs for the evaluation demonstration.

Run this file in QGIS's Python Console, then call one of the functions below.
It uses only QGIS application APIs. The saved portable project must be open.
"""
from pathlib import Path
import processing
from qgis.core import QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem

GUI_ROOT = Path(QgsProject.instance().fileName()).resolve().parent.parent


def show_buffer_dialog(root=GUI_ROOT):
    target = QgsProject.instance().mapLayersByName("Taj Mahal reference point")[0]
    dialog = processing.createAlgorithmDialog("native:buffer", {
        "INPUT": target, "DISTANCE": 5000, "SEGMENTS": 72,
        "END_CAP_STYLE": 0, "JOIN_STYLE": 0, "MITER_LIMIT": 2,
        "DISSOLVE": False,
        "OUTPUT": str(Path(root) / "GIS/buffer_from_gui.gpkg")})
    dialog.show()
    return dialog


def show_attribute_join_dialog(root=GUI_ROOT):
    project = QgsProject.instance()
    raw = QgsVectorLayer(str(Path(root) / "Dataset/integrated/claims.csv"),
                         "Supported filming assertions (raw CSV)", "ogr")
    if not raw.isValid() or not raw.setSubsetString("relation = 'filming' AND status = 'source_supported'"):
        raise RuntimeError("Cannot load/filter the original supported filming assertions")
    project.addMapLayer(raw)
    movies = project.mapLayersByName("Canonical movie table")[0]
    dialog = processing.createAlgorithmDialog("native:joinattributestable", {
        "INPUT": raw, "FIELD": "subject_id", "INPUT_2": movies, "FIELD_2": "film_id",
        "FIELDS_TO_COPY": ["title", "release_year"], "METHOD": 1,
        "DISCARD_NONMATCHING": True, "PREFIX": "film_",
        "OUTPUT": str(Path(root) / "GIS/attribute_join_from_gui.gpkg")})
    dialog.show()
    return dialog


def show_spatial_join_dialog(root=GUI_ROOT):
    project = QgsProject.instance()
    filming = project.mapLayersByName("Filming assertions with geometry")[0]
    candidates = processing.run("native:extractbyexpression", {
        "INPUT": filming,
        "EXPRESSION": "(\"place_id\" LIKE 'heritage:%' OR \"place_id\" LIKE 'heritage-component:%') "
                      "AND x($geometry) BETWEEN 77 AND 79 AND y($geometry) BETWEEN 26 AND 28",
        "OUTPUT": "memory:"})["OUTPUT"]
    metric_output = processing.run("native:reprojectlayer", {
        "INPUT": candidates, "TARGET_CRS": QgsCoordinateReferenceSystem("EPSG:32644"),
        "OUTPUT": str(Path(root) / "GIS/agra_candidates_from_gui.gpkg")})["OUTPUT"]
    metric = QgsVectorLayer(str(metric_output), "Agra filming-site candidates (UTM 44N)", "ogr")
    if not metric.isValid():
        raise RuntimeError("Cannot load the reprojected Agra candidate layer")
    project.addMapLayer(metric)
    buffer = project.mapLayersByName("5 km buffer (UTM 44N)")[0]
    dialog = processing.createAlgorithmDialog("native:joinattributesbylocation", {
        "INPUT": metric, "JOIN": buffer, "PREDICATE": [0],
        "JOIN_FIELDS": ["place_name", "place_id"], "METHOD": 0,
        "DISCARD_NONMATCHING": True, "PREFIX": "buffer_",
        "OUTPUT": str(Path(root) / "GIS/spatial_join_from_gui.gpkg")})
    dialog.show()
    return dialog
