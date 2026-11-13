import json,tempfile,unittest
from pathlib import Path
from build_integrated_graph import Integration
from song_locations.apply import apply_places


class ReviewedSongPlaceTests(unittest.TestCase):
    def test_reviewed_place_adds_no_movie_claim_and_keeps_existing_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reviewed_places.json';g=Integration(Path(directory));g.add_place('Q1','Old name',(10,20),'place_representative_point','https://example.org/original')
            record=dict(name='Named Site',kind='venue',precision='site_reference',latitude=30,longitude=40,coordinate_source='https://example.org/site',identity_source='https://example.org/site',review_note='Representative site reference.',country='')
            path.write_text(json.dumps(dict(records={'Q1':record,'Q2':record})),encoding='utf-8');apply_places(g,path)
            self.assertEqual(g.places['Q1']['latitude'],10);self.assertEqual(g.places['Q2']['latitude'],30);self.assertEqual(g.claims,{})
            self.assertEqual(g.place_quality['reviewed_song_place_records'],2)
    def test_reviewed_coordinates_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reviewed_places.json';g=Integration(Path(directory))
            record=dict(name='Bad Site',kind='venue',precision='site_reference',latitude=91,longitude=40,coordinate_source='https://example.org/site',identity_source='https://example.org/site',review_note='Invalid',country='')
            path.write_text(json.dumps(dict(records={'Q2':record})),encoding='utf-8')
            with self.assertRaises(ValueError):apply_places(g,path)


if __name__=='__main__':unittest.main()
