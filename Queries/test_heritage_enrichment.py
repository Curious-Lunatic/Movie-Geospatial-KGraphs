import unittest
from pathlib import Path
import tempfile
from build_integrated_graph import Integration, norm


class HeritageMatchingTests(unittest.TestCase):
    def test_alias_requires_same_site_and_country(self):
        graph = Integration(Path('/tmp'))
        graph.heritage_aliases[norm('Humayuns Tomb')] = dict(heritage_id='heritage:232', country='India')
        self.assertEqual(graph.place('Humayuns Tomb', 'Humayuns Tomb -- Delhi -- India'), 'heritage:232')
        self.assertNotEqual(graph.place('Humayuns Tomb', 'Humayuns Tomb -- Another country'), 'heritage:232')
        self.assertNotEqual(graph.place('Delhi'), 'heritage:232')

    def test_component_stays_component(self):
        graph = Integration(Path('/tmp'))
        graph.heritage_aliases[norm('Darjeeling Toy Train')] = dict(
            heritage_id='heritage-component:944ter-001', country='India')
        self.assertEqual(graph.place('Darjeeling Toy Train'), 'heritage-component:944ter-001')
        self.assertNotEqual(graph.place('Darjeeling'), 'heritage-component:944ter-001')


if __name__ == '__main__':
    unittest.main()
