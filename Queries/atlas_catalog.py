"""Indexed, read-only catalogue and reproducible public assets for the new atlas."""
import collections,contextlib,csv,gzip,hashlib,itertools,json,math,os,re,sqlite3,uuid
from pathlib import Path
from build_integrated_graph import norm,key

ROOT=Path(__file__).resolve().parents[1]
REL_LABELS={'filming':'filmed at','narrative':'story set in','song_filming':'song filmed at','in_film':'song in film','genre':'has genre','cast_member':'cast member','director':'directed by','character_in_film':'character in film','portrays':'portrays','part_of_heritage':'part of heritage','performed_by':'performed by','composed_by':'composed by','lyrics_by':'lyrics by'}


def rows(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
def packed(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode();path.write_bytes(gzip.compress(raw,mtime=0));return dict(bytes=len(raw),compressed_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
def json_file(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def distance(a,b):
    r=math.pi/180;h=math.sin((b[0]-a[0])*r/2)**2+math.cos(a[0]*r)*math.cos(b[0]*r)*math.sin((b[1]-a[1])*r/2)**2
    return 12742*math.asin(math.sqrt(min(1,h)))
def source_grade(method):
    return 'reviewed_source_statement' if 'reviewed' in method else 'structured_source_assertion' if 'wikidata' in method or 'tmdb' in method else 'supplied_source_record'


def build(directory=ROOT/'Dataset/integrated'):
    directory=Path(directory);public=directory/'atlas-data';public.mkdir(exist_ok=True)
    nodes={};idfields={'Film':('films.csv','film_id','title'),'Song':('songs.csv','song_id','title'),'Person':('people.csv','person_id','name'),'Character':('characters.csv','character_id','name'),'Genre':('genres.csv','genre_id','name'),'Place':('places.csv','place_id','place_name')}
    for kind,(filename,identity,label) in idfields.items():
        for row in rows(directory/filename):
            item=dict(id=row[identity],kind='Heritage' if kind=='Place' and (row[identity].startswith(('heritage:','heritage-component:')) or row.get('heritage_kind')) else kind,label=row[label],year=int(row['release_year']) if kind=='Film' else None,attributes=row)
            nodes[item['id']]=item
    for item in nodes.values():
        item['aliases']=json.loads(item['attributes'].get('aliases') or '[]') if item['kind'] in ('Place','Heritage') else []
    for alias in rows(directory/'entity_aliases.csv'):
        if alias['canonical_id'] in nodes:nodes[alias['canonical_id']]['aliases'].append(alias['alias_label'])
    films={n['attributes'].get('tmdb_id'):n for n in nodes.values() if n['kind']=='Film' and n['attributes'].get('tmdb_id')}
    cached=ROOT/'Queries/tmdb_details.jsonl'
    if cached.exists():
        with cached.open(encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():continue
                movie=json.loads(line);n=films.get(str(movie.get('id','')))
                if not n:continue
                n['attributes']['original_language']=movie.get('original_language','')
                poster=movie.get('poster_path','')
                if isinstance(poster,str) and re.fullmatch(r'/[A-Za-z0-9_-]+\.(?:jpg|png|webp)',poster):n['poster']='https://image.tmdb.org/t/p/w185'+poster
    listed_hindi={r['film_id'] for r in rows(directory/'film_attributes.csv') if r['field']=='language' and norm(r['value'])=='hindi'}
    rules_path=ROOT/'Queries/curation/rules.json';rules=json.loads(rules_path.read_text(encoding='utf-8')) if rules_path.exists() else {};scope_rules={r['wikidata_id']:r for r in rules.get('film_scope_reviews',[])}
    for n in nodes.values():
        if n['kind']!='Film':continue
        a=n['attributes'];a['scope_status']='metadata_hindi' if a.get('original_language')=='hi' else 'source_listed_hindi' if n['id'] in listed_hindi else 'scope_unverified'
        a['scope_note']='Hindi-language metadata in the supplied TMDB cache.' if a['scope_status']=='metadata_hindi' else 'Listed as Hindi in the supplied source; original production language is not independently established.' if a['scope_status']=='source_listed_hindi' else 'Included in the team film list; production-language metadata is missing.'
        if a.get('wikidata_id') in scope_rules:
            r=scope_rules[a['wikidata_id']];a.update(scope_status=r['status'],recorded_languages=' / '.join(r['languages']),scope_source=r['source_url'],scope_note=r['note'])
        n['scope_status']=a['scope_status']
    edges={};assertions=rows(directory/'claims.csv');adj=collections.defaultdict(list)
    for c in assertions:
        eid=key('edge',c['subject_id'],c['relation'],c['object_id'])
        if eid not in edges:
            edges[eid]=dict(id=eid,subject=c['subject_id'],relation=c['relation'],object=c['object_id'],label=REL_LABELS.get(c['relation'],c['relation']),assertions=[],confidence='source_record',precision=c.get('location_precision') or nodes.get(c['object_id'],{}).get('attributes',{}).get('location_precision','unknown_reference'))
            adj[c['subject_id']].append(eid);adj[c['object_id']].append(eid)
        evidence={k:c.get(k,'') for k in ['claim_id','source_file','source_row','source_url','evidence','method','status','revision_id','retrieved_at','location_precision','scene_start_seconds','scene_end_seconds','scene_evidence_url','coordinate_uncertainty_m','camera_position_verified','scene_latitude','scene_longitude','coordinate_source','reviewed_at','original_subject_id','original_object_id']};evidence['source_grade']=source_grade(c.get('method',''));edges[eid]['assertions'].append(evidence)
    for index,p in enumerate(rows(directory/'places.csv'),2):
        parent=p.get('heritage_parent_id')
        if not parent or parent not in nodes:continue
        subject=p['place_id'];eid=key('edge',subject,'part_of_heritage',parent)
        if eid in edges:continue
        edges[eid]=dict(id=eid,subject=subject,relation='part_of_heritage',object=parent,label='part of heritage',confidence='source_record',precision='not_applicable',assertions=[dict(source_file='places.csv',source_row=str(index),source_url=p.get('heritage_source') or p.get('coordinate_source',''),method='retained_heritage_parent_metadata',source_grade='structured_source_assertion',evidence='Documented parent membership retained in the place identity registry; this is not inferred from proximity.')])
        adj[subject].append(eid);adj[parent].append(eid)
    for e in edges.values():
        e['assertion_count']=len(e['assertions']);e['distinct_source_records']=len({(a['source_file'],a['source_url']) for a in e['assertions']});e['confidence']='reviewed_source_statement' if any(a['source_grade']=='reviewed_source_statement' for a in e['assertions']) else 'multiple_recorded_sources' if e['distinct_source_records']>1 else 'source_record'
    # Geometry and film-only links stay small enough to fetch when the map is opened.
    geo=[];place_films=collections.defaultdict(set);film_places=collections.defaultdict(set);filming_films=set();year_places=collections.defaultdict(set);year_films=collections.defaultdict(set)
    for e in edges.values():
        if e['relation']=='filming':
            place_films[e['object']].add(e['subject']);film_places[e['subject']].add(e['object']);filming_films.add(e['subject'])
            year=nodes[e['subject']]['year'];year_places[year].add(e['object']);year_films[year].add(e['subject'])
    for n in nodes.values():
        a=n['attributes']
        if n['kind'] not in ('Place','Heritage') or a.get('latitude','')=='':continue
        geo.append(dict(id=n['id'],name=n['label'],lat=float(a['latitude']),lon=float(a['longitude']),kind=a.get('place_type','unknown'),precision=a.get('location_precision','unknown_reference'),country=a.get('country_names',''),locality=a.get('locality',''),aliases=json.loads(a.get('aliases') or '[]'),films=sorted(place_films[n['id']]),source=a.get('identity_source') or a.get('coordinate_source',''),coordinate_source=a.get('coordinate_source',''),quality_flags=a.get('quality_flags',''),heritage=n['kind']=='Heritage',parent_id=a.get('heritage_parent_id','')))
    summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'));quality=json.loads((directory/'place_quality.json').read_text(encoding='utf-8'))
    source_counts=collections.Counter(a['source_file'] for a in assertions);song_locations=rows(directory/'song_locations.csv')
    timeline=[dict(year=y,films=sum(n['kind']=='Film' and n['year']==y for n in nodes.values()),filming_films=len(year_films[y]),places=len(year_places[y])) for y in range(*[summary['year_range'][0],summary['year_range'][1]+1])]
    coverage=dict(summary={k:v for k,v in summary.items() if k!='sources'},quality=quality,film_scope_counts=dict(collections.Counter(n['attributes']['scope_status'] for n in nodes.values() if n['kind']=='Film')),filming_film_coverage=round(100*len(filming_films)/max(1,summary['films']),2),song_location_coverage=round(100*summary['songs_with_filming_locations']/max(1,summary['songs']),2),missing_place_geometry=summary['places']-summary['geocoded_places'],source_counts=dict(source_counts),timeline=timeline,precision_counts=dict(collections.Counter(p['precision'] for p in geo)),limitations=['Coordinates are reference points unless a reviewed scene source explicitly provides shooting coordinates.','A missing link means a coverage gap, not evidence of absence.','Published administrative boundaries may differ from current divisions.','Hindi-cinema project scope follows the team list; missing language metadata and multilingual productions are explicitly flagged.'])
    source_hash=hashlib.sha256((directory/'graph.ttl').read_bytes()).hexdigest()
    # Build a separate immutable database; readers keep their old version until
    # the atomic pointer replacement after the complete build succeeds.
    db=directory/('catalog-'+source_hash[:16]+'-'+uuid.uuid4().hex[:8]+'.sqlite')
    con=sqlite3.connect(db);con.executescript('''DROP TABLE IF EXISTS nodes; DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS node_search; DROP TABLE IF EXISTS geometry;
CREATE TABLE nodes(id TEXT PRIMARY KEY,kind TEXT,label TEXT,normalized TEXT,year INTEGER,payload TEXT);
CREATE TABLE edges(id TEXT PRIMARY KEY,subject TEXT,relation TEXT,object TEXT,payload TEXT);
CREATE INDEX edge_subject ON edges(subject,relation);CREATE INDEX edge_object ON edges(object,relation);CREATE INDEX node_kind_label ON nodes(kind,normalized);
CREATE TABLE geometry(id TEXT PRIMARY KEY,lat REAL,lon REAL,precision TEXT,payload TEXT);CREATE INDEX geo_latlon ON geometry(lat,lon);
''')
    con.executemany('INSERT INTO nodes VALUES(?,?,?,?,?,?)',[(n['id'],n['kind'],n['label'],norm(n['label']+' '+' '.join(n['aliases'])),n['year'],json.dumps(n,ensure_ascii=False)) for n in nodes.values()])
    con.executemany('INSERT INTO edges VALUES(?,?,?,?,?)',[(e['id'],e['subject'],e['relation'],e['object'],json.dumps(e,ensure_ascii=False)) for e in edges.values()])
    con.executemany('INSERT INTO geometry VALUES(?,?,?,?,?)',[(p['id'],p['lat'],p['lon'],p['precision'],json.dumps(p,ensure_ascii=False)) for p in geo])
    try:
        con.execute('CREATE VIRTUAL TABLE node_search USING fts5(id UNINDEXED,label,normalized,tokenize="unicode61")');con.executemany('INSERT INTO node_search VALUES(?,?,?)',[(n['id'],n['label'],norm(n['label']+' '+' '.join(n['aliases']))) for n in nodes.values()]);fts=True
    except sqlite3.OperationalError:fts=False
    con.commit();con.execute('PRAGMA optimize');con.close()
    assets={};index=[dict(id=n['id'],kind=n['kind'],label=n['label'],year=n['year'],aliases=n['aliases'],poster=n.get('poster',''),scope_status=n['attributes'].get('scope_status','')) for n in nodes.values()]
    assets['search-core']=packed(public/'search-core.json.gz',[n for n in index if n['kind'] in ('Film','Song','Place','Heritage')]);assets['search-full']=packed(public/'search-full.json.gz',index)
    assets['places']=packed(public/'places.json.gz',geo);assets['timeline']=packed(public/'timeline.json.gz',timeline)
    genres=collections.defaultdict(list)
    for e in edges.values():
        if e['relation']=='genre':genres[e['subject']].append(nodes[e['object']]['label'])
    assets['film-filters']=packed(public/'film-filters.json.gz',{n['id']:dict(year=n['year'],genres=genres[n['id']]) for n in nodes.values() if n['kind']=='Film'})
    assets['song-locations']=packed(public/'song-locations.json.gz',[dict(r,song=nodes[r['song_id']]['label'],film=nodes[r['film_id']]['label'],place=nodes[r['place_id']]['label']) for r in song_locations])
    # Prefix shards hold complete film neighbourhoods including song credits and character roles.
    shards=collections.defaultdict(lambda:dict(nodes={},edges={}))
    for fid,n in nodes.items():
        if n['kind']!='Film':continue
        shard=shards[fid.split(':')[-1][:2]];selected=set(adj[fid]);neighbours={fid}
        for eid in list(selected):
            e=edges[eid];other=e['object'] if e['subject']==fid else e['subject'];neighbours.add(other)
            if nodes[other]['kind'] in ('Song','Character'):
                selected.update(adj[other])
            elif nodes[other]['kind']=='Heritage':selected.update(eid for eid in adj[other] if edges[eid]['relation']=='part_of_heritage')
        for eid in selected:
            e=edges[eid];shard['edges'][eid]=e;neighbours.update([e['subject'],e['object']])
        for nid in neighbours:shard['nodes'][nid]=nodes[nid]
    for prefix,shard in shards.items():assets['films/'+prefix]=packed(public/'films'/(prefix+'.json.gz'),shard)
    compact=dict(nodes={i:[n['label'],n['kind']] for i,n in nodes.items()},edges=[[e['subject'],e['relation'],e['object']] for e in edges.values()]);assets['connections']=packed(public/'connections.json.gz',compact)
    json_file(public/'coverage.json',coverage)
    asset_version=hashlib.sha256((source_hash+json.dumps(assets,sort_keys=True)).encode()).hexdigest()
    json_file(public/'catalog.json',dict(version=2,graph_sha256=source_hash,asset_version=asset_version,database=db.name,fts=fts,assets=assets,film_prefixes=sorted(shards)))
    pointer=directory/'catalog.current.tmp';json_file(pointer,dict(database=db.name,graph_sha256=source_hash));pointer.replace(directory/'catalog.current.json')
    print(json.dumps(dict(database=str(db),nodes=len(nodes),relationships=len(edges),public_compressed_bytes=sum(v['compressed_bytes'] for v in assets.values()),search_core_compressed_bytes=assets['search-core']['compressed_bytes'],film_shards=len(shards)),indent=2))
    return coverage


class Catalog:
    def __init__(self,directory=ROOT/'Dataset/integrated'):self.directory=Path(directory)
    def connect(self):
        current=json.loads((self.directory/'catalog.current.json').read_text(encoding='utf-8'));con=sqlite3.connect((self.directory/current['database']).resolve().as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row;return con
    def node(self,identity):
        with contextlib.closing(self.connect()) as con:row=con.execute('SELECT payload FROM nodes WHERE id=?',(identity,)).fetchone()
        return json.loads(row[0]) if row else None
    def search(self,text='',kind='',limit=30,offset=0):
        limit=max(1,min(int(limit),100));offset=max(0,int(offset));q=norm(text);where='WHERE (?="" OR kind=?) AND (?="" OR normalized LIKE ? ESCAPE "\\")'
        escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        with contextlib.closing(self.connect()) as con:
            if q and con.execute("SELECT 1 FROM sqlite_master WHERE name='node_search'").fetchone():
                tokens=re.findall(r'\w+',q,flags=re.UNICODE)
                if tokens:
                    match=' AND '.join('"'+t.replace('"','')+'"*' for t in tokens)
                    total=con.execute('SELECT COUNT(*) FROM node_search s JOIN nodes n ON n.id=s.id WHERE node_search MATCH ? AND (?="" OR n.kind=?)',(match,kind,kind)).fetchone()[0]
                    if total:
                        result=con.execute('SELECT n.payload FROM node_search s JOIN nodes n ON n.id=s.id WHERE node_search MATCH ? AND (?="" OR n.kind=?) ORDER BY n.label LIMIT ? OFFSET ?',(match,kind,kind,limit,offset)).fetchall()
                        return dict(total=total,items=[{k:v for k,v in json.loads(r[0]).items() if k!='attributes'} for r in result],offset=offset,limit=limit)
            total=con.execute('SELECT COUNT(*) FROM nodes '+where,(kind,kind,q,'%'+escaped+'%')).fetchone()[0]
            result=con.execute("SELECT payload FROM nodes "+where+" ORDER BY CASE WHEN label LIKE 'Fanaa%' THEN 0 WHEN label='Jodhaa Akbar' THEN 1 WHEN label='Haider' THEN 2 WHEN label='3 Idiots' THEN 3 WHEN label='Kabhi Khushi Kabhie Gham...' THEN 4 WHEN label='Yeh Jawaani Hai Deewani' THEN 5 ELSE 6 END,CASE WHEN normalized=? THEN 0 ELSE 1 END,label LIMIT ? OFFSET ?",(kind,kind,q,'%'+escaped+'%',q,limit,offset)).fetchall()
        return dict(total=total,items=[{k:v for k,v in json.loads(r[0]).items() if k!='attributes'} for r in result],offset=offset,limit=limit)
    def graph(self,identity,relations=None):
        n=self.node(identity)
        if not n:raise ValueError('Unknown entity')
        with contextlib.closing(self.connect()) as con:
            edges=[json.loads(r[0]) for r in con.execute('SELECT payload FROM edges WHERE subject=? OR object=?',(identity,identity))]
            if n['kind']=='Film':
                extras={e['subject'] if e['object']==identity else e['object'] for e in edges}
                for other in extras:
                    kind=con.execute('SELECT kind FROM nodes WHERE id=?',(other,)).fetchone()
                    if kind and kind[0] in ('Song','Character'):edges.extend(json.loads(r[0]) for r in con.execute('SELECT payload FROM edges WHERE subject=? OR object=?',(other,other)))
                    elif kind and kind[0]=='Heritage':edges.extend(json.loads(r[0]) for r in con.execute('SELECT payload FROM edges WHERE (subject=? OR object=?) AND relation="part_of_heritage"',(other,other)))
            edges=list({e['id']:e for e in edges}.values())
            if relations:edges=[e for e in edges if e['relation'] in relations]
            ids={identity}|{e[k] for e in edges for k in ('subject','object')}
            nodes={i:json.loads(con.execute('SELECT payload FROM nodes WHERE id=?',(i,)).fetchone()[0]) for i in ids}
        return dict(center=identity,nodes=nodes,edges=edges)
    def nearest(self,lat,lon,radius=25,limit=20,precise=False,heritage=False):
        lat,lon,radius=float(lat),float(lon),float(radius)
        if not all(math.isfinite(v) for v in (lat,lon,radius)) or abs(lat)>90 or abs(lon)>180 or not .1<=radius<=2000:raise ValueError('Invalid point or radius (0.1–2,000 km)')
        delta=radius/110
        with contextlib.closing(self.connect()) as con:candidates=[json.loads(r[0]) for r in con.execute('SELECT payload FROM geometry WHERE lat BETWEEN ? AND ?',(lat-delta,lat+delta))]
        items=[]
        for p in candidates:
            if heritage and (not p['heritage'] or p.get('parent_id')):continue
            if precise and p['precision']!='site_reference':continue
            d=distance([lat,lon],[p['lat'],p['lon']])
            if d<=radius:items.append(dict(p,distance_km=d))
        return dict(items=sorted(items,key=lambda p:p['distance_km'])[:max(1,min(int(limit),100))],distance_type='spherical_reference_point',radius_km=radius)
    def path(self,start,end,max_depth=4):
        if not self.node(start) or not self.node(end):raise ValueError('Choose known graph entities')
        max_depth=max(1,min(int(max_depth),5));queue=collections.deque([(start,[])]);seen={start};visited=0
        with contextlib.closing(self.connect()) as con:
            while queue:
                node,path=queue.popleft();visited+=1
                if node==end:return dict(found=True,path=path,visited=visited)
                if len(path)>=max_depth:continue
                if visited>15000:return dict(found=False,path=[],visited=visited,truncated=True)
                for r in con.execute('SELECT payload FROM edges WHERE subject=? OR object=?',(node,node)):
                    e=json.loads(r[0]);other=e['object'] if e['subject']==node else e['subject']
                    if other not in seen:seen.add(other);queue.append((other,path+[dict(edge=e,from_id=node,to_id=other)]))
        return dict(found=False,path=[],visited=visited,truncated=False)
    def itinerary(self,ids):
        if not 2<=len(ids)<=8 or len(set(ids))!=len(ids):raise ValueError('Choose 2–8 different places')
        places=[]
        for identity in ids:
            n=self.node(identity)
            if not n or n['kind'] not in ('Place','Heritage') or n['attributes'].get('latitude','')=='':raise ValueError('Itinerary needs geocoded places')
            places.append(dict(id=identity,name=n['label'],lat=float(n['attributes']['latitude']),lon=float(n['attributes']['longitude']),precision=n['attributes'].get('location_precision','unknown_reference')))
        def cost(order):return sum(distance([a['lat'],a['lon']],[b['lat'],b['lon']]) for a,b in zip(order,order[1:]))
        best=min(([places[0],*tail] for tail in itertools.permutations(places[1:])),key=cost)
        return dict(stops=best,distance_km=cost(best),method='shortest_straight_line_open_path_fixed_start',road_route=False,geojson=dict(type='Feature',properties=dict(role='reference_point_itinerary',method='geodesic_order'),geometry=dict(type='LineString',coordinates=[[p['lon'],p['lat']] for p in best])))


if __name__=='__main__':build()
