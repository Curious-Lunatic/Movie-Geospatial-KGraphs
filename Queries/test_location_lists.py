import unittest
from bs4 import BeautifulSoup
from enrich_from_location_lists import extract, page_key


class LocationListTests(unittest.TestCase):
    def test_category_excludes_subcategories_and_navigation(self):
        soup = BeautifulSoup('''<div id="mw-subcategories"><a href="/wiki/Category:Other">Other</a></div>
        <div id="mw-pages"><a href="/wiki/Help">Help</a><div class="mw-category-group">
        <ul><li><a href="/wiki/Test_(2001_film)">Test</a></li></ul></div></div>''', 'html.parser')
        rows = extract(soup, 'category')
        self.assertEqual([page_key(a['href']) for a, text in rows], ['Test (2001 film)'])

    def test_list_stops_before_tv_and_ignores_place_links(self):
        soup = BeautifulSoup('''<h2 id="Films">Films</h2><ul><li><a href="/wiki/Test">Test</a>
        at <a href="/wiki/Jaipur">Jaipur</a></li></ul><h2>OTT Platforms</h2>
        <ul><li><a href="/wiki/TV_show">TV show</a></li></ul>''', 'html.parser')
        self.assertEqual([page_key(a['href']) for a, text in extract(soup, 'list', 'Films')], ['Test'])

    def test_film_identity_keeps_disambiguation(self):
        self.assertNotEqual(page_key('/wiki/Don_(1978_film)'), page_key('/wiki/Don_(2006_film)'))
        self.assertEqual(page_key('https://en.wikipedia.org/wiki/Delhi-6#Production'), 'Delhi-6')


if __name__ == '__main__':
    unittest.main()
