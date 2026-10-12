#!/usr/bin/env python3
"""Offline, provenance-preserving integration of the team's supplied datasets.

Python 3.9+; standard library only. Run from any directory. Original inputs
are never changed. See Docs/INTEGRATION_METHOD.md for assumptions and limits.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
NS = "https://w3id.org/gwm/"
REPO = "https://github.com/Curious-Lunatic/Movie-Geospatial-KGraphs/blob/main/Dataset/"
FILM_SOURCES = ["enriched/films_enriched.csv", "tmdb_movies.csv",
                "wikidata_movies.csv", "bf_2K-25.csv",
                "bollywood_films_1970_2000.csv", "movies_with_locations.csv",
                "filmapia_film_locations.csv"]


def norm(value):
    """Unicode-aware exact normalized label; never transliterate/fuzzy-match."""
    value = unicodedata.normalize("NFKC", value).casefold()
    # Python \w omits combining marks used by Hindi and other scripts.
    return " ".join("".join(c if unicodedata.category(c)[0] in "LMN" else " "
                            for c in value).split())


def key(prefix, *parts):
    # Length-safe encoding distinguishes ('a|b','c') from ('a','b|c').
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + ":" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def year(value):
    match = re.match(r"^(\d{4})(?:$|[-/])", str(value).strip())
    return int(match[1]) if match else None


def coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (ValueError, TypeError):
        pass
    return None


def parse_latlon(value):
    bits = value.split(",")
    return coordinates(*bits) if len(bits) == 2 else None


def parse_wkt(value):
    # Wikidata POINT uses longitude latitude, unlike UNESCO Coordinates.
    match = re.fullmatch(r"\s*(?:<[^>]+>\s*)?Point\s*\(\s*([-+\deE.]+)\s+([-+\deE.]+)\s*\)\s*", value, re.I)
    return coordinates(match[2], match[1]) if match else None


def film_ids(row):
    result = {}
    for field, kind, pattern in [("wikidata_id", "wikidata", r"Q\d+"),
                                  ("imdb_id", "imdb", r"tt\d+"),
                                  ("tmdb_id", "tmdb", r"\d+"),
                                  ("filmapia_film_id", "filmapia", r"\d+")]:
        value = row.get(field, "").strip()
        if re.fullmatch(pattern, value):
            result[kind] = value
    url = row.get("wikipedia_url", "").strip()
    if urlsplit(url).hostname == "en.wikipedia.org" and "/wiki/" in url:
        result["wikipedia"] = unquote(urlsplit(url).path.split("/wiki/", 1)[1]).replace("_", " ")
    return result


class Resolver:
    """Constrained union: a component cannot contain conflicting strong IDs."""
    def __init__(self, records, issue):
        self.records, self.issue = records, issue
        self.parent = list(range(len(records)))
        self.ids = [{k: {v} for k, v in r["ids"].items()} for r in records]
        self.sources = [{r["source"]} for r in records]

    def find(self, i):
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def compatible(self, a, b):
        a, b = self.find(a), self.find(b)
        return all(not (self.ids[a].get(k) and self.ids[b].get(k)) or
                   self.ids[a][k] == self.ids[b][k] for k in set(self.ids[a]) | set(self.ids[b]))

    def merge(self, a, b, method):
        a, b = self.find(a), self.find(b)
        if a == b:
            return True
        if not self.compatible(a, b):
            self.issue("identifier_conflict", self.records[b]["source"], self.records[b]["row"],
                       "Refused " + method + " merge with " + self.records[a]["record_id"])
            return False
        a, b = min(a, b), max(a, b)
        self.parent[b] = a
        self.sources[a].update(self.sources[b])
        for kind, values in self.ids[b].items():
            self.ids[a].setdefault(kind, set()).update(values)
        return True

    def resolve(self):
        index = collections.defaultdict(list)
        for i, record in enumerate(self.records):
            for kind, value in record["ids"].items():
                index[(kind, value)].append(i)
        for identity in sorted(index):
            members = index[identity]
            for i in members[1:]:
                self.merge(members[0], i, "shared " + identity[0])
        labels = collections.defaultdict(list)
        for i, record in enumerate(self.records):
            if record["year"] is not None and norm(record["title"]):
                labels[(norm(record["title"]), record["year"])].append(i)
        for label in sorted(labels):
            members = labels[label]
            roots = sorted({self.find(i) for i in members})
            if len(roots) < 2:
                continue
            by_source = collections.defaultdict(set)
            # Check complete components, including records with alternate titles.
            for root in roots:
                for source in self.sources[root]:
                    by_source[source].add(root)
            if any(len(v) > 1 for v in by_source.values()) or any(
                    not self.compatible(a, b) for a in roots for b in roots if a < b):
                self.issue("ambiguous_title_year", "identity_resolution", "", repr(label))
                continue
            for i in roots[1:]:
                self.merge(roots[0], i, "unique normalized title and year")
        groups = collections.defaultdict(list)
        for i, record in enumerate(self.records):
            groups[self.find(i)].append(record)
        return list(groups.values())


class Integration:
    def __init__(self, data, start=2000, end=2025, heritage_cutoff=2025):
        self.data, self.start, self.end, self.cutoff = Path(data), start, end, heritage_cutoff
        self.inputs, self.issues, self.crosswalk, self.films = {}, [], [], {}
        self.attributes = []
        self.places, self.people, self.songs, self.claims = {}, {}, {}, {}
        self.review_claims = []
        self.source_to_film = {}
        self.id_index, self.title_index = collections.defaultdict(set), collections.defaultdict(set)
        self.place_index = collections.defaultdict(set)
        self.heritage_index = collections.defaultdict(set)

    def issue(self, kind, source, row, detail):
        self.issues.append(dict(kind=kind, source_file=source, source_row=row, detail=detail))

    def read(self, name):
        path = self.data / name
        if not path.exists():
            self.issue("missing_source", name, "", "Input absent; not downloaded or invented")
            return []
        raw = path.read_bytes()
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            if any(None in row for row in rows):
                raise ValueError("Extra CSV fields: " + name)
            rows = [{k: (v or "").strip() for k, v in row.items()} for row in rows]
        self.inputs[name] = dict(rows=len(rows), sha256=hashlib.sha256(raw).hexdigest())
        return rows

    def build_films(self):
        records = []
        self.raw_films = {}
        for source in FILM_SOURCES:
            rows = self.read(source)
            self.raw_films[source] = rows
            for number, row in enumerate(rows, 2):
                if source.startswith("filmapia") and row.get("film_type") != "Movie":
                    continue
                if not row.get("title"):
                    self.issue("missing_title", source, number, "Cannot resolve film")
                    continue
                records.append(dict(record_id=source + ":" + str(number), source=source,
                                    row=number, title=row["title"],
                                    year=year(row.get("release_year") or row.get("release_date", "")),
                                    ids=film_ids(row), raw=row))
        for group in Resolver(records, self.issue).resolve():
            identifiers = sorted({(k, v) for r in group for k, v in r["ids"].items()})
            fid = key("film", identifiers or sorted(r["record_id"] for r in group))
            years = sorted({r["year"] for r in group if r["year"] is not None})
            release = min(years) if years else None
            in_scope = release is not None and self.start <= release <= self.end
            if len(years) > 1:
                self.issue("release_year_disagreement", "identity_resolution", "", fid + ": " + str(years))
            if in_scope:
                ids = dict(identifiers)
                self.films[fid] = dict(film_id=fid, title=group[0]["title"], release_year=release,
                    observed_years="|".join(map(str, years)), wikidata_id=ids.get("wikidata", ""),
                    imdb_id=ids.get("imdb", ""), tmdb_id=ids.get("tmdb", ""),
                    filmapia_id=ids.get("filmapia", ""), sources="|".join(sorted({r["source"] for r in group})))
                for record in group:
                    for field, value in record["raw"].items():
                        if value:
                            self.attributes.append(dict(film_id=fid, field=field, value=value,
                                source_file=record["source"], source_row=record["row"]))
            for record in group:
                self.crosswalk.append(dict(source_file=record["source"], source_row=record["row"],
                    source_title=record["title"], source_year=record["year"],
                    film_id=fid, scope="included" if in_scope else "outside_year_scope"))
                if in_scope:
                    self.source_to_film[record["record_id"]] = fid
                    for identity in record["ids"].items():
                        self.id_index[identity].add(fid)
                    if record["year"] is not None:
                        self.title_index[(norm(record["title"]), record["year"])].add(fid)
                    old_id = record["raw"].get("film_id")
                    if old_id:
                        self.id_index[("enriched", old_id)].add(fid)

    def lookup(self, kind, value):
        hits = self.id_index.get((kind, value), set())
        return next(iter(hits)) if len(hits) == 1 else None

    def add_place(self, pid, name, coord=None, scope="unresolved", source_url="", **extra):
        if pid not in self.places:
            self.places[pid] = dict(place_id=pid, place_name=name, latitude=coord[0] if coord else "",
                longitude=coord[1] if coord else "", coordinate_scope=scope, coordinate_source=source_url,
                heritage_parent_id="", country_codes="", country_names="", inscription_year="", **extra)
            self.place_index[norm(name)].add(pid)
        return pid

    def build_places(self):
        for number, row in enumerate(self.read("whc001.csv"), 2):
            inscribed = year(row.get("Date inscribed", ""))
            if inscribed is None or inscribed > self.cutoff:
                continue
            uid, name = row.get("ID", ""), row.get("Name EN", "")
            if not uid or not name:
                self.issue("invalid_heritage", "whc001.csv", number, "Missing ID or name")
                continue
            pid = "heritage:" + uid
            url = "https://whc.unesco.org/en/list/" + quote(uid) + "/"
            point = parse_latlon(row.get("Coordinates", ""))
            self.add_place(pid, name, point, "heritage_property_representative_point", url)
            extra = dict(country_codes=row.get("ISO Codes", ""), country_names=row.get("States Names", ""),
                         inscription_year=inscribed)
            self.places[pid].update(extra)
            self.heritage_index[norm(name)].add(pid)
            components = re.findall(r"\{name:\s*(.*?),\s*ref:\s*(.*?),\s*latitude:\s*([-+\deE.]+),\s*longitude:\s*([-+\deE.]+)\s*\}", row.get("Components", ""))
            expected = int(row.get("Components Count") or "0")
            if len(components) != expected:
                self.issue("heritage_component_parse", "whc001.csv", number,
                           "Parsed %d of %d components" % (len(components), expected))
            for label, ref, lat, lon in components:
                if ref == uid:  # single component is the property itself
                    if not point and coordinates(lat, lon):
                        self.places[pid].update(latitude=float(lat), longitude=float(lon))
                    continue
                cid = "heritage-component:" + ref
                self.add_place(cid, label, coordinates(lat, lon), "heritage_component_representative_point", url)
                self.places[cid].update(extra, heritage_parent_id=pid)
                self.heritage_index[norm(label)].add(cid)
        for number, row in enumerate(self.read("enriched/places.csv"), 2):
            pid = row.get("place_id", "")
            if not pid:
                continue
            coord = coordinates(row.get("latitude"), row.get("longitude"))
            if row.get("globe") and row["globe"].casefold() != "earth" and not row["globe"].endswith("Q2"):
                coord = None
                self.issue("non_earth_coordinate", "enriched/places.csv", number, pid)
            self.add_place(pid, row["place_name"], coord,
                "place_representative_point" if coord else "unresolved", row.get("source_url", ""))

    def place(self, label, context="", coord=None, coordinate_source=""):
        heritage = self.heritage_index.get(norm(label), set())
        if context:
            country = context.split(" -- ")[-1]
            heritage = {p for p in heritage if norm(country) in
                        {norm(c) for c in re.split(r"[,;|]", self.places[p]["country_names"])}}
        # An exact property/component label may be linked. A city near a property
        # is never given the property's identity or coordinates.
        if len(heritage) == 1:
            return next(iter(heritage))
        known = self.place_index.get(norm(label), set()) if not context else set()
        if len(known) == 1:
            pid = next(iter(known))
            if coord and self.places[pid]["latitude"] == "":
                self.places[pid].update(latitude=coord[0], longitude=coord[1],
                    coordinate_scope="place_representative_point", coordinate_source=coordinate_source)
            return pid
        pid = key("place", norm(label), norm(context))
        return self.add_place(pid, label, coord, "place_representative_point" if coord else "unresolved",
                              coordinate_source)

    def claim(self, subject, relation, obj, source, row, method, url="", status="source_supported", evidence=""):
        if not subject or not obj:
            return
        cid = key("claim", subject, relation, obj, source, str(row), method)
        self.claims[cid] = dict(claim_id=cid, subject_id=subject, relation=relation, object_id=obj,
            source_file=source, source_row=row, source_url=url, method=method, status=status,
            evidence=evidence, revision_id="", retrieved_at="")

    def build_locations(self):
        source = "enriched/location_assertions.csv"
        for number, row in enumerate(self.read(source), 2):
            fid = self.lookup("enriched", row["film_id"])
            if not fid:
                continue
            if row.get("status") != "source_supported" or row.get("relation") not in ("filming", "narrative"):
                self.review_claims.append(dict(row, canonical_film_id=fid, source_row=number))
                continue
            pid = row.get("place_id")
            if pid not in self.places:
                pid = self.place(row["place_name"])
            self.claim(fid, row["relation"], pid, source, number, row["method"], row["source_url"], evidence=row["evidence"])
            cid = key("claim", fid, row["relation"], pid, source, str(number), row["method"])
            self.claims[cid].update(revision_id=row.get("revision_id", ""), retrieved_at=row.get("retrieved_at", ""))
        for source in ["wikidata_movies.csv", "bollywood_films_1970_2000.csv", "filmapia_film_locations.csv"]:
            for number, row in enumerate(self.raw_films[source], 2):
                fid = self.source_to_film.get(source + ":" + str(number))
                if not fid:
                    continue
                url = "https://www.wikidata.org/wiki/" + row["wikidata_id"] if row.get("wikidata_id") else ""
                if source.startswith("filmapia"):
                    for full in filter(None, map(str.strip, row.get("place_name", "").split("|"))):
                        label = full.split(" -- ")[0]
                        pid = self.place(label, context=full)
                        self.claim(fid, "filming", pid, source, number, "filmapia_existing_snapshot",
                                   evidence=full)
                    continue
                for relation in ("filming", "narrative"):
                    value = row.get(relation + "_location", "")
                    if not value:
                        continue
                    labels, raw_coords = value.split("|"), row.get(relation + "_coordinates", "").split("|")
                    for position, label in enumerate(labels):
                        label = label.strip()
                        if not label:
                            continue
                        coord = parse_wkt(raw_coords[position]) if len(labels) == len(raw_coords) else None
                        pid = self.place(label, coord=coord, coordinate_source=url)
                        self.claim(fid, relation, pid, source, number, "wikidata_existing_snapshot", url)
        # run.py retained unsuffixed labels in its cache; use those rather than
        # interpreting display strings such as 'Mumbai (India)' as new places.
        cache_path = self.data / "wikidata_cache.json"
        if cache_path.exists():
            raw = cache_path.read_bytes()
            cache = json.loads(raw.decode("utf-8-sig"))
            self.inputs["wikidata_cache.json"] = dict(rows=len(cache), sha256=hashlib.sha256(raw).hexdigest())
            for qid, relations in sorted(cache.items()):
                fid = self.lookup("wikidata", qid)
                if fid:
                    for relation in ("filming", "narrative"):
                        for label in sorted(relations.get(relation, {})):
                            self.claim(fid, relation, self.place(label), "wikidata_cache.json", qid,
                                       "wikidata_existing_snapshot", "https://www.wikidata.org/wiki/" + qid)
        else:
            self.issue("missing_source", "wikidata_cache.json", "", "No cache; formatted locations retained only in source inputs")

    def build_credits(self):
        for source, relation in [("tmdb_cast.csv", "cast_member"), ("tmdb_directors.csv", "director")]:
            for number, row in enumerate(self.read(source), 2):
                fid = self.lookup("tmdb", row.get("tmdb_id", ""))
                person = row.get("person_id", "")
                if not fid or not person:
                    continue
                pid = "person:tmdb:" + person
                self.people[pid] = dict(person_id=pid, name=row.get("name", ""), tmdb_person_id=person)
                self.claim(fid, relation, pid, source, number, "tmdb_credit_snapshot",
                           "https://www.themoviedb.org/movie/" + row["tmdb_id"], evidence=row.get("character", ""))

    def build_songs(self):
        for source in ["songs_2000_2004.csv", "songs_2005_2009.csv"]:
            for number, row in enumerate(self.read(source), 2):
                sy = year(row.get("year", ""))
                fid = self.lookup("wikidata", row.get("wikidata_id", ""))
                if not fid:
                    hits = self.title_index.get((norm(row.get("film", "")), sy), set())
                    fid = next(iter(hits)) if len(hits) == 1 else None
                if not fid or sy != self.films[fid]["release_year"]:
                    self.issue("unresolved_song_film", source, number,
                               row.get("film", "") + ": identifier missing/ambiguous, outside scope, or year disagreement")
                    continue
                title = row.get("song", "")
                if not title:
                    continue
                sid = key("song", fid, norm(title))
                self.songs.setdefault(sid, dict(song_id=sid, title=title, film_id=fid, singers=row.get("singers", ""),
                                                music=row.get("music", ""), lyrics=row.get("lyrics", "")))
                self.claim(sid, "in_film", fid, source, number, "wikipedia_song_table_snapshot", row.get("source_url", ""))
                if row.get("song_location_note"):
                    self.issue("song_location_needs_review", source, number, row["song_location_note"])
                # Film locations do not prove that this particular song was shot there.
        for number, row in enumerate(self.read("bollywood_songs_1970_2026.csv"), 2):
            sy = year(row.get("release_date", ""))
            if sy is not None and self.start <= sy <= self.end:
                self.issue("standalone_song_needs_mapping", "bollywood_songs_1970_2026.csv", number,
                           row.get("title", "") + ": part_of has no validated film identity")

    def validate(self):
        nodes = set(self.films) | set(self.places) | set(self.people) | set(self.songs)
        for claim in self.claims.values():
            if claim["subject_id"] not in nodes or claim["object_id"] not in nodes:
                raise ValueError("Dangling graph edge: " + claim["claim_id"])
            if claim["status"] != "source_supported" or claim["source_file"] not in self.inputs:
                raise ValueError("Unprovenanced graph edge: " + claim["claim_id"])
        for place in self.places.values():
            if place["latitude"] != "" and not coordinates(place["latitude"], place["longitude"]):
                raise ValueError("Invalid coordinate: " + place["place_id"])
        return True

    def build(self):
        self.build_films()
        self.build_places()
        self.build_locations()
        self.build_credits()
        self.build_songs()
        self.validate()
        return self

    def summary(self):
        locations = [c for c in self.claims.values() if c["relation"] in ("filming", "narrative")]
        return dict(year_range=[self.start, self.end], heritage_inscribed_by=self.cutoff,
            films=len(self.films), songs=len(self.songs), people=len(self.people), places=len(self.places),
            heritage_properties=sum(p.startswith("heritage:") for p in self.places),
            heritage_components=sum(p.startswith("heritage-component:") for p in self.places),
            claims=len(self.claims), location_claims=len(locations),
            source_attributes=len(self.attributes),
            films_with_filming_locations=len({c["subject_id"] for c in locations if c["relation"] == "filming"}),
            films_with_narrative_locations=len({c["subject_id"] for c in locations if c["relation"] == "narrative"}),
            geocoded_places=sum(p["latitude"] != "" for p in self.places.values()),
            review_only_location_claims=len(self.review_claims),
            issue_counts=dict(sorted(collections.Counter(i["kind"] for i in self.issues).items())),
            sources=self.inputs)

    def export(self, out):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        tables = {
            "films.csv": (self.films.values(), "film_id,title,release_year,observed_years,wikidata_id,imdb_id,tmdb_id,filmapia_id,sources"),
            "places.csv": (self.places.values(), "place_id,place_name,latitude,longitude,coordinate_scope,coordinate_source,heritage_parent_id,country_codes,country_names,inscription_year"),
            "people.csv": (self.people.values(), "person_id,name,tmdb_person_id"),
            "songs.csv": (self.songs.values(), "song_id,title,film_id,singers,music,lyrics"),
            "claims.csv": (self.claims.values(), "claim_id,subject_id,relation,object_id,source_file,source_row,source_url,method,status,evidence,revision_id,retrieved_at"),
            "film_crosswalk.csv": (self.crosswalk, "source_file,source_row,source_title,source_year,film_id,scope"),
            "film_attributes.csv": (self.attributes, "film_id,field,value,source_file,source_row"),
            "issues.csv": (self.issues, "kind,source_file,source_row,detail"),
            "location_review.csv": (self.review_claims, "canonical_film_id,film_id,relation,place_name,place_id,method,source_url,evidence,status,revision_id,retrieved_at,source_row")}
        for name, (rows, fields) in tables.items():
            with (out / name).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields.split(","), extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
        features = []
        for place in self.places.values():
            if place["latitude"] != "":
                features.append(dict(type="Feature", id=place["place_id"], properties=place,
                    geometry=dict(type="Point", coordinates=[place["longitude"], place["latitude"]])))
        (out / "places.geojson").write_text(json.dumps(dict(type="FeatureCollection", features=features),
                                                     ensure_ascii=False), encoding="utf-8")
        (out / "summary.json").write_text(json.dumps(self.summary(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.export_rdf(out / "graph.ttl")

    def export_rdf(self, path):
        def iri(identifier):
            return "<" + NS + "entity/" + quote(identifier, safe="") + ">"
        def lit(value):
            return json.dumps(str(value), ensure_ascii=False)
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write('@prefix gwm: <https://w3id.org/gwm/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n@prefix geo: <http://www.opengis.net/ont/geosparql#> .\n@prefix prov: <http://www.w3.org/ns/prov#> .\n')
            for name, info in sorted(self.inputs.items()):
                stream.write(iri("source:" + name) + ' a prov:Entity ; gwm:sha256 ' + lit(info["sha256"]) +
                             ' ; rdfs:seeAlso <' + REPO + quote(name, safe="/") + '> .\n')
            for fid, film in self.films.items():
                stream.write(iri(fid) + ' a gwm:Film ; rdfs:label ' + lit(film["title"]) +
                             ' ; gwm:releaseYear ' + str(film["release_year"]) + ' .\n')
                for field in ("wikidata_id", "imdb_id", "tmdb_id", "filmapia_id"):
                    if film[field]:
                        stream.write(iri(fid) + ' gwm:' + field + ' ' + lit(film[field]) + ' .\n')
            for pid, person in self.people.items():
                stream.write(iri(pid) + ' a gwm:Person ; rdfs:label ' + lit(person["name"]) + ' .\n')
            for sid, song in self.songs.items():
                stream.write(iri(sid) + ' a gwm:Song ; rdfs:label ' + lit(song["title"]) + ' .\n')
            for pid, place in self.places.items():
                kind = "HeritageSite" if pid.startswith("heritage:") else "HeritageComponent" if pid.startswith("heritage-component:") else "Place"
                stream.write(iri(pid) + ' a gwm:' + kind + ', geo:Feature ; rdfs:label ' + lit(place["place_name"]) +
                             ' ; gwm:coordinateScope ' + lit(place["coordinate_scope"]) + ' .\n')
                if place["heritage_parent_id"]:
                    stream.write(iri(pid) + ' gwm:partOfHeritage ' + iri(place["heritage_parent_id"]) + ' .\n')
                if place["inscription_year"] != "":
                    stream.write(iri(pid) + ' gwm:inscriptionYear ' + str(place["inscription_year"]) + ' .\n')
                if place["latitude"] != "":
                    geom = iri("geometry:" + pid)
                    wkt = '<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POINT (%s %s)' % (place["longitude"], place["latitude"])
                    stream.write(iri(pid) + ' geo:hasGeometry ' + geom + ' .\n' + geom +
                                 ' a geo:Geometry ; geo:asWKT ' + lit(wkt) + '^^geo:wktLiteral .\n')
                    if place["coordinate_source"]:
                        stream.write(iri(pid) + ' gwm:coordinateSourceURL ' + lit(place["coordinate_source"]) + ' .\n')
            predicates = {"filming": "filmedAt", "narrative": "setIn", "cast_member": "castMember",
                          "director": "directedBy", "in_film": "inFilm"}
            direct = set()
            for cid, claim in self.claims.items():
                triple = (claim["subject_id"], predicates[claim["relation"]], claim["object_id"])
                subject, predicate, obj = iri(triple[0]), "gwm:" + triple[1], iri(triple[2])
                if triple not in direct:
                    stream.write(subject + " " + predicate + " " + obj + " .\n")
                    direct.add(triple)
                stream.write(iri(cid) + ' a rdf:Statement ; rdf:subject ' + subject + ' ; rdf:predicate ' + predicate +
                    ' ; rdf:object ' + obj + ' ; prov:wasDerivedFrom ' + iri("source:" + claim["source_file"]) +
                    ' ; gwm:sourceRow ' + lit(claim["source_row"]) + ' ; gwm:method ' + lit(claim["method"]) +
                    ' ; gwm:status ' + lit(claim["status"]) + ' .\n')
                if claim["source_url"]:
                    # Treat URLs as data literals. Bad legacy URLs cannot inject Turtle.
                    stream.write(iri(cid) + ' gwm:sourceURL ' + lit(claim["source_url"]) + ' .\n')
                for field, predicate in [("evidence", "evidence"), ("revision_id", "revisionId"), ("retrieved_at", "retrievedAt")]:
                    if claim[field]:
                        stream.write(iri(cid) + ' gwm:' + predicate + ' ' + lit(claim[field]) + ' .\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "Dataset")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "Dataset" / "integrated")
    parser.add_argument("--start-year", type=int, default=2000)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--heritage-cutoff", type=int, default=2025)
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("start-year must not exceed end-year")
    pipeline = Integration(args.data_dir, args.start_year, args.end_year, args.heritage_cutoff).build()
    pipeline.export(args.output_dir)
    result = pipeline.summary()
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
    print("Wrote integrated tables, GeoJSON and RDF to", args.output_dir)


if __name__ == "__main__":
    main()
