import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
import time

def fetch_bollywood_year(year, sparql):
    # Notice the nested OPTIONAL blocks. This says: 
    # "If a location exists, also try to get its P625 coordinates."
    query = f"""
    SELECT ?movie ?movieLabel ?releaseDate ?directorLabel 
           ?narrativeLocationLabel ?narrativeCoords 
           ?filmingLocationLabel ?filmingCoords
    WHERE {{
      ?movie wdt:P31 wd:Q11424 ;       
             wdt:P495 wd:Q668 ;        
             wdt:P364 wd:Q1568 ;       
             wdt:P577 ?releaseDate .   
             
      OPTIONAL {{ ?movie wdt:P57 ?director . }} 
      
      OPTIONAL {{ 
          ?movie wdt:P840 ?narrativeLocation . 
          OPTIONAL {{ ?narrativeLocation wdt:P625 ?narrativeCoords . }}
      }} 
      
      OPTIONAL {{ 
          ?movie wdt:P915 ?filmingLocation . 
          OPTIONAL {{ ?filmingLocation wdt:P625 ?filmingCoords . }}
      }} 
      
      FILTER(?releaseDate >= "{year}-01-01T00:00:00Z"^^xsd:dateTime && 
             ?releaseDate <= "{year}-12-31T23:59:59Z"^^xsd:dateTime)
      
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    
    try:
        results = sparql.query().convert()
        movies = []
        for result in results["results"]["bindings"]:
            movies.append({
                "wikidata_id": result.get("movie", {}).get("value", "").split("/")[-1],
                "title": result.get("movieLabel", {}).get("value", ""),
                "release_date": result.get("releaseDate", {}).get("value", "").split("T")[0],
                "director": result.get("directorLabel", {}).get("value", ""),
                "narrative_location": result.get("narrativeLocationLabel", {}).get("value", ""),
                "narrative_coordinates": result.get("narrativeCoords", {}).get("value", ""),
                "filming_location": result.get("filmingLocationLabel", {}).get("value", ""),
                "filming_coordinates": result.get("filmingCoords", {}).get("value", "")
            })
        return movies
    except Exception as e:
        print(f"Error fetching {year}: {e}")
        return []

def main():
    endpoint_url = "https://query.wikidata.org/sparql"
    sparql = SPARQLWrapper(endpoint_url)
    
    # REQUIRED: Change this to your actual email
    user_email = "your_actual_email@gmail.com" 
    sparql.agent = f"BollywoodGeoGraphBot/1.0 ({user_email}) SPARQLWrapper/1.8.5"
    
    all_movies = []
    
    for year in range(2000, 2026):
        print(f"Fetching data and coordinates for {year}...")
        year_data = fetch_bollywood_year(year, sparql)
        all_movies.extend(year_data)
        time.sleep(2) # Prevent rate-limiting
        
    df = pd.DataFrame(all_movies)
    
    if not df.empty:
        # Group to merge multiple rows for the same movie
        # This creates lists of coordinates paired with their locations
        df = df.groupby(['wikidata_id', 'title', 'release_date'], as_index=False).agg({
            'director': lambda x: ' | '.join(set(filter(None, x))),
            'narrative_location': lambda x: ' | '.join(set(filter(None, x))),
            'narrative_coordinates': lambda x: ' | '.join(set(filter(None, x))),
            'filming_location': lambda x: ' | '.join(set(filter(None, x))),
            'filming_coordinates': lambda x: ' | '.join(set(filter(None, x)))
        })
        
        df = df.sort_values(by='release_date', ascending=False)
        
        filename = "bollywood_geospatial_data_2000_2025.csv"
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"\nSuccess! Saved {len(df)} unique films with coordinates to {filename}")
    else:
        print("No data retrieved.")

if __name__ == "__main__":
    main()