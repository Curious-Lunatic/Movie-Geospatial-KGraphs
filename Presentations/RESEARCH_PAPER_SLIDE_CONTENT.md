# Literature review: what we have built and what is still pending

The quotes below use the exact wording from “Review of Existing Studies” in the supplied PDF. The explanations describe our project. We use some of the same ideas, but have not reproduced every study’s full method.

## Slide 1 — Connecting movie information

**Exact words from the review**

> “Movie, Director, Actor, Genre”

> “added TMDb data with ReDial data”

**What we have built**

- **A connected movie graph:** Each film links to its actors, directors and genres. This lets us follow connections between a film and the people or categories associated with it.
- **Combining information from different sources:** We add TMDB details to the supplied film records. We first use shared movie IDs to match records. When these are unavailable, we match a title and release year only if they identify one film without conflicting IDs.

**Still pending**

- We have not added ReDial conversations or built the reviewed movie-similarity and recommendation methods, such as Jaccard similarity or TuckER.

**Implementation location:** `Queries/build_integrated_graph.py` — film matching and cast, director and genre links.

## Slide 2 — Saving relationships with their evidence

**Exact words from the review**

> “It turns this evidence into RDF using the Media Annotation Ontology, PROV-O, OWL-Time and Media Fragments URIs”

**What we have built**

- **RDF relationships:** We save facts as linked statements, such as “a film was filmed at a place.” RDF gives these relationships a consistent format that graph queries can read.
- **A record of where each claim came from:** We use PROV-O to link claims to their source. We keep the original file and row, along with available URLs and evidence. If two sources support the same relationship, we retain both sources while counting the relationship once.

**Still pending**

- Extracting text, speech and actions directly from movie videos. We have also not added the other quoted standards for describing individual scenes and their timestamps.

**Implementation location:** `Queries/build_integrated_graph.py` — `claim` and `export_rdf`.

## Slide 3 — Representing places and checking distances

**Exact words from the review**

> “GeoSPARQL also allows a Feature to exist without a geometry, which suits vague places.”

> “added GADM polygons and RCC-8 relations to YAGO”

**What we have built**

- **Places with optional coordinates:** We use GeoSPARQL to represent a place separately from its coordinates. If coordinates are missing, the place and its film connections still remain in the graph.
- **Distance analysis in QGIS:** We connect film records to mapped places and create a 5 km search area around the Taj Mahal reference point. The saved example finds Agra Fort, linked to Jodhaa Akbar, about 2.145 km away. This compares site reference points, not exact shooting spots.

**Still pending**

- Adding geographic boundary polygons and RCC-8 reasoning about areas that contain, touch or overlap each other. Running our distance-query template in a GeoSPARQL-enabled database is also pending.

**Implementation location:** `Queries/build_integrated_graph.py` — place representation; `Queries/build_qgis_project.py` — map joins and distance analysis.

## Slide 4 — Checking graph data and query answers

**Exact words from the review**

> “used ontological subgraph patterns for fact checking”

> “checked SPARQL query candidates before answering”

**What we have built**

- **Checks for common data errors:** Our checks look for missing entities, missing source references and invalid coordinates. SHACL rules check that records contain the required fields and link to the expected kinds of entities. Tests also check cases such as remakes being wrongly merged.
- **Checks on query results:** Our scripts run fixed SPARQL queries about places, heritage sites and characters. For the place and heritage summaries, they compare graph-query answers with calculations from the CSV tables.

**Still pending**

- The reviewed method that learns graph patterns to judge facts, and a system that creates and checks queries from user questions. Our current checks find structural errors and inconsistent answers, but do not prove that every filming claim is historically correct.

**Implementation location:** `Queries/integration_shapes.ttl`, `Queries/validate_integrated_graph.py` and `Queries/validate_graph_queries.py`.

## Slide 5 — Learning missing links and making predictions

**Exact words from the review**

> “TransGeo [10] uses distance as weight for the neighbours.”

> “SE-KGE [11] encodes coordinates with a multiscale location encoder.”

**What we have built**

- **Data for future experiments:** Our graph contains film relationships and available place coordinates. These could become inputs to the learning methods discussed in the review.
- **Direct distance calculations:** At present, we calculate distances from known coordinates. We have not trained a model to learn geographic relationships or predict missing locations.

**Still pending**

- **Spatial learning:** Implementing TransGeo and SE-KGE to learn from distance and location information, then testing whether they help suggest useful links or alternative query answers.
- **Other prediction methods:** Contrastive learning, which trains a model by comparing selected examples, and tourist-attraction prediction using place reviews. Any suggested links would need review before entering the accepted graph.

**Implementation location:** `Queries/query_integrated_graph.py` contains the current distance calculation. The learning methods have no implementation yet.
