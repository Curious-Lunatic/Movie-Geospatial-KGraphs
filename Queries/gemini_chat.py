"""Gemini 3.5 Flash Lite backend for the Cinema Atlas chatbot.

Uses Python standard library only so no extra packages are required.
Reads GEMINI_API_KEY from the environment or a local .env file at repo root.
"""
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL = "gemini-3.5-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def load_api_key():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                return v.strip().strip('"').strip("'")
    return None


TOOL_DECLARATIONS = [
    {
        "name": "search_movies_nearby",
        "description": "Find movies filmed or set within a radius (0.1 to 2000 km) of a named place or heritage site.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "placeText": {"type": "STRING", "description": "Name of the place or heritage site (e.g., 'Taj Mahal', 'Chennai', 'Agra Fort')."},
                "radiusKm": {"type": "NUMBER", "description": "Search radius in kilometres (0.1 to 2000). Default 10."},
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"], "description": "Whether to match filming locations, story settings, or both. Default 'filming'."},
                "genre": {"type": "STRING", "description": "Optional genre filter matching one of the recorded genres."},
                "yearFrom": {"type": "INTEGER", "description": "Optional start release year."},
                "yearTo": {"type": "INTEGER", "description": "Optional end release year."},
                "heritageOnly": {"type": "BOOLEAN", "description": "If true, only include heritage result locations."},
                "excludeBroad": {"type": "BOOLEAN", "description": "If true, exclude broad city/country/region reference points."},
            },
            "required": ["placeText"],
        },
    },
    {
        "name": "search_movies_in_region",
        "description": "Find movies filmed or set inside an Indian state, union territory, or district boundary.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "regionText": {"type": "STRING", "description": "State, union territory, or district name (e.g., 'Rajasthan', 'Agra district', 'Kerala')."},
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"], "description": "Default 'filming'."},
                "genre": {"type": "STRING", "description": "Optional genre filter."},
                "yearFrom": {"type": "INTEGER", "description": "Optional start release year."},
                "yearTo": {"type": "INTEGER", "description": "Optional end release year."},
                "heritageOnly": {"type": "BOOLEAN", "description": "If true, only include heritage result locations."},
                "excludeBroad": {"type": "BOOLEAN", "description": "If true, exclude broad city/region reference points."},
            },
            "required": ["regionText"],
        },
    },
    {
        "name": "search_heritage_sites_nearby",
        "description": "List recorded UNESCO and historic heritage reference sites within a radius of a place.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "placeText": {"type": "STRING", "description": "Centre place name (e.g., 'Chennai', 'Delhi')."},
                "radiusKm": {"type": "NUMBER", "description": "Search radius in km (0.1 to 2000). Default 100."},
            },
            "required": ["placeText"],
        },
    },
    {
        "name": "search_movies_along_route",
        "description": "Find movies within a corridor along a road route between two places using the Valhalla routing service.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "startPlace": {"type": "STRING", "description": "Starting place name (e.g., 'Delhi')."},
                "endPlace": {"type": "STRING", "description": "Destination place name (e.g., 'Agra')."},
                "corridorKm": {"type": "NUMBER", "description": "Corridor width in km on each side of the route (0.1 to 250). Default 25."},
                "travelMode": {"type": "STRING", "enum": ["auto", "pedestrian", "bicycle"], "description": "Routing mode: 'auto' (car), 'pedestrian' (walking), or 'bicycle'. Default 'auto'."},
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"]},
                "genre": {"type": "STRING"},
                "yearFrom": {"type": "INTEGER"},
                "yearTo": {"type": "INTEGER"},
                "heritageOnly": {"type": "BOOLEAN"},
            },
            "required": ["startPlace", "endPlace"],
        },
    },
    {
        "name": "search_reachable_locations",
        "description": "Find movies inside the area reachable within a given travel time (isochrone) from a starting place.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "startPlace": {"type": "STRING", "description": "Starting place name (e.g., 'Mumbai', 'Jaipur')."},
                "minutes": {"type": "INTEGER", "description": "Travel time in minutes (5 to 120). Default 60."},
                "travelMode": {"type": "STRING", "enum": ["auto", "pedestrian", "bicycle"], "description": "Default 'auto'."},
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"]},
                "genre": {"type": "STRING"},
                "yearFrom": {"type": "INTEGER"},
                "yearTo": {"type": "INTEGER"},
                "heritageOnly": {"type": "BOOLEAN"},
            },
            "required": ["startPlace"],
        },
    },
    {
        "name": "search_in_polygon",
        "description": "Search movies within a custom polygon defined by coordinates, or open the interactive polygon drawing tool on the map.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "coordinates": {
                    "type": "ARRAY",
                    "description": "Optional list of [lat, lon] points forming the polygon. Omit to open interactive drawing mode on the map.",
                    "items": {
                        "type": "ARRAY",
                        "items": {"type": "NUMBER"},
                    },
                },
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"]},
                "genre": {"type": "STRING"},
                "yearFrom": {"type": "INTEGER"},
                "yearTo": {"type": "INTEGER"},
                "heritageOnly": {"type": "BOOLEAN"},
            },
        },
    },
    {
        "name": "inspect_movie",
        "description": "Inspect a specific film's connections in the knowledge graph: overview, cast, songs, characters, genres, heritage sites, or filming/story locations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filmText": {"type": "STRING", "description": "Film title, optionally with release year (e.g., 'Fanaa 2006', 'Dilwale')."},
                "category": {"type": "STRING", "enum": ["overview", "cast", "actors", "songs", "characters", "genres", "heritage", "locations"], "description": "Default 'overview'."},
                "relation": {"type": "STRING", "enum": ["filming", "narrative"], "description": "Optional filter when category is 'locations'."},
            },
            "required": ["filmText"],
        },
    },
    {
        "name": "inspect_place",
        "description": "Explore a specific place or heritage site: opens its info panel with recorded films, nearby landmarks/towns, description, and Google Maps link.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "placeText": {"type": "STRING", "description": "Name of the place or heritage site to inspect."},
            },
            "required": ["placeText"],
        },
    },
    {
        "name": "search_song_locations",
        "description": "Find explicit source-supported song filming locations, filtered optionally by song title, film title, or place.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "songText": {"type": "STRING", "description": "Optional song title (e.g., 'Gerua', 'Chaiyya Chaiyya')."},
                "filmText": {"type": "STRING", "description": "Optional film title."},
                "placeText": {"type": "STRING", "description": "Optional place name."},
                "radiusKm": {"type": "NUMBER", "description": "Optional radius in km if searching near a place."},
            },
        },
    },
    {
        "name": "search_places_by_genre",
        "description": "List places connected to films of a genre, ranked by number of distinct linked films. Use for questions such as 'What places are associated with Romance?' or 'Which filming locations are connected to Drama films?'. This is a fresh catalogue query, not a refinement of the prior search.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "genre": {"type": "STRING", "description": "A recorded genre, such as Romance, Drama, Action, or Comedy."},
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"], "description": "Whether to include filming locations, story settings, or both. Default 'both'."},
                "yearFrom": {"type": "INTEGER"},
                "yearTo": {"type": "INTEGER"},
            },
            "required": ["genre"],
        },
    },
    {
        "name": "update_previous_search",
        "description": "Modify or refine filters on the immediately preceding spatial, heritage catalog, or movie query (e.g., 'only heritage', 'within 20 km', 'after 2010', 'only Romance', 'show songs').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "radiusKm": {"type": "NUMBER"},
                "heritageOnly": {"type": "BOOLEAN"},
                "excludeBroad": {"type": "BOOLEAN"},
                "relation": {"type": "STRING", "enum": ["filming", "narrative", "both"]},
                "genre": {"type": "STRING", "description": "Genre name, or empty string '' for all genres."},
                "yearFrom": {"type": "INTEGER"},
                "yearTo": {"type": "INTEGER"},
                "category": {"type": "STRING", "enum": ["overview", "cast", "actors", "songs", "characters", "genres", "heritage", "locations"]},
            },
        },
    },
]


