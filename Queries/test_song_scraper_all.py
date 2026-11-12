import unittest
from collections import defaultdict
from pathlib import Path
import scrape_song_locations_all as all_sources


class GlobalSongScraperTests(unittest.TestCase):
    def test_every_filming_place_is_ranked_without_a_manual_place(self):
        places=[dict(place_id='city',place_name='Shimla',aliases='["Simla"]'),dict(place_id='site',place_name='Example Fort',aliases='[]')]
        claims=[dict(relation='filming',object_id='city',subject_id='f1'),dict(relation='filming',object_id='city',subject_id='f1'),dict(relation='filming',object_id='city',subject_id='f2'),dict(relation='filming',object_id='site',subject_id='f3')]
        ranked=all_sources.location_ranking(places,claims)
        self.assertEqual([(p['name'],p['film_count']) for p in ranked],[('Shimla',2),('Example Fort',1)])
        self.assertEqual(ranked[0]['aliases'],['Simla'])
    def test_discovery_is_bidirectional_and_covers_all_known_songs(self):
        by_song={'one':[dict(song_id='s1',title='One Song',film_id='f')],'two':[dict(song_id='s2',title='Two Song',film_id='f')]}
        tasks=all_sources.query_tasks([dict(name='Shimla',aliases=['Simla'])],by_song,{'f':dict(title='A Film')})
        self.assertEqual({t['song_id'] for t in tasks if t['direction']=='song_to_locations'},{'s1','s2'})
        self.assertEqual(sum(t['direction']=='location_to_songs' for t in tasks),2)
        self.assertEqual(tasks[0]['direction'],'location_to_songs');self.assertEqual(tasks[1]['direction'],'song_to_locations')
    def test_song_pages_cover_both_qualified_and_plain_titles(self):
        self.assertEqual(all_sources.song_pages({'track':[dict(title='Example Track')]}),['Example Track (song)','Example Track'])
    def test_explicitly_named_new_song_is_retained_with_film_scoped_identity(self):
        blocks=[dict(text='The song "New Track" was filmed at Example Fort.')]
        rows=all_sources.new_song_mentions(blocks,'film:one',[])
        self.assertEqual(rows[0]['title'],'New Track');self.assertTrue(rows[0]['new_song'])
        self.assertEqual(all_sources.new_song_mentions(blocks,'film:one',rows),[])
        self.assertNotEqual(rows[0]['song_id'],all_sources.new_song_mentions(blocks,'film:two',[])[0]['song_id'])
    def test_song_page_requires_an_identifiable_film_connection(self):
        song={'track':[dict(film_id='f')]};jobs={'A Film':{'f'}}
        self.assertEqual(all_sources.resolve_page_films('Track (song)',dict(linked_pages=['A Film']),jobs,song),{'f'})
        self.assertEqual(all_sources.resolve_page_films('Track (song)',dict(linked_pages=['Different Film']),jobs,song),set())
    def test_coordinate_lookup_preserves_reference_precision(self):
        row=dict(site_article='Example Fort',latitude='',longitude='',place_id='')
        body=dict(query=dict(pages=[dict(title='Example Fort',pageprops=dict(wikibase_item='Q123'),coordinates=[dict(lat=31.1,lon=77.2,globe='earth')])]))
        all_sources.attach_coordinates([row],body,{})
        self.assertEqual(row['coordinate_role'],'linked_place_representative_point');self.assertEqual(row['location_precision'],'unknown_reference');self.assertEqual(row['place_id'],'Q123')
    def test_only_explicit_source_coordinates_are_reported_separately(self):
        row=dict(place_id='city',place='Shimla',latitude='31.1',longitude='77.2',source_url='https://example.org/song',evidence='The song was filmed at 31.1048 N, 77.1734 E.')
        result=all_sources.decorate(row,{'city':dict(coordinate_source='https://example.org/city')})
        self.assertEqual(result['reported_latitude'],31.1048);self.assertEqual(result['latitude'],'31.1');self.assertEqual(result['reported_coordinate_source'],'https://example.org/song')
        self.assertIsNone(all_sources.explicit_coordinates('Filmed at Shimla.'));self.assertIsNone(all_sources.explicit_coordinates('91 N, 200 E'))
    def test_both_existing_scraper_output_trees_are_protected(self):
        for path in [all_sources.LEGACY,all_sources.LEGACY/'cache',all_sources.FAST,all_sources.FAST/'wiki-cache']:
            with self.assertRaises(ValueError):all_sources.protect_all_output(path)
        all_sources.protect_all_output(all_sources.ROOT/'outputs/song-location-all')
    def test_coordinate_enrichment_cannot_duplicate_a_site_on_resume(self):
        row=dict(song_id='s',place_id='',site_article='Example Fort',source_url='https://example.org/song',evidence='The song was filmed at Example Fort.')
        self.assertEqual(all_sources.row_marker(row),all_sources.row_marker(dict(row,place_id='Q123')))


if __name__=='__main__':unittest.main()
