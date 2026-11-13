"""Execute native QGIS regional counts and representative-point kernel density.

Run with the installed QGIS Python environment. Does not modify the earlier
Good_Will_Mapping project. All outputs use relative, portable layer paths.
"""
import collections,csv,gzip,hashlib,json,os,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'GIS/analysis';DATA=ROOT/'Dataset/integrated'

def main():
    from qgis.core import (Qgis,QgsApplication,QgsProject,QgsVectorLayer,QgsSpatialIndex,
        QgsGeometry,QgsPointXY,QgsCoordinateReferenceSystem,QgsRectangle,QgsReferencedRectangle,
        QgsRasterLayer,QgsSingleBandPseudoColorRenderer,QgsRasterShader,QgsColorRampShader,
        QgsFillSymbol,QgsMarkerSymbol,QgsPrintLayout,QgsLayoutItemPage,QgsLayoutItemLabel,
        QgsLayoutItemMap,QgsLayoutPoint,QgsLayoutSize,QgsLayoutExporter,QgsTextFormat)
    from qgis.PyQt.QtGui import QColor,QFont,QFontDatabase
    app=QgsApplication([],False);app.initQgis()
    for font in ['arial.ttf','arialbd.ttf']:
        path=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/font
        if path.exists():QFontDatabase.addApplicationFont(str(path))
    sys.path.insert(0,str(Path(QgsApplication.pkgDataPath())/'python/plugins'))
    import processing
    from processing.core.Processing import Processing
    Processing.initialize();OUT.mkdir(parents=True,exist_ok=True)
    def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    boundaries=ROOT/'Queries/webmap/data/india_regions.geojson'
    fixed=processing.run('native:fixgeometries',dict(INPUT=str(boundaries),OUTPUT='memory:'))['OUTPUT']
    regions=list(fixed.getFeatures());index=QgsSpatialIndex(fixed.getFeatures());by_id={r.id():r for r in regions}
    all_places=json.loads(gzip.decompress((DATA/'atlas-data/places.json.gz').read_bytes()))
    song_by_place=collections.defaultdict(set)
    with (DATA/'song_locations.csv').open(encoding='utf-8-sig',newline='') as stream:
        for r in csv.DictReader(stream):song_by_place[r['place_id']].add(r['song_id'])
    assigned={};points=[];film_rows=[];songs=[];broad=[]
    def point(p,props):return dict(type='Feature',geometry=dict(type='Point',coordinates=[p['lon'],p['lat']]),properties=props)
    for p in all_places:
        if not p['films'] and p['id'] not in song_by_place:continue
        geometry=QgsGeometry.fromPointXY(QgsPointXY(p['lon'],p['lat']))
        matches=[by_id[i] for i in index.intersects(geometry.boundingBox()) if by_id[i].geometry().intersects(geometry)]
        if not matches:continue
        assigned[p['id']]=[r['id'] for r in matches]
        if p['films']:
            points.append(point(p,dict(place_id=p['id'],name=p['name'],precision=p['precision'],film_count=len(p['films']))))
            for fid in p['films']:film_rows.append(point(p,dict(film_id=fid,place_id=p['id'])))
            if p['precision'] not in ('site_reference','route_reference'):broad.append(point(p,dict(place_id=p['id'])))
        for sid in song_by_place[p['id']]:songs.append(point(p,dict(song_id=sid,place_id=p['id'])))
    def layer(name,features):
        path=OUT/(name+'.geojson');dump(path,dict(type='FeatureCollection',features=features));v=QgsVectorLayer(str(path),name,'ogr');assert v.isValid();return v
    places=layer('reference_points',points);film_links=layer('film_place_links',film_rows);song_links=layer('song_place_links',songs);broad_points=layer('broad_references',broad)
    result=fixed
    operations=[('place_count',places,None),('film_count',film_links,'film_id'),('song_count',song_links,'song_id'),('broad_count',broad_points,None)]
    for field,source,unique in operations:
        result=processing.run('native:countpointsinpolygon',dict(POLYGONS=result,POINTS=source,CLASSFIELD=unique,FIELD=field,OUTPUT='memory:'))['OUTPUT']
    # Independently reconcile native results against distinct-ID intersections.
    expected=collections.defaultdict(lambda:dict(places=set(),films=set(),songs=set(),broad=set()))
    for p in all_places:
        for rid in assigned.get(p['id'],[]):
            v=expected[rid]
            if p['films']:
                v['places'].add(p['id']);v['films'].update(p['films'])
                if p['precision'] not in ('site_reference','route_reference'):v['broad'].add(p['id'])
            v['songs'].update(song_by_place[p['id']])
    counts=[]
    for r in result.getFeatures():
        row=dict(id=r['id'],name=r['name'],level=r['level'],boundary_year=str(r['year']),**{f:int(r[f]) for f,_,_ in operations})
        for f,key in [('place_count','places'),('film_count','films'),('song_count','songs'),('broad_count','broad')]:assert row[f]==len(expected[row['id']][key]),(row['name'],f,row[f],len(expected[row['id']][key]))
        counts.append(row)
    counts.sort(key=lambda r:(r['level'],-r['film_count'],r['name']));dump(OUT/'regional_counts.json',counts)
    with (OUT/'regional_counts.csv').open('w',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(counts[0]));w.writeheader();w.writerows(counts)
    vector=OUT/'regional_counts.gpkg'
    if vector.exists():vector.unlink()
    saved=processing.run('native:savefeatures',dict(INPUT=result,OUTPUT=str(vector)))['OUTPUT'];regional=QgsVectorLayer(saved,'Regional reference counts','ogr');assert regional.isValid()
    projected=QgsCoordinateReferenceSystem();assert projected.createFromProj('+proj=aeqd +lat_0=22 +lon_0=79 +datum=WGS84 +units=m +no_defs')
    projected_points=processing.run('native:reprojectlayer',dict(INPUT=places,TARGET_CRS=projected,OUTPUT='memory:'))['OUTPUT']
    raster=OUT/'filming_reference_density.tif'
    processing.run('qgis:heatmapkerneldensityestimation',dict(INPUT=projected_points,RADIUS=100000,PIXEL_SIZE=5000,WEIGHT_FIELD=None,KERNEL=0,OUTPUT_VALUE=0,OUTPUT=str(raster)))
    density=QgsRasterLayer(str(raster),'Filming reference density · 100 km quartic kernel');assert density.isValid()
    stats=density.dataProvider().bandStatistics(1);maximum=stats.maximumValue
    ramp=QgsColorRampShader();ramp.setColorRampType(QgsColorRampShader.Interpolated)
    ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(maximum*f,QColor(c),str(round(maximum*f,2))) for f,c in [(0,'#fffdf8'),(.1,'#dfe9cc'),(.35,'#8db89a'),(.65,'#3a8b76'),(1,'#184b42')]])
    shader=QgsRasterShader();shader.setRasterShaderFunction(ramp);density.setRenderer(QgsSingleBandPseudoColorRenderer(density.dataProvider(),1,shader))
    regional.renderer().setSymbol(QgsFillSymbol.createSimple(dict(color='255,255,255,0',outline_color='#5e7165',outline_width='.15')))
    places.renderer().setSymbol(QgsMarkerSymbol.createSimple(dict(name='circle',color='#b66d25',outline_color='white',size='1.5',outline_width='.15')))
    project=QgsProject.instance();project.setFilePathStorage(Qgis.FilePathType.Relative);project.setCrs(projected);project.setTitle('Cinema atlas · regional counts and reference-point density')
    for v in [density,regional,places]:project.addMapLayer(v)
    extent=QgsRectangle(density.extent());extent.scale(1.05);project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent,projected))
    layout=QgsPrintLayout(project);layout.initializeDefaults();layout.pageCollection().pages()[0].setPageSize('A4',QgsLayoutItemPage.Landscape)
    def text(content,x,y,w,h,size=11):
        label=QgsLayoutItemLabel(layout);label.setText(content);fmt=QgsTextFormat();fmt.setFont(QFont('Arial'));fmt.setSize(size);fmt.setColor(QColor('#193731'));label.setTextFormat(fmt);layout.addLayoutItem(label);label.attemptMove(QgsLayoutPoint(x,y));label.attemptResize(QgsLayoutSize(w,h))
    text('Cinema atlas: geography of recorded filming references',10,7,280,12,17)
    text('Native QGIS kernel density and regional counts · unique reference places, not filming events',10,21,280,10,10)
    map_item=QgsLayoutItemMap(layout);layout.addLayoutItem(map_item);map_item.attemptMove(QgsLayoutPoint(10,36));map_item.attemptResize(QgsLayoutSize(185,150));map_item.setCrs(projected);map_item.setLayers([places,regional,density]);map_item.setKeepLayerSet(True);map_item.zoomToExtent(extent)
    text(f'{len(points)} unique filming-reference points\n{len(film_rows)} distinct film/place links\n{len(songs)} song/place references\n{len(counts)} state/district polygons\n\nGreen: point-density kernel\nOrange: source reference points\n\nKernel radius: 100,000 metres\nPixel size: 5,000 metres\nQuartic kernel; equal place weights\n\nCRS: WGS 84 / custom AEQD\nCentred at 22° N, 79° E\nDistances distort away from centre.\n\nADM1 boundaries: 2011\nADM2 boundaries: 2021\nNo location means a coverage gap.',201,38,87,145,10)
    text('City and regional points can create artificial clusters. This exploratory density does not identify shooting addresses or production intensity.',10,191,280,10,8)
    export=QgsLayoutExporter(layout);assert export.exportToImage(str(OUT/'filming_reference_density.png'),QgsLayoutExporter.ImageExportSettings())==QgsLayoutExporter.Success
    project.layoutManager().addLayout(layout);project.setFileName(str(OUT/'Regional_Analysis.qgz'));assert project.write()
    reopened=QgsProject();assert reopened.read(project.fileName());assert all(v.isValid() for v in reopened.mapLayers().values())
    report=dict(qgis_version=Qgis.QGIS_VERSION,algorithms=['native:fixgeometries','native:countpointsinpolygon','native:reprojectlayer','qgis:heatmapkerneldensityestimation'],unique_filming_points=len(points),distinct_film_place_links=len(film_rows),song_place_references=len(songs),regions=len(counts),native_counts_reconciled=True,project_reopened=True,relative_paths=True,radius_metres=100000,pixel_metres=5000,kernel='quartic',weights='one per unique place',crs_proj=projected.toProj(),boundary_sha256=hashlib.sha256(boundaries.read_bytes()).hexdigest(),limitations=['Reference point density, not filming event counts.','City/region reference points can create artificial clusters.','Custom AEQD is metre based; distance distortion varies away from its centre.','Historic administrative boundaries retain source dates.'])
    dump(OUT/'validation.json',report);print(json.dumps(report,indent=2),flush=True)
    reopened.clear();project.clear();return app

if __name__=='__main__':
    runtime=main()
    import gc
    gc.collect();runtime.exitQgis()
