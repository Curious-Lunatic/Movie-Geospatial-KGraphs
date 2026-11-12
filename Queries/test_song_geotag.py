import copy,unittest
from validate_song_geotag import validate

class SongGeotagTests(unittest.TestCase):
    def setUp(self):
        self.draft=dict(song_id='song:one',place_name='Railway',latitude=13,longitude=80,source_url='https://example.org/song',evidence='This evidence explicitly identifies the song and railway.',location_precision='route_reference',scene_timestamp='00:01:23',status='proposed')
    def test_valid_remains_proposed(self):
        self.assertEqual(validate(self.draft,{'song:one'})['status'],'proposed')
    def test_invalid_or_unreviewed_evidence_cannot_be_accepted(self):
        for patch in [dict(song_id='unknown'),dict(latitude=True),dict(longitude=float('nan')),dict(source_url='file:///tmp/song'),dict(source_url='https://user:secret@example.org'),dict(evidence='short'),dict(scene_timestamp='00:99:23'),dict(location_precision='exact'),dict(status='source_supported')]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):validate(dict(self.draft,**patch),{'song:one'})
    def test_validation_does_not_mutate_proposal(self):
        original=copy.deepcopy(self.draft);validate(self.draft,{'song:one'});self.assertEqual(self.draft,original)

if __name__=='__main__':unittest.main()
