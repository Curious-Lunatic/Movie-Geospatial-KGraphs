# Final demonstration — 11 November 2026

Keep the background short. The main demonstration is **question → interpreted
filters → recorded answer → map → evidence → QGIS export**. Fanaa is the verified
film example. Jeans and Genie have no matching film identity in this snapshot;
do not add unsupported movie/location claims to make a demonstration work.

## Start locally

From the repository root:

```sh
python Queries/build_integrated_graph.py
python Queries/build_graph_explorer.py
python Queries/serve_demo.py
```

Open `http://127.0.0.1:8767/graph_explorer.html#chat`. If the port is already
occupied, use `python Queries/serve_demo.py --port 8768` and the corresponding URL.
Use the local server for region queries: browsers can block boundary-file fetches
when the HTML is opened directly through `file://`.

## Five-minute speaking script

**0:00–0:30 — context.** “We connect supplied cinema records with geographic and
heritage information. Shared identifiers resolve film identities, and each
relationship retains source evidence. Today we focus on using that data through
the chat and map, rather than repeating the entire mid-evaluation background.”

**0:30–1:40 — nearby question and follow-up.** Ask `Movies within 5 km of Taj Mahal`.
“The chat translates a supported question into a radius, place, relationship and
year filters. This snapshot returns **14 distinct films at two place identities**.
These include a broad Agra city reference, so they are not 14 verified filming
addresses.” Then ask `Only heritage`. “The follow-up keeps the centre and radius
and filters the result locations. Now the result is **Jodhaa Akbar (2008), Agra
Fort**, about **2.141 km** from the Taj Mahal representative point. Being near
the Taj Mahal does not establish filming at the Taj Mahal.” Expand Evidence.

**1:40–2:40 — region overlay.** Ask `Romance movies in Rajasthan`. “This is a
point-in-polygon selection, not a radius around the state's central coordinate.
The snapshot returns **46 films and 16 place identities**.” Ask `After 2010`.
“The state and genre remain selected; the year filter changes to 2011–2025.
This returns **20 films and 11 places**.” Explain that known country references
are excluded and that state-level points can remain in state results. District
queries additionally exclude known state-level references. Boundaries are
published research layers, not a claim of current administrative accuracy.

**2:40–3:40 — film, graph and evidence.** Ask `Tell me about Fanaa 2006`.
“This film has links in all six categories: songs, people, characters, genres,
places and heritage.” Open the movie graph. Identify Chand Sifarish, Aamir Khan,
Rehan Qadri, Romance, Delhi, and Qutb Minar. Return to the chat and ask
`Heritage sites in Fanaa`, then expand Evidence. “This answer reports recorded
filming relationships. Individual soundtrack shooting locations are not
inherited from the film.” Ask `Show songs` to demonstrate film-context follow-up.

**3:40–4:30 — QGIS handoff.** Repeat the Taj Mahal question and `Only heritage`.
Use **QGIS layer ↓** below the map. The actual downloaded GeoJSON includes the
search polygon, point result, film/place IDs, relationship and source reference.
Open `GIS/chat_demo/Chat_Query_Demo.qgz` for the prepared two-layer import. “The
browser computes spherical reference-point distance. This project demonstrates
importing that result into QGIS. Our earlier native projected QGIS calculation
gave 2.145 km; it is a different distance method. We are not claiming that the
website runs a QGIS server or that the new import reran the native buffer.”

**4:30–5:00 — limits and conclusion.** “The chat is a deterministic interface to
supported query patterns, not an unrestricted language model. It shows the
interpreted filters and returns source-backed records. Missing or ambiguous
places trigger an explanation; empty results mean no recorded matches. Missing
coordinates, incomplete movie coverage and broad reference points limit answers.”

## Expected results in the saved snapshot

| Question | Expected result |
|---|---|
| Movies within 5 km of Taj Mahal | 14 films / 2 places |
| Only heritage | 1 film / 1 place: Jodhaa Akbar / Agra Fort |
| Romance movies in Rajasthan | 46 films / 16 places |
| After 2010, following the Rajasthan question | 20 films / 11 places |
| Movies in Agra district | 15 films / 3 places |
| Songs in Fanaa | 7 recorded song entities |
| Heritage sites in Fanaa | 2 recorded heritage links |

Counts describe this build, not all cinema. Machine-readable answers are saved
in `Dataset/chat_demo/results.json`. The browser transcript is session-only;
New conversation clears it and its follow-up context.

## Reliability and fallback

The graph and nearby questions work on the stored data. Region queries fetch
the committed boundary assets from the local server. Posters and background
tiles need internet; their absence does not prevent local selections. Road
routes and travel-time tools require the existing external routing service and
are outside the chat's supported patterns. Do not present an unsupported question
as answered. Use saved screenshots and the prepared QGIS import if the browser
or network is unavailable. The repository includes build scripts rather than
checking the large regenerated explorer into Git.
