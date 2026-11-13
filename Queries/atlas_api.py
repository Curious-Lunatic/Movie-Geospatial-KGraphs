"""Loopback-only catalogue/review API. Public static deployments are read-only."""
import json,secrets,subprocess,sys,threading
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from atlas_catalog import Catalog,ROOT
from atlas_questions import answer
from atlas_review import ReviewStore,Conflict


class AtlasAPI:
    def __init__(self):self.catalog=Catalog();self.review=None;self.token=secrets.token_urlsafe(32);self.build_status=dict(running=False)
    def store(self):
        if self.review is None:self.review=ReviewStore(catalog=self.catalog);self.review.seed()
        return self.review
    def get(self,path,query):
        one=lambda k,default='':query.get(k,[default])[0]
        if path=='/api/catalog/search':return self.catalog.search(one('q'),one('kind'),one('limit',30),one('offset',0))
        if path=='/api/catalog/node':return self.catalog.node(one('id')) or {}
        if path=='/api/catalog/graph':return self.catalog.graph(one('id'),one('relations').split(',') if one('relations') else None)
        if path=='/api/catalog/nearest':return self.catalog.nearest(one('lat'),one('lon'),one('radius',25),one('limit',30),one('precise')=='true')
        if path=='/api/catalog/path':return self.catalog.path(one('from'),one('to'),one('depth',4))
        if path=='/api/catalog/ask':return answer(self.catalog,one('q'))
        if path=='/api/review/session':return dict(token=self.token,mode='local_review',read_only=False)
        if path=='/api/review/items':return self.store().list(one('status'),one('q'),one('limit',25),one('offset',0))
        if path=='/api/review/build-status':return self.build_status
        if path=='/api/review/history':return self.store().history(one('id'))
        return None
    def post(self,path,body):
        if path=='/api/catalog/itinerary':return self.catalog.itinerary(body.get('places',[]))
        if path=='/api/review/decision':return self.store().decide(body['id'],body['version'],body['status'],body.get('note',''),body.get('payload'))
        if path=='/api/review/propose':return self.store().propose(body)
        if path=='/api/review/export':return self.store().export()
        if path=='/api/review/rescan':self.store().seed();return self.store().list(limit=1)
        if path=='/api/review/rebuild':
            if self.build_status['running']:raise Conflict('A rebuild is already running')
            self.store().export();self.build_status=dict(running=True,stage='Building reviewed catalogue')
            def work():
                try:
                    log=ROOT/'outputs/review/build.log';log.parent.mkdir(parents=True,exist_ok=True)
                    with log.open('w',encoding='utf-8') as stream:
                        for script in ['build_integrated_graph.py','build_graph_explorer.py','build_atlas_product.py']:
                            subprocess.run([sys.executable,str(ROOT/'Queries'/script)],cwd=ROOT,check=True,stdout=stream,stderr=subprocess.STDOUT)
                    self.build_status=dict(running=False,complete=True,message='Reviewed catalogue is ready. Reload the atlas to use the new version.')
                except Exception:self.build_status=dict(running=False,complete=False,message='Rebuild failed. Check outputs/review/build.log before reloading or exporting. Source files and review decisions are retained.')
            threading.Thread(target=work,daemon=True).start();return self.build_status
        raise ValueError('Unknown operation')


API=AtlasAPI()


def handle_get(handler,path,query):
    if not path.startswith('/api/catalog/') and not path.startswith('/api/review/'):return False
    host=urlsplit('http://'+handler.headers.get('Host','')).hostname
    if host not in ('127.0.0.1','localhost','::1'):respond(handler,403,dict(error='Local API only'));return True
    try:
        result=API.get(path,query);respond(handler,200 if result is not None else 404,result if result is not None else dict(error='Unknown operation'))
    except Conflict as error:respond(handler,409,dict(error=str(error)))
    except (ValueError,KeyError,TypeError) as error:respond(handler,400,dict(error=str(error)))
    except Exception:respond(handler,503,dict(error='The catalogue is not ready. Finish the local build and refresh.'))
    return True


def handle_post(handler):
    host=handler.headers.get('Host','');origin=handler.headers.get('Origin')
    if urlsplit('http://'+host).hostname not in ('127.0.0.1','localhost','::1') or (origin and origin!='http://'+host) or handler.headers.get('X-Atlas-Token')!=API.token:
        respond(handler,403,dict(error='Open the local review page before saving changes.'));return
    try:
        length=int(handler.headers.get('Content-Length','0'))
        if not 0<length<=100000:raise ValueError('Request is empty or too large')
        body=json.loads(handler.rfile.read(length));result=API.post(urlsplit(handler.path).path,body);respond(handler,200,result)
    except Conflict as error:respond(handler,409,dict(error=str(error)))
    except (ValueError,KeyError,TypeError) as error:respond(handler,400,dict(error=str(error)))
    except Exception:respond(handler,500,dict(error='The operation could not be completed. Please retry.'))


def respond(handler,status,body):
    raw=json.dumps(body,ensure_ascii=False).encode('utf-8');handler.send_response(status);handler.send_header('Content-Type','application/json; charset=utf-8');handler.send_header('Cache-Control','no-store');handler.send_header('Content-Length',str(len(raw)));handler.send_header('X-Content-Type-Options','nosniff');handler.end_headers();handler.wfile.write(raw)
