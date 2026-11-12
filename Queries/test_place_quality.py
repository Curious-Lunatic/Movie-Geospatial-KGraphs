import json,tempfile,unittest
from pathlib import Path
from place_profiles.apply import apply,classify
from local_place_details import lookup


class PlaceQualityTests(unittest.TestCase):
    def test_classification_preserves_unknown_and_separates_city_and_heritage(self):
        p=dict(coordinate_scope='place_representative_point')
        self.assertEqual(classify(p,dict(instance_of=[dict(label='city')])),'city')
        self.assertEqual(classify(p,dict(instance_of=[dict(label='unrecognised classification')])),'unknown')
        p['coordinate_scope']='heritage_property_representative_point'
        self.assertEqual(classify(p,dict(instance_of=[dict(label='city')])),'heritage_property')

    def test_metadata_adds_no_movie_claims_and_retains_original_coordinates(self):
        from build_integrated_graph import Integration
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'Dataset';data.mkdir();profiles=root/'Queries/place_profiles';profiles.mkdir(parents=True)
            (profiles/'wikidata.json').write_text(json.dumps(dict(records={'Q1352':dict(aliases=['Madras'],source='https://www.wikidata.org/wiki/Q1352',instance_of=[dict(label='city')],countries=['India'])})),encoding='utf-8')
            g=Integration(data);g.add_place('Q1352','Chennai',(13.08,80.27),'place_representative_point');apply(g)
            self.assertEqual(g.places['Q1352']['place_type'],'city');self.assertEqual(g.places['Q1352']['latitude'],13.08)
            self.assertEqual(g.claims,{});self.assertIn('Madras',json.loads(g.places['Q1352']['aliases']))

    def test_local_settlement_context_is_explicit_and_validated(self):
        query=dict(action=['profile'],lat=['13.08'],lng=['80.27'],radius=['5'],category=['landmarks'])
        status,result=lookup(query,records=[[1,'Chennai',13.08,80.27,'India',100,'Asia/Kolkata']])
        self.assertEqual(status,200);self.assertEqual(result['items'][0]['kind'],'Settlement context')
        self.assertIn('not the selected heritage identity',result['source'])
        for value in ['nan','91','bad']:
            with self.assertRaises(ValueError):lookup(dict(query,lat=[value]),records=[])

    def test_live_only_tools_fail_explicitly_without_substituting_a_place(self):
        status,result=lookup(dict(action=['articles'],lat=['13.08'],lng=['80.27'],radius=['5']),records=[])
        self.assertEqual(status,503);self.assertNotIn('items',result)


if __name__=='__main__':unittest.main()
