"""Local review queue with durable decisions, optimistic versions and an audit log."""
import collections,contextlib,csv,hashlib,json,math,re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from atlas_catalog import ROOT,rows
from build_integrated_graph import key,norm

STATUSES={'needs_review','approved','rejected','conflict','source_supported','rejected_or_duplicate'}
class Conflict(ValueError):pass
def now():return datetime.now(timezone.utc).isoformat()
def marker(row):return hashlib.sha256(json.dumps([row.get('song_id',''),row.get('place_id') or row.get('site_article') or row.get('place',''),row.get('source_url',''),row.get('evidence','')],ensure_ascii=False).encode()).hexdigest()
def public_url(url):
    try:p=urlsplit(url)
    except ValueError:raise ValueError('Invalid evidence URL')
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password or len(url)>2048:raise ValueError('Use a public HTTP(S) evidence URL without login details')
    return url


class ReviewStore:
    def __init__(self,path=ROOT/'outputs/review/review.sqlite',catalog=None):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.catalog=catalog
        with contextlib.closing(self.connect()) as con:
            con.executescript('''CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,status TEXT NOT NULL,version INTEGER NOT NULL,original_payload TEXT,payload TEXT,note TEXT,reviewer TEXT,updated_at TEXT,batch TEXT);
CREATE INDEX IF NOT EXISTS candidate_status ON candidates(status,updated_at);
CREATE TABLE IF NOT EXISTS review_events(id INTEGER PRIMARY KEY,candidate_id TEXT,action TEXT,old_version INTEGER,new_version INTEGER,payload TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS imports(path TEXT PRIMARY KEY,sha256 TEXT,imported_at TEXT);''');con.commit()
    def connect(self):
        con=sqlite3.connect(self.path,timeout=10);con.row_factory=sqlite3.Row;return con
    def ingest(self,path,batch=None,decisions=None):
        path=Path(path)
        if not path.exists():return 0
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();added=0
        with contextlib.closing(self.connect()) as con:
            old=con.execute('SELECT sha256 FROM imports WHERE path=?',(str(path.resolve()),)).fetchone()
            if old and old[0]==sha and not decisions:return 0
            for i,row in enumerate(rows(path),2):
                identity=marker(row);decision=(decisions or {}).get(i,{});status=decision.get('status','needs_review')
                if status not in STATUSES:status='needs_review'
                payload=json.dumps(row,ensure_ascii=False)
                result=con.execute('INSERT OR IGNORE INTO candidates VALUES(?,?,1,?,?,?,?,?,?)',(identity,status,payload,payload,decision.get('reason',''),'source_review' if decision else '',now(),batch or path.parent.name));added+=result.rowcount
                if not result.rowcount and status=='source_supported':
                    existing=con.execute('SELECT status,version,reviewer FROM candidates WHERE id=?',(identity,)).fetchone()
                    if existing['status']=='rejected_or_duplicate' and existing['version']==1 and existing['reviewer']=='source_review':
                        # A duplicate-row exclusion must not hide the source-supported
                        # representative of that exact song/place/source assertion.
                        con.execute('UPDATE candidates SET status=?,payload=?,note=?,version=2,updated_at=? WHERE id=?',(status,payload,decision.get('reason',''),now(),identity))
                        con.execute('INSERT INTO review_events(candidate_id,action,old_version,new_version,payload,created_at) VALUES(?,"import_reconciled",1,2,?,?)',(identity,json.dumps(dict(reason='Source-supported representative takes precedence over an excluded duplicate CSV row')),now()))
            con.execute('INSERT OR REPLACE INTO imports VALUES(?,?,?)',(str(path.resolve()),sha,now()));con.commit()
        return added
    def seed(self):
        original=ROOT/'outputs/song-location-review/candidates-snapshot.csv';decisions={int(r['candidate_csv_row']):r for r in rows(ROOT/'Dataset/song_review/decisions.csv')}
        self.ingest(original,'reviewed-437',decisions)
        for folder in ['song-location-all','song-location-fast','song-location-scrape','discovery-v2']:
            self.ingest(ROOT/'outputs'/folder/'candidates.csv',folder)
    def list(self,status='',text='',limit=25,offset=0):
        limit=max(1,min(int(limit),100));offset=max(0,int(offset));args=(status,status,text,'%'+text+'%')
        with contextlib.closing(self.connect()) as con:
            where=' WHERE (?="" OR status=?) AND (?="" OR payload LIKE ?)'
            total=con.execute('SELECT COUNT(*) FROM candidates'+where,args).fetchone()[0]
            data=con.execute('SELECT * FROM candidates'+where+' ORDER BY CASE status WHEN "needs_review" THEN 0 WHEN "conflict" THEN 1 ELSE 2 END,updated_at DESC LIMIT ? OFFSET ?',args+(limit,offset)).fetchall()
            counts=dict(con.execute('SELECT status,COUNT(*) FROM candidates GROUP BY status').fetchall())
        return dict(total=total,counts=counts,items=[dict(id=r['id'],status=r['status'],version=r['version'],payload=json.loads(r['payload']),note=r['note'],reviewer=r['reviewer'],updated_at=r['updated_at'],batch=r['batch']) for r in data],offset=offset,limit=limit)
    def validate(self,payload):
        p=dict(payload)
        for flag in ['allow_new_song','allow_new_place','camera_position_verified']:
            if flag in p and not isinstance(p[flag],bool):raise ValueError('Review checkboxes must be true or false')
        if not isinstance(p.get('evidence'),str) or not 20<=len(p['evidence'].strip())<=4000:raise ValueError('Explain the song-specific source evidence in 20–4,000 characters')
        public_url(p.get('source_url',''))
        if p.get('location_precision') not in {'site_reference','route_reference','locality_reference','region_reference','country_reference','unknown_reference'}:raise ValueError('Choose the coordinate precision')
        film=self.catalog.node(p.get('film_id','')) if self.catalog else None
        song=self.catalog.node(p.get('song_id','')) if self.catalog else None
        place=self.catalog.node(p.get('place_id','')) if self.catalog else None
        if self.catalog:
            if not film or film['kind']!='Film':raise ValueError('Resolve the canonical film first')
            if song:
                if song['kind']!='Song' or song['attributes'].get('film_id')!=film['id']:raise ValueError('The selected song belongs to a different film')
            elif p.get('allow_new_song') and p.get('song','').strip():p['song_id']=key('song',film['id'],norm(p['song']));p['new_song']=True
            else:raise ValueError('Resolve the song or explicitly approve a new film-scoped song')
            if place:
                if place['kind'] not in ('Place','Heritage'):raise ValueError('Selected location is not a place')
            elif p.get('allow_new_place') and p.get('place','').strip():p['place_id']=key('place','local_review',norm(p['place']));p['new_place']=True
            else:raise ValueError('Resolve the place or explicitly approve a new place')
        lat,lon=p.get('latitude',''),p.get('longitude','')
        if lat!='' or lon!='':
            try:lat,lon=float(lat),float(lon)
            except (ValueError,TypeError):raise ValueError('Provide both latitude and longitude or leave both blank')
            if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat)>90 or abs(lon)>180:raise ValueError('Coordinates must be valid WGS 84 latitude/longitude')
            p.update(latitude=lat,longitude=lon)
            if p.get('new_place'):public_url(p.get('coordinate_source',''))
        for name in ['scene_start_seconds','scene_end_seconds','coordinate_uncertainty_m']:
            if p.get(name,'')!='':
                try:value=float(p[name])
                except (ValueError,TypeError):raise ValueError('Invalid '+name)
                if not math.isfinite(value) or value<0 or value>1e7:raise ValueError('Invalid '+name)
                p[name]=value
        if p.get('scene_end_seconds','')!='' and p.get('scene_start_seconds','')!='' and p['scene_end_seconds']<p['scene_start_seconds']:raise ValueError('Scene end must follow scene start')
        if p.get('scene_start_seconds','')!='':public_url(p.get('scene_evidence_url') or p['source_url'])
        if p.get('camera_position_verified') and (p.get('scene_start_seconds','')=='' or not p.get('coordinate_source')):raise ValueError('Exact camera claims need scene evidence, a coordinate source and explicit source review')
        if p.get('camera_position_verified'):
            if lat=='' or lon=='':raise ValueError('An exact shooting-coordinate claim needs both coordinates')
            p['scene_latitude']=lat;p['scene_longitude']=lon
        p['camera_position_verified']=bool(p.get('camera_position_verified',False))
        return p
    def decide(self,identity,version,status,note='',payload=None,reviewer='local_review'):
        if status not in STATUSES or len(note)>4000:raise ValueError('Invalid review decision')
        with contextlib.closing(self.connect()) as con:
            con.execute('BEGIN IMMEDIATE');row=con.execute('SELECT * FROM candidates WHERE id=?',(identity,)).fetchone()
            if not row:raise ValueError('Unknown review record')
            if row['version']!=int(version):raise Conflict('This record changed. Reload it before saving your decision.')
            p=payload if payload is not None else json.loads(row['payload'])
            if status=='approved':p=self.validate(p)
            encoded=json.dumps(p,ensure_ascii=False);new_version=row['version']+1
            con.execute('UPDATE candidates SET status=?,version=?,payload=?,note=?,reviewer=?,updated_at=? WHERE id=?',(status,new_version,encoded,note,reviewer,now(),identity))
            con.execute('INSERT INTO review_events(candidate_id,action,old_version,new_version,payload,created_at) VALUES(?,?,?,?,?,?)',(identity,status,row['version'],new_version,json.dumps(dict(note=note,payload=p),ensure_ascii=False),now()));con.commit()
        return dict(id=identity,status=status,version=new_version)
    def propose(self,payload):
        if not isinstance(payload,dict) or not payload.get('song_id') or not payload.get('place') or len(json.dumps(payload))>15000:raise ValueError('Proposal needs a recorded song and named place')
        if self.catalog:
            song=self.catalog.node(payload['song_id'])
            if not song or song['kind']!='Song':raise ValueError('Choose a recorded song for a new proposal')
            if payload.get('film_id') and payload['film_id']!=song['attributes'].get('film_id'):raise ValueError('The proposed song belongs to a different film')
            payload=dict(payload,film_id=song['attributes']['film_id'])
        if not isinstance(payload.get('evidence'),str) or len(payload['evidence'].strip())<20:raise ValueError('Include the song-specific source evidence')
        public_url(payload.get('source_url',''))
        identity=marker(payload)
        with contextlib.closing(self.connect()) as con:
            text=json.dumps(payload,ensure_ascii=False);con.execute('INSERT OR IGNORE INTO candidates VALUES(?,"needs_review",1,?,?,"","",?,"scene-proposals")',(identity,text,text,now()));con.commit()
        return dict(id=identity,status='needs_review',accepted_graph_changed=False)
    def history(self,identity):
        with contextlib.closing(self.connect()) as con:items=con.execute('SELECT action,old_version,new_version,payload,created_at FROM review_events WHERE candidate_id=? ORDER BY id',(identity,)).fetchall()
        return dict(items=[dict(r) for r in items])
    def export(self,path=ROOT/'Queries/curation/approved_records.json'):
        with contextlib.closing(self.connect()) as con:data=con.execute('SELECT id,version,payload,note,reviewer,updated_at FROM candidates WHERE status="approved" ORDER BY id').fetchall()
        records=[]
        for row in data:records.append(dict(self.validate(json.loads(row['payload'])),review_id=row['id'],review_version=row['version'],review_note=row['note'],reviewer=row['reviewer'],reviewed_at=row['updated_at']))
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(dict(version=1,records=records),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)
        return dict(exported=len(records),path=str(path),accepted_graph_changed=False)


