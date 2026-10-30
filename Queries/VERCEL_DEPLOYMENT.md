# Publish Places & Stories on Vercel

Live website: <https://places-and-stories.vercel.app>

From the repository root:

```sh
python Queries/prepare_vercel_site.py
vercel login
vercel deploy outputs/vercel-site --prod
```

On the first deployment, create a project named `places-and-stories` in your
Vercel account. The deployment folder contains its static-site configuration;
no framework, install step or build step is needed on Vercel.

The preparation script rebuilds the explorer from `Dataset/integrated/` and
packages the website, a compressed graph script, and its spatial layers and downloads. The
homepage loads the compressed script separately to reduce the initial transfer.
RDF and evidence downloads are
gzip-compressed to keep the upload below the Hobby plan's 100 MB limit. The
original local downloads are preserved. Posters load from TMDB, while the
graph, dark mode and spatial searches work without external scripts or API
credentials. Leaflet is bundled locally; background map tiles load from
OpenStreetMap. Movie locations, region boundaries and analysis exports open in QGIS. The large region layer is served gzip-compressed and loaded only on demand. Road routes and travel-time areas use the external Valhalla service.
See [the map documentation](webmap/README.md) for supported queries and accuracy.

Generated deployment files and Vercel project metadata remain under the
ignored `outputs/` folder. Commit the preparation script, UI template and
explorer builder and `Queries/webmap/` sources (including the Leaflet license)
to GitHub; regenerating the site requires the integrated
dataset locally. This deployment workflow publishes directly from your
computer and does not configure automatic deployments from GitHub.
