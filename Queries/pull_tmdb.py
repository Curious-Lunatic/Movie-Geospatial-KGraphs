import requests, time, json, os
import pandas as pd

KEY = "df5975d9920219aad617e6a3aee4c6f6"
BASE = "https://api.themoviedb.org/3"
s = requests.Session()

def get(path, **params):
    params["api_key"] = KEY
    for attempt in range(5):
        r = s.get(f"{BASE}{path}", params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)))
        else:
            time.sleep(2 * (attempt + 1))
    return None

# Step A: collect all Hindi movie IDs, year by year
ids = {}
for y in range(1913, 2027):
    page = 1
    while True:
        d = get("/discover/movie", with_original_language="hi",
                primary_release_year=y, page=page)
        if not d: break
        for m in d["results"]:
            ids[m["id"]] = y
        if page >= min(d["total_pages"], 500): break
        page += 1
    print("listed", y, len(ids))

# Step B: fetch details + credits + external IDs (resumable)
done = set()
if os.path.exists("tmdb_details.jsonl"):
    with open("tmdb_details.jsonl") as f:
        done = {json.loads(l)["id"] for l in f}

with open("tmdb_details.jsonl", "a", encoding="utf-8") as out:
    for i, mid in enumerate(ids):
        if mid in done: continue
        d = get(f"/movie/{mid}", append_to_response="credits,external_ids")
        if d:
            out.write(json.dumps(d, ensure_ascii=False) + "\n")
        if i % 200 == 0: print("details", i, "/", len(ids))
        time.sleep(0.05)

# Step C: flatten into CSVs
movies, directors, cast = [], [], []
with open("tmdb_details.jsonl", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        movies.append({
            "tmdb_id": d["id"],
            "imdb_id": (d.get("external_ids") or {}).get("imdb_id"),
            "wikidata_id": (d.get("external_ids") or {}).get("wikidata_id"),
            "title": d.get("title"),
            "original_title": d.get("original_title"),
            "release_date": d.get("release_date"),
            "runtime": d.get("runtime"),
            "genres": "|".join(g["name"] for g in d.get("genres", [])),
            "vote_average": d.get("vote_average"),
            "vote_count": d.get("vote_count"),
            "production_countries": "|".join(c["iso_3166_1"] for c in d.get("production_countries", [])),
        })
        for c in d.get("credits", {}).get("crew", []):
            if c["job"] == "Director":
                directors.append({"tmdb_id": d["id"], "person_id": c["id"], "name": c["name"]})
        for c in d.get("credits", {}).get("cast", [])[:15]:
            cast.append({"tmdb_id": d["id"], "person_id": c["id"], "name": c["name"],
                         "character": c.get("character"), "order": c.get("order")})

pd.DataFrame(movies).to_csv("tmdb_movies.csv", index=False)
pd.DataFrame(directors).to_csv("tmdb_directors.csv", index=False)
pd.DataFrame(cast).to_csv("tmdb_cast.csv", index=False)