def apply_approved(graph):
    from build_integrated_graph import coordinates
    path=graph.data/'../Queries/curation/approved_records.json'
    if not path.exists():return
    raw=path.read_bytes();records=json.loads(raw)['records'];source='../Queries/curation/approved_records.json';graph.inputs[source]=dict(rows=len(records),sha256=hashlib.sha256(raw).hexdigest())
    for index,p in enumerate(records,1):
        fid=p['film_id']
        if fid not in graph.films:continue
        sid,pid=p['song_id'],p['place_id']
        public_url(p['source_url'])
        if sid not in graph.songs:
            if not p.get('new_song'):raise ValueError('Approved song identity missing')
            graph.songs[sid]=dict(song_id=sid,title=p['song'],film_id=fid,singers='',music='',lyrics='');graph.claim(sid,'in_film',fid,source,index,'reviewed_local_dashboard',p['source_url'])
        if graph.songs[sid]['film_id']!=fid:raise ValueError('Approved song/film mismatch')
        if pid not in graph.places:
            if not p.get('new_place'):raise ValueError('Approved place identity missing')
            point=coordinates(p.get('latitude'),p.get('longitude'));graph.add_place(pid,p['place'],point,'place_representative_point' if point else 'unresolved',p.get('coordinate_source',''))
            graph.places[pid].update(place_type=p.get('place_type','unknown'),location_precision=p['location_precision'],aliases='[]',locality=p.get('locality',''),description='Locally reviewed song-location reference.',identity_source=p['source_url'],classification_source=source,wikidata_revision='')
        graph.claim(sid,'song_filming',pid,source,index,'reviewed_local_dashboard',p['source_url'],evidence=p['evidence'],precision=p['location_precision'])
        cid=key('claim',sid,'song_filming',pid,source,str(index),'reviewed_local_dashboard')
        graph.claims[cid].update({k:p.get(k,'') for k in ['scene_start_seconds','scene_end_seconds','scene_evidence_url','coordinate_uncertainty_m','camera_position_verified','scene_latitude','scene_longitude','coordinate_source']})
        graph.claims[cid]['retrieved_at']=p.get('retrieved_at','')
        graph.claims[cid]['reviewed_at']=p['reviewed_at']
        graph.song_locations.append(dict(song_id=sid,film_id=fid,place_id=pid,location_precision=p['location_precision'],source_url=p['source_url'],source_file=source,source_row=index,evidence=p['evidence'],scene_timestamp=str(p.get('scene_start_seconds','')),status='source_supported'))
