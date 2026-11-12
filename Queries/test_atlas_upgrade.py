"""Regression checks for identity, durable discovery, review and spatial queries."""
import contextlib,csv,io,json,sqlite3,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from atlas_catalog import Catalog,build,distance
from atlas_questions import resolve,title_reference
from atlas_review import ReviewStore,Conflict,marker
from discovery_queue import Queue
from curation.apply import apply

class QueueTests(unittest.TestCase):
    def test_source_supported_import_is_not_hidden_by_duplicate_row_order(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'candidates.csv';row=dict(song_id='s',place_id='p',source_url='https://example.org',evidence='Same source assertion')
            with path.open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerows([row,row])
            store=ReviewStore(Path(temp)/'review.sqlite');decisions={2:dict(status='rejected_or_duplicate'),3:dict(status='source_supported')};store.ingest(path,decisions=decisions)
            item=store.list()['items'][0];self.assertEqual(item['status'],'source_supported');store.decide(item['id'],item['version'],'rejected');store.ingest(path,decisions=decisions);self.assertEqual(store.list()['items'][0]['status'],'rejected')
    def test_unresolved_named_sites_keep_separate_review_identities(self):
        row=dict(song_id='s',place_id='',source_url='https://example.org/source',evidence='Song filmed at A and B.')
        self.assertNotEqual(marker(dict(row,site_article='A')),marker(dict(row,site_article='B')))
    def test_budgets_duplicates_language_and_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'work.sqlite';q=Queue(path)
            q.add_many([('page','en',{'title':'A'}),('page','en',{'title':'B'}),('page','hi',{'title':'A'}),('page','en',{'title':'A'})])
            batch=q.claim('page',20);self.assertEqual(len(batch),2);self.assertEqual({j['language'] for j in batch},{'en'})
            q.finish(batch[0]['id']);q.release();self.assertEqual(Queue(path).summary()['pending'],2)
            second=Queue(path);job=second.claim('page')[0];second.block_owned('HTTP 429');self.assertEqual(second.summary()['statuses']['blocked'],1)
            second.retry();self.assertEqual(second.claim('page')[0]['id'],job['id']);second.release()
    def test_unexpired_lease_is_not_stolen(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'work.sqlite';one=Queue(path);one.add('page','en',{'title':'A'});job=one.claim('page')[0];two=Queue(path)
            self.assertEqual(two.claim('page'),[])
            with contextlib.closing(one.connect()) as con:con.execute('UPDATE jobs SET lease_until=0');con.commit()
            self.assertEqual(two.claim('page')[0]['id'],job['id'])
    def test_offline_waiting_does_not_starve_cached_jobs(self):
        with tempfile.TemporaryDirectory() as temp:
            q=Queue(Path(temp)/'q.sqlite');q.add_many([('page','en',{'title':str(i)}) for i in range(3)])
            a=q.claim('page',1,False)[0];q.finish(a['id'],'waiting');b=q.claim('page',1,False)[0];self.assertNotEqual(a['id'],b['id'])

class IdentityTests(unittest.TestCase):
    def test_numbers_in_titles_are_not_assumed_to_be_release_years(self):
        self.assertEqual(title_reference('1971'),('1971',None));self.assertEqual(title_reference('1942: A Love Story'),('1942: A Love Story',None));self.assertEqual(title_reference('Fanaa (2006 film)'),('Fanaa',2006))
    def test_ambiguous_and_generic_names_are_not_guessed(self):
        def p(name,lat,source='same'):return dict(place_name=name,latitude=lat,longitude=80.0,coordinate_source=source,country_names='India',place_type='city')
        with tempfile.TemporaryDirectory() as temp:
            graph=SimpleNamespace(data=Path(temp)/'Dataset',places={'Q1':p('Chennai',13.0),'Q2':p('Chennai',13.0),'other':p('Chennai',14.0),'bad':p('The',12.0)},claims={},song_locations=[],songs={},inputs={},place_quality={})
            apply(graph);self.assertEqual(len(graph.places),4);self.assertTrue(graph.places['bad']['place_name'].startswith('Unresolved place'));self.assertEqual(graph.places['bad']['original_label'],'The');self.assertFalse(graph.curation['redirects'])

class ProductFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.directory=Path(cls.temp.name)
        def csvfile(name,fields,values):
            with (cls.directory/name).open('w',newline='',encoding='utf-8') as stream:
                w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(values)
        csvfile('films.csv',['film_id','title','release_year'],[dict(film_id='film:a1',title='Example',release_year=2000),dict(film_id='film:b2',title='Example',release_year=2010)])
        csvfile('songs.csv',['song_id','title','film_id'],[dict(song_id='song:one',title='Short Title',film_id='film:a1')])
        csvfile('places.csv',['place_id','place_name','latitude','longitude','location_precision','aliases'],[dict(place_id='place:near',place_name='Near',latitude=0,longitude=.001,location_precision='locality_reference',aliases='[]'),dict(place_id='heritage:one',place_name='Named heritage',latitude=0,longitude=.01,location_precision='site_reference',aliases='[]'),dict(place_id='place:far',place_name='Far',latitude=0,longitude=179.9,location_precision='country_reference',aliases='[]')])
        csvfile('claims.csv',['claim_id','subject_id','relation','object_id','source_file','source_row','source_url','method'],[dict(claim_id='1',subject_id='song:one',relation='in_film',object_id='film:a1',source_file='input.csv',source_row=2,source_url='https://example.org/record',method='reviewed_test'),dict(claim_id='2',subject_id='song:one',relation='song_filming',object_id='heritage:one',source_file='input.csv',source_row=3,source_url='https://example.org/evidence',method='reviewed_test')])
        csvfile('entity_aliases.csv',['canonical_id','alias_label'],[dict(canonical_id='song:one',alias_label='Full Song Title')])
        (cls.directory/'graph.ttl').write_text('# fixture')
        (cls.directory/'summary.json').write_text(json.dumps(dict(year_range=[2000,2010],films=2,songs=1,places=3,geocoded_places=3,songs_with_filming_locations=1)))
        (cls.directory/'place_quality.json').write_text('{}');build(cls.directory);cls.catalog=Catalog(cls.directory)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_ambiguous_film_needs_year(self):
        self.assertIn('error',resolve(self.catalog,'Example','Film'));self.assertEqual(resolve(self.catalog,'Example 2000','Film')['id'],'film:a1')
    def test_song_alias_joins_canonical_identity(self):
        self.assertEqual(resolve(self.catalog,'Full Song Title','Song')['id'],'song:one')
    def test_source_and_second_hop_preserved(self):
        graph=self.catalog.graph('film:a1');edge=next(e for e in graph['edges'] if e['relation']=='song_filming');self.assertEqual(edge['assertions'][0]['source_row'],'3')
    def test_filter_before_nearest_limit_and_antimeridian(self):
        self.assertEqual(self.catalog.nearest(0,0,25,1,heritage=True)['items'][0]['id'],'heritage:one')
        self.assertAlmostEqual(distance([0,179.9],[0,-179.9]),22.239,places=2)
        self.assertLess(self.catalog.nearest(0,-179.9,30)['items'][0]['distance_km'],30)
    def test_path_and_route_are_grounded(self):
        self.assertEqual(len(self.catalog.path('film:a1','heritage:one')['path']),2)
        route=self.catalog.itinerary(['place:near','heritage:one']);self.assertFalse(route['road_route']);self.assertEqual(route['stops'][0]['id'],'place:near')
    def test_review_versions_validation_audit_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            store=ReviewStore(Path(temp)/'review.sqlite',self.catalog)
            p=dict(song_id='song:one',song='Short Title',film_id='film:a1',place_id='heritage:one',place='Named heritage',source_url='https://example.org/evidence',evidence='The named song was explicitly filmed at this named site.',location_precision='site_reference')
            item=store.propose(p);store.decide(item['id'],1,'approved',payload=p)
            with self.assertRaises(Conflict):store.decide(item['id'],1,'rejected')
            self.assertEqual(len(store.history(item['id'])['items']),1)
            out=Path(temp)/'approved.json';self.assertEqual(store.export(out)['exported'],1)
            for update in [dict(camera_position_verified='false'),dict(latitude='nan',longitude=0),dict(film_id='film:b2')]:
                with self.assertRaises(ValueError):store.validate(dict(p,**update))
            store.decide(item['id'],2,'rejected');self.assertEqual(store.export(out)['exported'],0)
    def test_local_api_rejects_cross_origin_and_missing_token(self):
        import atlas_api
        class Handler:
            def __init__(self,headers,body=b'{}'):
                self.headers=headers;self.path='/api/catalog/itinerary';self.rfile=io.BytesIO(body);self.wfile=io.BytesIO();self.status=None
            def send_response(self,status):self.status=status
            def send_header(self,*args):pass
            def end_headers(self):pass
        previous=atlas_api.API
        try:
            atlas_api.API=atlas_api.AtlasAPI();atlas_api.API.catalog=self.catalog
            for headers in [dict(Host='attacker.example'),dict(Host='127.0.0.1:8769'),dict(Host='127.0.0.1:8769',Origin='https://attacker.example',**{'X-Atlas-Token':atlas_api.API.token})]:
                h=Handler(headers);atlas_api.handle_post(h);self.assertEqual(h.status,403)
            raw=json.dumps(dict(places=['place:near','heritage:one'])).encode()
            h=Handler(dict(Host='127.0.0.1:8769',Origin='http://127.0.0.1:8769',**{'X-Atlas-Token':atlas_api.API.token,'Content-Length':str(len(raw))}),raw);atlas_api.handle_post(h);self.assertEqual(h.status,200);self.assertFalse(json.loads(h.wfile.getvalue())['road_route'])
        finally:atlas_api.API=previous

if __name__=='__main__':unittest.main()