def build_system_instruction(context):
    genres = ", ".join(context.get("genres", [])) or "Romance, Drama, Action, Comedy, etc."
    years = context.get("years", [1970, 2025])
    previous = context.get("previous")
    prev_text = json.dumps(previous, ensure_ascii=False) if previous else "None"
    return (
        "You are the Cinema Atlas geospatial assistant for a Bollywood/Indian cinema knowledge graph "
        f"covering years {years[0]}–{years[1]}.\n"
        f"Recorded genres: {genres}.\n"
        f"Previous active search plan: {prev_text}.\n\n"
        "Guidelines:\n"
        "1. Whenever the user asks to find movies, heritage sites, song locations, routes, travel-time reachable areas, "
        "drawn polygon searches, or to inspect a specific film or place/landmark/Google Maps link, ALWAYS call the most "
        "appropriate tool function so the interactive map and panels update in-place.\n"
        "2. If the user asks for places/locations connected to films of a genre (for example, 'what places are associated with Romance'), "
        "call `search_places_by_genre` as a new query, even when there is a previous search.\n"
        "3. Call `update_previous_search` only when the user clearly refers to the existing result and asks to change/refine it "
        "(for example, 'filter those to Romance', 'only heritage in those results', or 'increase that radius'). A new question about a different "
        "subject, category, or geographic scope starts a new query.\n"
        "4. If the user asks what a result means or asks whether the current locations are filming locations or story settings, "
        "explain the displayed result in plain text without calling any function. The graph distinguishes 'filming' from 'narrative' links; if both were requested, say both are included and the counts may overlap.\n"
        "5. Never invent film or filming-location facts from memory; rely on the atlas tools for dataset queries.\n"
        "6. If the user asks a general, conceptual, or conversational question (e.g., how distances work, what the app can do, "
        "or general greetings), answer concisely and helpfully in plain text without calling a tool."
    )


def chat(payload):
    api_key = load_api_key()
    if not api_key:
        return 503, {
            "error": "GEMINI_API_KEY is not configured. Set the GEMINI_API_KEY environment variable or add GEMINI_API_KEY=... to a .env file in the repository root, then restart serve_demo.py."
        }

    message = str(payload.get("message") or "").strip()
    if not message:
        return 400, {"error": "Message must not be empty."}

    history = payload.get("history") or []
    context = payload.get("context") or {}

    contents = []
    for turn in history[-12:]:
        role = "model" if turn.get("role") == "model" else "user"
        text = str(turn.get("text") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    body = {
        "systemInstruction": {"parts": [{"text": build_system_instruction(context)}]},
        "contents": contents,
        "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
    }

    req = urllib.request.Request(
        f"{API_URL}?key={api_key}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")
        return err.code, {"error": f"Gemini API error ({err.code}): {detail}"}
    except Exception as err:
        return 502, {"error": f"Failed to reach Gemini API: {err}"}

    candidates = data.get("candidates") or []
    if not candidates:
        return 502, {"error": "Gemini returned no response candidates."}

    parts = (candidates[0].get("content") or {}).get("parts") or []
    tool_call = None
    text_parts = []
    for part in parts:
        if "functionCall" in part:
            fc = part["functionCall"]
            tool_call = {"name": fc.get("name"), "args": fc.get("args") or {}}
        elif "text" in part and part["text"]:
            text_parts.append(part["text"])

    return 200, {
        "model": MODEL,
        "toolCall": tool_call,
        "reply": "\n".join(text_parts).strip(),
    }
