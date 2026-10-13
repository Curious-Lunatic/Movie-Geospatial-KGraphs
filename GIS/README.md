# QGIS deliverable

Open **Good_Will_Mapping_1970_2025.qgz** in QGIS and keep **good_will_mapping_1970_2025.gpkg** next
to it. The saved project contains 22 persistent layers, nine linked-table
relations, Agra/India bookmarks and two print layouts. It works without an
online basemap or the regenerated integration CSVs.

- [Workflow and interpretation](../Docs/GIS_WORKFLOW.md)
- [Actual QGIS screenshots](screenshots/README.md)
- [Executed processing report](qgis_report.json)
- [Saved-file and screenshot verification](delivery_verification.json)
- [Nearby film result](qgis_nearby_movies.csv)
- [Agra map export](agra_5km_map.png)
- [India map export](india_overview.png)

The four additional `*_from_gui.gpkg` files retain the outputs of the GUI
demonstration: buffer, attribute join, reprojected candidate points and spatial
join. Those GUI outputs preserve the 12 October 2000–2025 demonstration. The refreshed
project uses `good_will_mapping_1970_2025.gpkg` as its stable snapshot.

The sourced Agra query identifies **Jodhaa Akbar (2008) / Agra Fort**, about
**2.145 km** from the Taj Mahal reference point. This is a distance between
representative points; the data does not establish precise shooting positions.
