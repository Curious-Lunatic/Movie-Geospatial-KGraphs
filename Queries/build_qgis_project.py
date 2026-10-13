#!/usr/bin/env python3
r"""Execute real QGIS joins and spatial analysis, then save a portable GIS project.

Run with QGIS's Python environment, not the ordinary system Python. On Windows:
  & 'C:\Program Files\QGIS 4.0.0\bin\python-qgis.bat' Queries/build_qgis_project.py

Inputs: the preceding build_integrated_graph.py outputs. All spatial processing
is performed by QGIS. No internet/basemap service or API key is required.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Dataset" / "integrated"
OUT = ROOT / "GIS"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (Qgis, QgsApplication, QgsCoordinateReferenceSystem,
    QgsFeature, QgsFillSymbol, QgsGeometry, QgsLayoutExporter, QgsLayoutItemLabel,
    QgsLayoutItemMap, QgsLayoutItemPage, QgsLayoutPoint, QgsLayoutSize,
    QgsLineSymbol, QgsMarkerSymbol, QgsPalLayerSettings, QgsPrintLayout,
    QgsProcessingFeedback, QgsProject, QgsRectangle, QgsReferencedRectangle,
    QgsRelation, QgsTextBufferSettings, QgsTextFormat, QgsVectorFileWriter,
    QgsVectorLayer, QgsVectorLayerSimpleLabeling, QgsBookmark)
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase


class Feedback(QgsProcessingFeedback):
    def __init__(self):
        super().__init__()
        self.warnings = []

    def reportError(self, error, fatalError=False):
        self.warnings.append(dict(message=error, fatal=fatalError))
        if fatalError:
            print("QGIS processing error:", error, flush=True)

    def pushWarning(self, warning):
        self.warnings.append(dict(message=warning, fatal=False))


def text_format(size=10, color="#172554", bold=False):
    fmt = QgsTextFormat()
    font = QFont("Arial")
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSize(size)
    fmt.setColor(QColor(color))
    return fmt


def labels(layer, expression, color="#172554", size=10):
    config = QgsPalLayerSettings()
    config.fieldName = expression
    config.isExpression = True
    config.dist = 3
    fmt = text_format(size, color)
    halo = QgsTextBufferSettings()
    halo.setEnabled(True)
    halo.setSize(0.8)
    halo.setColor(QColor("white"))
    fmt.setBuffer(halo)
    config.setFormat(fmt)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(config))
    layer.setLabelsEnabled(True)


def layout_label(layout, text, x, y, width, height, size=10, bold=False, color="#172554"):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    item.setTextFormat(text_format(size, color, bold))
    item.setMargin(0)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y))
    item.attemptResize(QgsLayoutSize(width, height))
    return item


def layout_map(layout, layers, crs, extent, x=10, y=38, width=181, height=148, grid_interval=None):
    item = QgsLayoutItemMap(layout)
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y))
    item.attemptResize(QgsLayoutSize(width, height))
    item.setCrs(crs)
    item.setLayers(layers)
    item.setKeepLayerSet(True)
    item.setFrameEnabled(True)
    item.zoomToExtent(extent)
    if grid_interval:
        grid = item.grid()
        grid.setEnabled(True)
        grid.setIntervalX(grid_interval)
        grid.setIntervalY(grid_interval)
        grid.setGridLineColor(QColor("#dbe3eb"))
        grid.setGridLineWidth(0.1)
    return item


def main():
    if not (DATA / "places.geojson").exists():
        raise SystemExit("Run Queries/build_integrated_graph.py first.")
    OUT.mkdir(exist_ok=True)
    app = QgsApplication([], False, str(ROOT / "outputs" / "qgis_profile"))
    app.initQgis()
    # Qt's offscreen platform on Windows does not automatically load system
    # fonts. Register installed Arial fonts explicitly for readable map exports.
    for filename in ("arial.ttf", "arialbd.ttf"):
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    sys.path.append(str(Path(QgsApplication.prefixPath()) / "python" / "plugins"))
    import processing
    from processing.core.Processing import Processing
    Processing.initialize()
    project = QgsProject.instance()
    project.clear()
    project.setTitle("Good Will Mapping: QGIS integration and 5 km heritage query")
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    project.setEllipsoid("WGS84")
    feedback, steps = Feedback(), []

    def load(path, name):
        layer = QgsVectorLayer(str(path), name, "ogr")
        if not layer.isValid():
            raise RuntimeError("QGIS cannot load " + str(path))
        return layer

    def run(algorithm, **params):
        print("QGIS:", algorithm, flush=True)
        params.setdefault("OUTPUT", "memory:")
        output = processing.run(algorithm, params, feedback=feedback)["OUTPUT"]
        if not isinstance(output, QgsVectorLayer) or not output.isValid():
            raise RuntimeError("Invalid QGIS output from " + algorithm)
        details = {k: v.name() if isinstance(v, QgsVectorLayer) else v.authid()
                   if isinstance(v, QgsCoordinateReferenceSystem) else v for k, v in params.items()}
        steps.append(dict(algorithm=algorithm, parameters=details, output_features=output.featureCount()))
        return output

    films = load(DATA / "films.csv", "Canonical movies")
    songs = load(DATA / "songs.csv", "Film-linked songs")
    people = load(DATA / "people.csv", "People and scoped music credits")
    characters = load(DATA / "characters.csv", "Film-specific character credits")
    genres = load(DATA / "genres.csv", "Genre identities")
    claims = load(DATA / "claims.csv", "Sourced relationship table")
    places = load(DATA / "places.geojson", "Place reference points (WGS84)")
    if places.crs().authid() != "EPSG:4326":
        raise RuntimeError("Expected longitude/latitude GeoJSON in EPSG:4326")
    supported_filming = run("native:extractbyexpression", INPUT=claims,
                            EXPRESSION='"relation" = \'filming\' AND "status" = \'source_supported\'')
    # Attribute join 1: every assertion gets the canonical movie title/year.
    film_claims = run("native:joinattributestable", INPUT=supported_filming, FIELD="subject_id",
        INPUT_2=films, FIELD_2="film_id", FIELDS_TO_COPY=["title", "release_year"],
        METHOD=1, DISCARD_NONMATCHING=True, PREFIX="film_")
    if film_claims.featureCount() != supported_filming.featureCount():
        raise RuntimeError("A filming assertion failed to join to its canonical movie")
    # Attribute join 2 is deliberately one-to-many: keep each source assertion.
    mapped_filming = run("native:joinattributestable", INPUT=places, FIELD="place_id",
        INPUT_2=film_claims, FIELD_2="object_id", FIELDS_TO_COPY=["claim_id", "subject_id", "relation",
        "film_title", "film_release_year", "source_file", "source_row", "source_url", "method", "status"],
        METHOD=0, DISCARD_NONMATCHING=True, PREFIX="")
    supported_narrative = run("native:extractbyexpression", INPUT=claims,
        EXPRESSION='"relation" = \'narrative\' AND "status" = \'source_supported\'')
    narrative_claims = run("native:joinattributestable", INPUT=supported_narrative, FIELD="subject_id",
        INPUT_2=films, FIELD_2="film_id", FIELDS_TO_COPY=["title", "release_year"],
        METHOD=1, DISCARD_NONMATCHING=True, PREFIX="film_")
    if narrative_claims.featureCount() != supported_narrative.featureCount():
        raise RuntimeError("A narrative assertion failed to join to its canonical movie")
    mapped_narrative = run("native:joinattributestable", INPUT=places, FIELD="place_id",
        INPUT_2=narrative_claims, FIELD_2="object_id", FIELDS_TO_COPY=["claim_id", "subject_id", "relation",
        "film_title", "film_release_year", "source_file", "source_row", "source_url", "method", "status"],
        METHOD=0, DISCARD_NONMATCHING=True, PREFIX="")
    cast_links = run("native:extractbyexpression", INPUT=claims, EXPRESSION='"relation" = \'cast_member\'')
    genre_links = run("native:extractbyexpression", INPUT=claims, EXPRESSION='"relation" = \'genre\'')
    properties = run("native:extractbyexpression", INPUT=places,
                     EXPRESSION='"place_id" LIKE \'heritage:%\'')
    components = run("native:extractbyexpression", INPUT=places,
                     EXPRESSION='"place_id" LIKE \'heritage-component:%\'')
    indian_properties = run("native:extractbyexpression", INPUT=properties,
                             EXPRESSION='regexp_match("country_codes", \'(^|[,;| ])IN($|[,;| ])\')')
    indian_components = run("native:extractbyexpression", INPUT=components,
                             EXPRESSION='regexp_match("country_codes", \'(^|[,;| ])IN($|[,;| ])\')')
    world_path = Path(QgsApplication.prefixPath()) / "resources/data/world_map.gpkg"
    world = load(world_path, "QGIS bundled context boundaries")
    india = run("native:extractbyexpression", INPUT=world, EXPRESSION='"iso_a2" = \'IN\'')
    india_filming = run("native:extractbylocation", INPUT=mapped_filming, PREDICATE=[0], INTERSECT=india)
    india_narrative = run("native:extractbylocation", INPUT=mapped_narrative, PREDICATE=[0], INTERSECT=india)

    # The Taj Mahal example is local to Agra: use UTM zone 44N and metre units.
    metric_crs = QgsCoordinateReferenceSystem("EPSG:32644")
    target = run("native:extractbyexpression", INPUT=places,
                 EXPRESSION='"place_id" = \'heritage:252\'')
    if target.featureCount() != 1:
        raise RuntimeError("Expected exactly one Taj Mahal reference point")
    target_m = run("native:reprojectlayer", INPUT=target, TARGET_CRS=metric_crs)
    # Local candidate window prevents projecting unrelated worldwide points into
    # this UTM zone. One degree around Agra comfortably contains the 5 km radius.
    local_sites = run("native:extractbyexpression", INPUT=mapped_filming,
        EXPRESSION='("place_id" LIKE \'heritage:%\' OR "place_id" LIKE \'heritage-component:%\') '
                   'AND x($geometry) BETWEEN 77 AND 79 AND y($geometry) BETWEEN 26 AND 28')
    local_sites_m = run("native:reprojectlayer", INPUT=local_sites, TARGET_CRS=metric_crs)
    buffer = run("native:buffer", INPUT=target_m, DISTANCE=5000, SEGMENTS=72,
                 END_CAP_STYLE=0, JOIN_STYLE=0, MITER_LIMIT=2, DISSOLVE=False)
    selected = run("native:extractbylocation", INPUT=local_sites_m, PREDICATE=[0], INTERSECT=buffer)
    # Spatial join: add the buffer's target attributes using geometry intersection.
    spatial_join = run("native:joinattributesbylocation", INPUT=selected, JOIN=buffer,
        PREDICATE=[0], JOIN_FIELDS=["place_name", "place_id"], METHOD=0,
        DISCARD_NONMATCHING=True, PREFIX="buffer_")
    measured = run("native:joinbynearest", INPUT=spatial_join, INPUT_2=target_m,
        FIELDS_TO_COPY=["place_name"], DISCARD_NONMATCHING=True, PREFIX="target_",
        NEIGHBORS=1, MAX_DISTANCE=5000)
    rows = []
    for feature in measured.getFeatures():
        distance = float(feature["distance"])
        if not 0 <= distance <= 5000:
            raise RuntimeError("Spatial join produced an out-of-radius point")
        rows.append(dict(title=feature["film_title"], release_year=feature["film_release_year"],
            place_id=feature["place_id"], place_name=feature["place_name"], target="Taj Mahal",
            distance_m=round(distance, 3), source_file=feature["source_file"], source_row=feature["source_row"],
            analysis_crs="EPSG:32644", interpretation="Projected distance between representative points"))
    if not rows or not any(r["title"] == "Jodhaa Akbar" and r["place_name"] == "Agra Fort" for r in rows):
        raise RuntimeError("Expected the sourced Jodhaa Akbar / Agra Fort result")
    # Independent comparison with the earlier spherical Python result.
    from query_integrated_graph import nearby
    reference = nearby(DATA, "Taj Mahal", 5, site_only=True)
    expected = {(r["title"], r["place_id"]) for r in reference}
    if {(r["title"], r["place_id"]) for r in rows} != expected:
        raise RuntimeError("QGIS and independent spatial query disagree on film/place pairs")
    for row in rows:
        baseline = next(r for r in reference if (r["title"], r["place_id"]) == (row["title"], row["place_id"]))
        if abs(row["distance_m"] - baseline["distance_km"]*1000) > 20:
            raise RuntimeError("Projected/spherical distance differs unexpectedly")

    # Save actual QGIS output layers, then use these persistent layers in the
    # project, avoiding temporary memory sources or installed-machine-only paths.
    gpkg = OUT / "good_will_mapping_1970_2025.gpkg"
    first = True
    def save(layer, table, name, group, visible=False):
        nonlocal first
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName, opts.layerName, opts.fileEncoding = "GPKG", table, "UTF-8"
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile if first else QgsVectorFileWriter.CreateOrOverwriteLayer
        result = QgsVectorFileWriter.writeAsVectorFormatV3(layer, str(gpkg), project.transformContext(), opts)
        if int(result[0]) != 0:
            raise RuntimeError("GeoPackage export failed: " + str(result))
        first = False
        saved = load(str(gpkg) + "|layername=" + table, name)
        if saved.featureCount() != layer.featureCount():
            raise RuntimeError("Saved layer count mismatch: " + table)
        project.addMapLayer(saved, False)
        group.addLayer(saved).setItemVisibilityChecked(visible)
        return saved

    root = project.layerTreeRoot()
    demo_group = root.addGroup("Agra: executed 5 km spatial query")
    india_group = root.addGroup("India: heritage and filming reference points")
    world_group = root.addGroup("Worldwide heritage and filming layers")
    table_group = root.addGroup("Linked cinema graph tables")
    films_saved = save(films, "movies", "Canonical movie table", table_group)
    songs_saved = save(songs, "songs", "Film-linked song table", table_group)
    people_saved = save(people, "people", "People and scoped music credits", table_group)
    characters_saved = save(characters, "characters", "Film-specific character credits", table_group)
    genres_saved = save(genres, "genres", "Genre table", table_group)
    cast_saved = save(cast_links, "cast_links", "Movie to cast evidence", table_group)
    genre_links_saved = save(genre_links, "genre_links", "Movie to genre evidence", table_group)
    claims_saved = save(film_claims, "filming_assertions", "Filming assertions with movie attributes", table_group)
    narrative_saved = save(narrative_claims, "narrative_assertions", "Narrative assertions with movie attributes", table_group)
    world_properties = save(properties, "heritage_properties", "Worldwide heritage property points", world_group)
    world_components = save(components, "heritage_components", "Worldwide heritage component points", world_group)
    all_filming = save(mapped_filming, "mapped_filming", "Filming assertions with geometry", world_group)
    all_narrative = save(mapped_narrative, "mapped_narrative", "Narrative settings with geometry", world_group)
    context = save(india, "india_context", "India context boundaries (QGIS bundled data)", india_group)
    india_props = save(indian_properties, "india_heritage", "Indian heritage property points", india_group)
    india_comps = save(indian_components, "india_components", "Indian heritage component points", india_group)
    india_movies = save(india_filming, "india_filming", "Filming reference points within India context", india_group)
    india_story = save(india_narrative, "india_narrative", "Narrative reference points within India context", india_group)
    target_saved = save(target_m, "taj_mahal", "Taj Mahal reference point", demo_group, True)
    buffer_saved = save(buffer, "taj_mahal_5km", "5 km buffer (UTM 44N)", demo_group, True)
    matches = save(measured, "nearby_movies", "Movie locations within the 5 km buffer", demo_group, True)
    lines = QgsVectorLayer("LineString?crs=EPSG:32644", "Reference-point distances", "memory")
    lines.dataProvider().addAttributes(measured.fields())
    lines.updateFields()
    destination = next(target_m.getFeatures()).geometry().asPoint()
    for feature in measured.getFeatures():
        line = QgsFeature(lines.fields())
        line.setAttributes(feature.attributes())
        line.setGeometry(QgsGeometry.fromPolylineXY([feature.geometry().asPoint(), destination]))
        lines.dataProvider().addFeatures([line])
    lines.updateExtents()
    lines_saved = save(lines, "distance_lines", "Distance between reference points", demo_group, True)

    for layer, color, size in [(target_saved,"#1d4ed8",4.5), (matches,"#d97706",4.5),
                              (india_props,"#1d4ed8",2.5), (india_comps,"#60a5fa",1.5),
                              (india_movies,"#d97706",1.8), (india_story,"#7e22ce",1.8)]:
        layer.renderer().setSymbol(QgsMarkerSymbol.createSimple(dict(name="circle", color=color,
            outline_color="#ffffff", outline_width="0.25", size=str(size))))
    buffer_saved.renderer().setSymbol(QgsFillSymbol.createSimple(dict(color="219,234,254,110",
        outline_color="#2563eb", outline_width="0.5", outline_style="dash")))
    context.renderer().setSymbol(QgsFillSymbol.createSimple(dict(color="#f1f5f9",
        outline_color="#94a3b8", outline_width="0.15")))
    lines_saved.renderer().setSymbol(QgsLineSymbol.createSimple(dict(line_color="#475569", line_width="0.55")))
    labels(target_saved, '"place_name"', "#1d4ed8", 11)
    labels(matches, '"place_name" || \'\\n\' || "film_title" || \' (\' || "film_release_year" || \')\'', "#92400e", 10)
    # QGIS relations expose the one-to-many links from movie records to songs
    # and filming assertions in the project's relation-aware attribute forms.
    relations = [
        ("movie_songs", "Movie to songs", songs_saved, "film_id", films_saved, "film_id"),
        ("movie_filming", "Movie to filming assertions", claims_saved, "subject_id", films_saved, "film_id"),
        ("movie_narrative", "Movie to narrative assertions", narrative_saved, "subject_id", films_saved, "film_id"),
        ("movie_characters", "Movie to credited roles", characters_saved, "film_id", films_saved, "film_id"),
        ("person_characters", "Performer to credited roles", characters_saved, "person_id", people_saved, "person_id"),
        ("movie_cast", "Movie to cast evidence", cast_saved, "subject_id", films_saved, "film_id"),
        ("person_cast", "Person to cast evidence", cast_saved, "object_id", people_saved, "person_id"),
        ("movie_genres", "Movie to genre evidence", genre_links_saved, "subject_id", films_saved, "film_id"),
        ("genre_movies", "Genre to movie evidence", genre_links_saved, "object_id", genres_saved, "genre_id")]
    for rid, name, child, field, parent, parent_field in relations:
        relation = QgsRelation()
        relation.setId(rid)
        relation.setName(name)
        relation.setReferencedLayer(parent.id())
        relation.setReferencingLayer(child.id())
        relation.addFieldPair(field, parent_field)
        if not relation.isValid():
            raise RuntimeError("Invalid QGIS table relation: " + name)
        project.relationManager().addRelation(relation)

    extent = QgsRectangle(buffer_saved.extent())
    extent.scale(1.18)
    project.setCrs(metric_crs)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent, metric_crs))
    for name, area, crs in [("Agra 5 km demo", extent, metric_crs),
                            ("India overview", QgsRectangle(67,6,99,38), QgsCoordinateReferenceSystem("EPSG:4326"))]:
        bookmark = QgsBookmark()
        bookmark.setName(name)
        bookmark.setGroup("Good Will Mapping")
        bookmark.setExtent(QgsReferencedRectangle(area, crs))
        project.bookmarkManager().addBookmark(bookmark)
    metric_distance = next(r["distance_m"] for r in rows if r["title"] == "Jodhaa Akbar")
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("Agra: 5 km buffer and spatial join")
    layout.pageCollection().pages()[0].setPageSize("A4", QgsLayoutItemPage.Landscape)
    layout_label(layout, "Good Will Mapping: QGIS spatial integration", 10,8,277,11,18,True)
    layout_label(layout, "Movie locations near the Taj Mahal: attribute joins, buffer and spatial join", 10,22,277,8,11)
    layout_map(layout, [matches,target_saved,lines_saved,buffer_saved], metric_crs, extent, grid_interval=2000)
    notes = ("Executed in QGIS " + Qgis.QGIS_VERSION + "\n\n"
             "1. Join claims to movie IDs\n2. Join records to place geometry\n"
             "3. Reproject to EPSG:32644\n4. Buffer the target by 5,000 m\n"
             "5. Intersect and spatially join\n6. Measure the nearest-point distance\n\n"
             "Result: Jodhaa Akbar (2008)\nFilming place: Agra Fort\n"
             "Distance: %.3f km\n\n" % (metric_distance/1000) +
             "Blue point: Taj Mahal\nOrange point: filming reference\n"
             "Blue dashed area: 5 km buffer\n\n"
             "Source: supplied Filmapia CSV,\nlogical record row 76.\n\n"
             "Distances refer to representative\npoints, not shooting positions.\n"
             "Grid spacing: 2,000 metres.")
    layout_label(layout, notes, 200,38,87,151,10)
    layout_label(layout, "CRS: WGS 84 / UTM zone 44N. Buffer and distance units: metres. Source geometry: supplied UNESCO reference points.",10,190,277,7,9)
    layout_label(layout, "Prepared for the 14 October 2026 mid evaluation. Native QGIS processing; no online basemap required.",10,198,277,6,9)
    project.layoutManager().addLayout(layout)
    overview = QgsPrintLayout(project)
    overview.initializeDefaults()
    overview.setName("India: heritage and film-location references")
    overview.pageCollection().pages()[0].setPageSize("A4", QgsLayoutItemPage.Landscape)
    layout_label(overview, "Good Will Mapping: India geographic overview",10,8,277,11,18,True)
    layout_label(overview, "Heritage points and filming references joined to canonical movie records",10,22,277,8,11)
    layout_map(overview,[india_movies,india_props,india_comps,context],QgsCoordinateReferenceSystem("EPSG:4326"),
               QgsRectangle(67,6,99,38))
    overview_text = ("Blue: heritage property points\nLight blue: serial components\n"
                     "Orange: film-location references\n\n"
                     "%d Indian property points\n%d component points\n%d sourced filming features\n\n" %
                     (india_props.featureCount(), india_comps.featureCount(),india_movies.featureCount()) +
                     "A location can carry several\nsource assertions and films.\nFeature counts are not unique\nmovie or shooting-spot counts.\n\n"
                     "The attribute joins preserve\nmovie IDs and source records.\nMissing-coordinate claims\nremain outside the map.\n\n"
                     "Context: QGIS bundled\nworld_map.gpkg boundaries.\nGeneralized display context.\n\n"
                     "CRS: WGS 84, EPSG:4326.\nDistance analysis is performed\nseparately in a metre-based CRS.")
    layout_label(overview,overview_text,200,38,87,151,10)
    layout_label(overview,"Source snapshots: team movie/location CSVs and UNESCO export. Heritage inscriptions included through 2025.",10,190,277,7,9)
    layout_label(overview,"Coordinates are representative points. Broad city/country references do not identify exact filming spots.",10,198,277,6,9)
    project.layoutManager().addLayout(overview)
    for name, page in [("agra_5km_map.png",layout),("india_overview.png",overview)]:
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = 160
        result = QgsLayoutExporter(page).exportToImage(str(OUT/name), settings)
        if int(result) != 0:
            raise RuntimeError("QGIS layout export failed: " + name)
    project_file = OUT / "Good_Will_Mapping_1970_2025.qgz"
    if not project.write(str(project_file)):
        raise RuntimeError("Could not save the QGIS project: " + project.error())
    project.clear()
    if not project.read(str(project_file)) or any(not layer.isValid() for layer in project.mapLayers().values()):
        raise RuntimeError("Saved QGIS project failed to reopen with valid layers")
    if len(project.relationManager().relations()) != len(relations) or len(project.layoutManager().layouts()) != 2:
        raise RuntimeError("Saved QGIS layouts/relations failed to round-trip")
    with (OUT/"qgis_nearby_movies.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report=dict(qgis_version=Qgis.QGIS_VERSION, attribute_joins_executed=4,
        project_file=project_file.name, geopackage_file=gpkg.name,
        year_range=json.loads((DATA / "summary.json").read_text(encoding="utf-8"))["year_range"],
        spatial_join_executed=True, metric_crs="EPSG:32644", buffer_metres=5000,
        geocoded_filming_assertions=mapped_filming.featureCount(),
        filming_claims_without_geometry=film_claims.featureCount()-mapped_filming.featureCount(),
        geocoded_narrative_assertions=mapped_narrative.featureCount(),
        narrative_claims_without_geometry=narrative_claims.featureCount()-mapped_narrative.featureCount(),
        indian_heritage_property_points=indian_properties.featureCount(),
        indian_heritage_component_points=indian_components.featureCount(),
        india_filming_features=india_filming.featureCount(), matched_features=len(rows), results=rows,
        india_narrative_features=india_narrative.featureCount(),
        project_reopened_with_valid_layers=True, portable_project_layers=len(project.mapLayers()),
        qgis_relations=len(relations), qgis_layouts=2, independent_python_pairs_agree=True,
        source_hashes={name:hashlib.sha256((DATA/name).read_bytes()).hexdigest()
                       for name in ["films.csv","claims.csv","songs.csv","places.geojson","people.csv","characters.csv","genres.csv"]},
        steps=steps,warnings=feedback.warnings)
    (OUT/"qgis_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ["steps","warnings","source_hashes"]},indent=2),flush=True)
    print("Saved QGIS project, GeoPackage, maps and processing report in",OUT,flush=True)
    project.clear()
    app.exitQgis()


if __name__ == "__main__":
    main()
