"""Durable discovery jobs. Budgets pause work without discarding pending searches."""
import contextlib,hashlib,json,sqlite3,time,uuid
from pathlib import Path


class Queue:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.owner=uuid.uuid4().hex
        with contextlib.closing(self.connect()) as con:
            con.executescript('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,language TEXT,payload TEXT,status TEXT,attempts INTEGER DEFAULT 0,owner TEXT,lease_until REAL DEFAULT 0,error TEXT DEFAULT '');CREATE INDEX IF NOT EXISTS work_status ON jobs(status,kind,language);
CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,payload TEXT);CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,job_id TEXT,event TEXT,created REAL);''');con.commit()
    def connect(self):
        con=sqlite3.connect(self.path,timeout=15);con.row_factory=sqlite3.Row;return con
    def add(self,kind,language,payload):
        text=json.dumps(payload,sort_keys=True,ensure_ascii=False);identity=hashlib.sha256((kind+'|'+language+'|'+text).encode()).hexdigest()
        with contextlib.closing(self.connect()) as con:con.execute('INSERT OR IGNORE INTO jobs(id,kind,language,payload,status) VALUES(?,?,?,?,"queued")',(identity,kind,language,text));con.commit()
        return identity
    def add_many(self,jobs):
        values=[]
        for kind,language,payload in jobs:
            text=json.dumps(payload,sort_keys=True,ensure_ascii=False);identity=hashlib.sha256((kind+'|'+language+'|'+text).encode()).hexdigest();values.append((identity,kind,language,text))
        with contextlib.closing(self.connect()) as con:con.executemany('INSERT OR IGNORE INTO jobs(id,kind,language,payload,status) VALUES(?,?,?,?,"queued")',values);con.commit()
    def claim(self,kind,limit=1,include_waiting=True):
        with contextlib.closing(self.connect()) as con:
            con.execute('BEGIN IMMEDIATE');con.execute('UPDATE jobs SET status="queued",owner=NULL WHERE status="running" AND lease_until<?',(time.time(),))
            statuses='("queued","waiting")' if include_waiting else '("queued")'
            first=con.execute('SELECT language FROM jobs WHERE kind=? AND status IN '+statuses+' ORDER BY rowid LIMIT 1',(kind,)).fetchone()
            if not first:con.commit();return []
            items=con.execute('SELECT * FROM jobs WHERE kind=? AND language=? AND status IN '+statuses+' ORDER BY rowid LIMIT ?',(kind,first[0],limit)).fetchall()
            for row in items:con.execute('UPDATE jobs SET status="running",owner=?,lease_until=?,attempts=attempts+1 WHERE id=?',(self.owner,time.time()+600,row['id']))
            con.commit()
        return [dict(id=r['id'],kind=r['kind'],language=r['language'],payload=json.loads(r['payload']),attempts=r['attempts']+1) for r in items]
    def finish(self,identity,status='done',error=''):
        if status not in {'done','queued','waiting','failed','blocked'}:raise ValueError('Invalid job status')
        with contextlib.closing(self.connect()) as con:
            con.execute('UPDATE jobs SET status=?,owner=NULL,lease_until=0,error=? WHERE id=? AND owner=?',(status,error,identity,self.owner));con.execute('INSERT INTO events(job_id,event,created) VALUES(?,?,?)',(identity,status,time.time()));con.commit()
    def release(self):
        with contextlib.closing(self.connect()) as con:con.execute('UPDATE jobs SET status="queued",owner=NULL,lease_until=0 WHERE status="running" AND owner=?',(self.owner,));con.commit()
    def block_owned(self,error):
        with contextlib.closing(self.connect()) as con:con.execute('UPDATE jobs SET status="blocked",owner=NULL,lease_until=0,error=? WHERE status="running" AND owner=?',(error,self.owner));con.commit()
    def retry(self,status='blocked'):
        if status not in ('blocked','waiting','failed'):raise ValueError('Invalid retry state')
        with contextlib.closing(self.connect()) as con:con.execute('UPDATE jobs SET status="queued",error="" WHERE status=?',(status,));con.commit()
    def candidate(self,identity,payload):
        with contextlib.closing(self.connect()) as con:con.execute('INSERT OR IGNORE INTO candidates VALUES(?,?)',(identity,json.dumps(payload,ensure_ascii=False)));con.commit()
    def candidates(self):
        with contextlib.closing(self.connect()) as con:return [json.loads(r[0]) for r in con.execute('SELECT payload FROM candidates ORDER BY rowid')]
    def summary(self):
        with contextlib.closing(self.connect()) as con:
            statuses=dict(con.execute('SELECT status,COUNT(*) FROM jobs GROUP BY status'));kinds=[dict(r) for r in con.execute('SELECT kind,language,status,COUNT(*) AS count FROM jobs GROUP BY kind,language,status')];count=con.execute('SELECT COUNT(*) FROM candidates').fetchone()[0]
        return dict(statuses=statuses,groups=kinds,candidates=count,pending=sum(statuses.get(s,0) for s in ['queued','waiting','running','blocked']),completed=statuses.get('done',0))
