import csv,json,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import scrape_song_locations_fast as fast


class FastScraperTests(unittest.TestCase):
    def setUp(self):
        self.songs=[dict(song_id='s',title='Example Song',film_id='f')]
        self.places=[dict(place_id='Q83786',place_name='Shimla',latitude='31.1',longitude='77.2',location_precision='locality_reference',aliases='["Simla"]')]
    def test_plain_text_and_old_alias_preserve_city_precision(self):
        matcher=fast.Matcher(self.places)
        rows=matcher.extract(fast.wikitext_blocks('The song "Example Song" was filmed in Simla.'),self.songs)
        self.assertEqual(rows[0]['place_id'],'Q83786');self.assertEqual(rows[0]['location_precision'],'locality_reference');self.assertEqual(rows[0]['status'],'needs_review')
    def test_no_inheritance_from_film_location_sentence(self):
        rows=fast.Matcher(self.places).extract(fast.wikitext_blocks('The film was shot in [[Shimla]]. Example Song is on the soundtrack.'),self.songs)
        self.assertEqual(rows,[])
    def test_batch_revisions_resolve_normalized_titles_and_redirects(self):
        body=dict(query=dict(normalized=[dict(**{'from':'Film_A','to':'Film A'})],redirects=[dict(**{'from':'Film A','to':'Canonical Film'})],pages=[dict(title='Canonical Film',revisions=[dict(revid=42,slots=dict(main=dict(content='The song "Example Song" was shot in [[Shimla]].')))]),dict(title='Missing',missing=True)]))
        result=fast.decode_batch(body,['Film_A','Missing'],'hash');self.assertEqual(set(result),{'Film_A'});self.assertEqual(result['Film_A']['revision_id'],42)
        self.assertEqual(result['Film_A']['blocks'][0]['links'][0]['title'],'Shimla')
    def test_legacy_output_tree_is_protected(self):
        for out in [fast.LEGACY,fast.LEGACY/'cache',fast.LEGACY.parent]:
            with self.assertRaises(ValueError):fast.protect_output(out)
        fast.protect_output(fast.LEGACY.parent/'song-location-fast')
    def test_ambiguous_place_alias_remains_for_review(self):
        places=self.places+[dict(self.places[0],place_id='other',place_name='Another Shimla',aliases='["Simla"]')]
        rows=fast.Matcher(places).extract([dict(text='The song Example Song was filmed in Simla.',links=[])],self.songs)
        self.assertEqual(len(rows),2);self.assertTrue(all(r['identity_match']=='ambiguous_alias' for r in rows))
    def test_tmdb_country_is_context_only_and_cached_mode_makes_no_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'Queries').mkdir();(root/'Queries/tmdb_details.jsonl').write_text(json.dumps(dict(id=123,title='Film',production_countries=[dict(name='India')]))+'\n',encoding='utf-8')
            out=root/'out';out.mkdir()
            with patch.object(fast,'ROOT',root):result=fast.tmdb_context({'f':dict(tmdb_id='123',imdb_id='tt123')},out,None)
            self.assertEqual(result['cached_context_rows'],1);self.assertEqual(result['fetched'],0)
            row=fast.read(out/'tmdb_context.csv')[0];self.assertEqual(row['scope'],'film_metadata_only');self.assertNotIn('place_id',row)
    def test_imdb_import_requires_exact_film_and_song_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'authorized.csv';fields=['imdb_id','song','place','source_url','evidence']
            valid=dict(imdb_id='tt123',song='Example Song',place='Shimla',source_url='https://www.imdb.com/title/tt123/locations/',evidence='The authorized evidence explicitly names the song and place.')
            fast.write_csv(path,[valid,dict(valid,song=''),dict(valid,source_url='https://example.org/title/tt123/locations/')],fields)
            rows=fast.imdb_import(path,{'f':dict(imdb_id='tt123',title='Film',release_year='2006')},{'f':self.songs},self.places)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'needs_review');self.assertEqual(rows[0]['source'],'IMDb authorized export')
    def test_provider_denial_stops_without_leaking_api_key(self):
        error=urllib.error.HTTPError('https://api.themoviedb.org/3/movie/1?api_key=SECRET',403,'Denied',{},None)
        with patch.object(fast.urllib.request,'urlopen',side_effect=error):
            with self.assertRaises(fast.AccessStopped) as caught:fast.Client(0).get(error.url)
        self.assertNotIn('SECRET',str(caught.exception));self.assertIn('403',str(caught.exception))
    def test_generic_place_names_and_film_title_matches_are_excluded(self):
        generic=[dict(place_id='bad',place_name='The ',aliases='[]')]
        self.assertEqual(fast.Matcher(generic).extract([dict(text='The song Example Song was shot.',links=[])],self.songs)[0]['place_id'],'')
        self.assertEqual(fast.Matcher(self.places).extract([dict(text='Example Song was shot in Shimla.',links=[])],self.songs),[])
    def test_place_in_song_title_does_not_become_a_filming_location(self):
        songs=[dict(song_id='s',title='Shimla Star',film_id='f')]
        rows=fast.Matcher(self.places).extract([dict(text='The song "Shimla Star" was shot for a promotional video.',links=[])],songs)
        self.assertEqual(rows,[])


if __name__=='__main__':unittest.main()
