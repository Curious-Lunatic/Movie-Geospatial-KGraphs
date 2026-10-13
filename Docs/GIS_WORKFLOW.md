# The merge and spatial query in QGIS

The first contribution resolved movie identities in Python. The GIS extension
now executes QGIS's own processing algorithms, saves a GeoPackage and QGIS
project, and captures the live QGIS interface while reproducing the operations.

## Two different kinds of merge

**Record matching** decides whether TMDB, Wikidata, Wikipedia and Filmapia records
refer to the same film. Shared IDs come first, then guarded title/year matches.
This produces a canonical `film_id` and a source crosswalk. The checks for remakes,
conflicting IDs and source years are described in `INTEGRATION_METHOD.md`.

**GIS joins** attach film records to geometry and compare geographic features.
QGIS uses the canonical keys for attribute joins and geometric predicates for
the spatial join. A plain merge of vector layers would combine their features
without solving duplicate movie identities or answering a proximity question.

## Executed QGIS workflow

| Step | QGIS tool | Inputs and choice | Meaning |
|---|---|---|---|
| 1 | Extract by expression | `relation='filming'`, `status='source_supported'` | Keep filming evidence separate from narrative settings and review-only candidates |
| 2 | Join attributes by field value | Assertion `subject_id` → movie `film_id`; copy title/year; one-to-one lookup | Attach canonical movie details to each assertion |
| 3 | Join attributes by field value | Place `place_id` → assertion `object_id`; **one-to-many** | Put every mapped film-location assertion on the correct point without dropping other movies or evidence sources |
| 4 | Extract by expression / location | Separate heritage properties/components; filter Indian points and context boundaries | Prepare meaningful map layers rather than one undifferentiated point cloud |
| 5 | Reproject layer | Taj Mahal and nearby named heritage filming sites → **EPSG:32644** | Use WGS 84 / UTM zone 44N, with metre units, for this local Agra analysis |
| 6 | Buffer | Taj Mahal reference point; **5,000 metres**, 72 segments per quarter circle | Create the search area in a suitable projected CRS |
| 7 | Extract by location | Filming-site points intersect the buffer | Select the geographically qualifying locations |
| 8 | Join attributes by location | Selected point layer joined to the buffer; predicate **intersects** | Attach the target heritage identity using geometry |
| 9 | Join attributes by nearest | Matched points → Taj Mahal point; one neighbour; maximum distance 5,000 m | Measure the projected reference-point distance |

These are QGIS processing algorithms called through PyQGIS. The buffer,
movie attribute join and spatial join are also reproduced through QGIS GUI
dialogs, with screenshots of their settings and completion logs.
The official documentation describes
[field-value, location and nearest joins](https://docs.qgis.org/3.44/en/docs/user_manual/processing_algs/qgis/vectorgeneral.html).
PyQGIS is QGIS's supported
[Python application interface](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/intro.html).

## Open the GIS deliverable

Open **`GIS/Good_Will_Mapping_1970_2025.qgz`** in QGIS. Keep it beside
**`GIS/good_will_mapping_1970_2025.gpkg`**. All 22 saved layers reference that GeoPackage
with relative paths. The project was reopened in the QGIS engine and desktop
application with valid layers. It includes two table relations, two spatial
bookmarks and two print layouts.

The initial view shows Agra. Use **Project → Layouts** to open:

- `Agra: 5 km buffer and spatial join`
- `India: heritage and film-location references`

The PNG exports `GIS/agra_5km_map.png` and `GIS/india_overview.png` are available
for the presentation. They are QGIS map exports. The files under
`GIS/screenshots/` are separately captured screenshots of the real application.

## Observed results

The attribute joins map **6,525 supported filming assertions** to usable point
geometry. Another **1,565 filming assertions** have no usable mapped coordinate
and remain in the tabular evidence. There are **44 Indian heritage property
points**, **128 Indian heritage component points**, and **4,422 sourced filming
features whose reference points fall inside the bundled India context geometry**.
Several assertions can share a point or film; these are not unique shooting-spot
or movie counts.

The default site-level Agra query returns **Jodhaa Akbar (2008) → Agra Fort**.
QGIS measures **2,144.978 metres** from the Agra Fort reference point to the
Taj Mahal reference point. The original evidence is Filmapia CSV logical row 76.
The prior spherical Python calculation gives 2,140.626 metres. The small
difference is expected from using different distance models; the film/place
result agrees. The QGIS analysis is the GIS presentation's reported result.

The buffer is around a reference point. It is not the protected-site boundary,
and neither reference point establishes an exact camera or shooting position.
Broad city/country points are displayed in the overview but excluded from this
site-level 5 km query. Context boundaries come from QGIS's bundled
`world_map.gpkg` and are generalized display data.

## Repeat in the GUI

1. Open the saved project and examine the film, song and filming-assertion tables.
2. In the Processing Toolbox, open **Join attributes by field value**. Match
   `subject_id` from the assertion table to `film_id` from the canonical movie
   table, then copy `title` and `release_year`.
3. For a geometry join, use the point layer as the first input and the assertions
   as the second, matching `place_id` to `object_id`. Choose **Create separate
   feature for each matching feature (one-to-many)**.
4. The saved Taj Mahal and Agra result layers are already in EPSG:32644. For new
   longitude/latitude layers, run **Reproject layer** first. Use **Buffer** with
   a distance of **5,000 metres**, not 5,000 degrees.
5. Run **Join attributes by location** with local named-site filming points as
   the input and the buffer as the join layer. Use **intersects** and discard
   nonmatching records.
6. Inspect the output attributes and source rows. Use **Join attributes by
   nearest** against the target point for the distance column.

`Queries/qgis_gui_steps.py` opens the demonstrated dialogs with the correct
parameters when loaded into QGIS's Python Console. Call `show_buffer_dialog()`,
`show_attribute_join_dialog()` or `show_spatial_join_dialog()`, then click Run.
It derives the repository
location from the open project's path. The helper creates separate `_from_gui`
outputs so the portable GeoPackage remains the presentation's stable snapshot.

## Rebuild from code

First run `python Queries/build_integrated_graph.py` from the repository root.
Then use the installed QGIS Python environment, for example on this machine:

```powershell
& 'C:\Program Files\QGIS 4.0.0\bin\python-qgis.bat' Queries/build_qgis_project.py
```

`GIS/qgis_report.json` contains the executed algorithms, parameters, layer counts,
input hashes, distances, and saved-project round-trip checks. This command runs
the actual QGIS processing engine. Normal system Python does not include PyQGIS.

The refreshed build also repeats the two field joins for narrative assertions:
6,907 have point geometry and 356 remain without geometry. India contains
5,039 mapped narrative assertion features. The 12 October GUI captures retain
the earlier cohort; 13 October processing counts come from the QGIS engine.
