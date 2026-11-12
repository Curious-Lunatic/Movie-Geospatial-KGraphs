import unittest
from scrape_song_locations import Paragraphs,candidates,wiki_title


class SongScraperTests(unittest.TestCase):
    def setUp(self):
        self.songs=[dict(song_id='song:gerua',title='Gerua')]
        self.places=[dict(place_id='Q189',place_name='Iceland',latitude='65',longitude='-18.6',location_precision='country_reference',aliases='[]')]
    def extract(self,html):
        parser=Paragraphs();parser.feed(html);parser.finish();return candidates(parser.blocks,self.songs,self.places)
    def test_explicit_song_evidence_keeps_precision_and_review_status(self):
        rows=self.extract('<p>The song "Gerua" was filmed in <a href="/wiki/Iceland">Iceland</a>.</p>')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['place_id'],'Q189');self.assertEqual(rows[0]['location_precision'],'country_reference');self.assertEqual(rows[0]['status'],'needs_review')
    def test_film_location_is_not_inherited_from_another_sentence(self):
        self.assertEqual(self.extract('<p>The film was shot in <a href="/wiki/Iceland">Iceland</a>. Gerua appears on the soundtrack.</p>'),[])
    def test_unknown_place_is_not_geocoded_or_invented(self):
        rows=self.extract('<p>Gerua was filmed at <a href="/wiki/Unknown_Cliff">Unknown Cliff</a>.</p>')
        self.assertEqual(rows[0]['place_id'],'');self.assertEqual(rows[0]['latitude'],'');self.assertEqual(rows[0]['identity_match'],'place_needs_identification')
    def test_only_english_wikipedia_source_urls_are_accepted(self):
        self.assertEqual(wiki_title('https://en.wikipedia.org/wiki/Dilwale_(2015_film)'),'Dilwale (2015 film)')
        self.assertIsNone(wiki_title('https://example.org/wiki/Dilwale'));self.assertIsNone(wiki_title('file:///wiki/Dilwale'))


if __name__=='__main__':unittest.main()
