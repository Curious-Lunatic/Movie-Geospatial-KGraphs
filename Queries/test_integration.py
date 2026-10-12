"""Regression cases for erroneous merges, unsupported claims and spatial semantics."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from build_integrated_graph import Integration, Resolver, coordinates, parse_wkt, norm
from query_integrated_graph import nearby, distance_km


class IntegrationTests(unittest.TestCase):
    def test_conflicting_identifiers_do_not_merge_transitively(self):
        records = [dict(ids=ids, source=str(i), row=2, record_id=str(i), title="Same", year=2000)
                   for i, ids in enumerate([{"wikidata": "Q1", "imdb": "tt1"},
                                            {"imdb": "tt1", "tmdb": "5"},
                                            {"tmdb": "5", "wikidata": "Q2"}])]
        issues = []
        groups = Resolver(records, lambda *a: issues.append(a)).resolve()
        self.assertEqual(len(groups), 2)
        self.assertTrue(any(i[0] == "identifier_conflict" for i in issues))
        for group in groups:
            self.assertLessEqual(len({r["ids"]["wikidata"] for r in group if "wikidata" in r["ids"]}), 1)

    def test_remakes_and_duplicate_titles_are_kept_separate(self):
        records = [dict(ids={}, source="wiki", row=i+2, record_id=str(i), title="Same", year=y)
                   for i, y in enumerate([2000, 2000, 2010])]
        issues = []
        self.assertEqual(len(Resolver(records, lambda *a: issues.append(a)).resolve()), 3)
        self.assertEqual(issues[0][0], "ambiguous_title_year")

    def test_title_fallback_checks_alternate_title_component_sources(self):
        records = [dict(ids=ids, source=source, row=i+2, record_id=str(i), title=title, year=2000)
                   for i, (ids, source, title) in enumerate([
                       ({"tmdb": "1"}, "tmdb", "Same"),
                       ({"tmdb": "1"}, "wiki", "Alternate title"),
                       ({}, "wiki", "Same")])]
        issues = []
        groups = Resolver(records, lambda *a: issues.append(a)).resolve()
        self.assertEqual(len(groups), 2)
        self.assertTrue(any(i[0] == "ambiguous_title_year" for i in issues))

    def test_coordinates_and_distance_have_correct_axis_order(self):
        self.assertEqual(parse_wkt("Point(78.04222 27.17417)"), (27.17417, 78.04222))
        self.assertIsNone(coordinates("NaN", "0"))
        self.assertIsNone(coordinates("91", "0"))
        self.assertAlmostEqual(distance_km(0, 0, 0, 1), 111.195080, places=5)
        self.assertEqual(norm("दिल्ली"), "दिल्ली")

    def test_full_merge_preserves_provenance_and_rejects_inherited_song_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, out = Path(tmp) / "Dataset", Path(tmp) / "output"
            data.mkdir()
            def write(name, rows):
                path = data / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8", newline="") as stream:
                    w = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    w.writeheader()
                    w.writerows(rows)
            write("tmdb_movies.csv", [dict(title="Test Film", release_date="2008-01-01", tmdb_id="1", wikidata_id="Q1", imdb_id="tt1")])
            write("bf_2K-25.csv", [dict(title="Test Film", release_year="2008", director="Director", wikipedia_url="")])
            write("filmapia_film_locations.csv", [dict(title="Test Film", release_year="2008", film_type="Movie", filmapia_film_id="2", place_name="Agra Fort -- Agra -- India")])
            write("enriched/films_enriched.csv", [dict(title="Test Film", release_year="2008", film_id="Q1", wikidata_id="Q1")])
            write("enriched/places.csv", [dict(place_id="Q2", place_name="Agra", latitude="27.18", longitude="78.02", globe="", source_url="https://www.wikidata.org/wiki/Q2")])
            write("enriched/location_assertions.csv", [dict(film_id="Q1", relation="filming", place_name="Agra", place_id="Q2", status="text_extracted_review_needed", method="rule", source_url="https://example.org", evidence="Review me", revision_id="", retrieved_at="")])
            write("whc001.csv", [{"ID": "251", "Name EN": "Agra Fort", "Date inscribed": "1983", "Coordinates": "27.179806, 78.021528", "Components": "", "Components Count": "0", "ISO Codes": "IN", "States Names": "India"},
                                {"ID": "252", "Name EN": "Taj Mahal", "Date inscribed": "1983", "Coordinates": "27.17417, 78.04222", "Components": "", "Components Count": "0", "ISO Codes": "IN", "States Names": "India"},
                                {"ID": "927", "Name EN": "Later inscription", "Date inscribed": "2026", "Coordinates": "0, 0", "Components": "", "Components Count": "0", "ISO Codes": "IN", "States Names": "India"}])
            write("songs_2005_2009.csv", [dict(film="Test Film", year="2008", wikidata_id="Q1", song="Test Song", singers="Singer", music="", lyrics="", source_url="https://example.org", song_location_note="", film_filming_locations="Agra Fort"),
                                       dict(film="Test Film", year="2009", wikidata_id="Q1", song="Wrong Year", singers="", music="", lyrics="", source_url="", song_location_note="", film_filming_locations="")])
            pipeline = Integration(data).build()
            pipeline.export(out)
            self.assertEqual(len(pipeline.films), 1)
            self.assertEqual(len(pipeline.songs), 1)
            self.assertEqual(len(pipeline.review_claims), 1)
            self.assertNotIn("heritage:927", pipeline.places)
            self.assertFalse(any(c["subject_id"].startswith("song:") and c["relation"] == "filming" for c in pipeline.claims.values()))
            result = nearby(out, "Taj Mahal")
            self.assertEqual(result[0]["title"], "Test Film")
            self.assertTrue(1 < result[0]["distance_km"] < 3)
            self.assertTrue(result[0]["sources"].startswith("filmapia_film_locations.csv:"))
            self.assertTrue(all(c["source_file"] in pipeline.inputs for c in pipeline.claims.values()))
            self.assertEqual(json.loads((out / "places.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"]["coordinates"], [78.021528, 27.179806])
            first = (out / "graph.ttl").read_bytes()
            Integration(data).build().export(out)
            self.assertEqual(first, (out / "graph.ttl").read_bytes())
            with self.assertRaises(ValueError):
                nearby(out, "Taj Mahal", float("nan"))


if __name__ == "__main__":
    unittest.main()
