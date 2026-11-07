"""Fetch round-two candidates; accepted identities remain reviewed in sites.csv."""
from fetch_sources import fetch
from concurrent.futures import ThreadPoolExecutor
PAGES = {
 'bandra':'Castella_de_Aguada','golden':'Golden_Temple','ramnagar':'Ramnagar_Fort',
 'chail':'Chail_Palace','fernhill':'Fernhills_Palace','baradari':'Baradari_Palace',
 'gajner':'Gajner_Palace','city_jaipur':'City_Palace,_Jaipur','afghan':'Afghan_Church',
 'devigarh':'Devigarh','thirumalai':'Thirumalai_Nayakkar_Mahal','lalgarh':'Lalgarh_Palace',
 'pari':'Pari_Mahal','gloria':'Gloria_Church','bidar':'Bidar_Fort','hadimba':'Hidimba_Devi_Temple',
 'martand':'Martand_Sun_Temple','aguada':'Fort_Aguada','umaid':'Umaid_Bhawan_Palace',
 'vijaya_coordinates':'Vijaya_Vilas_Palace'}
def run(item):
 try: return fetch(item)
 except Exception as e:return item[0],str(e)
if __name__=='__main__':
 items=[(k,'https://en.wikipedia.org/wiki/'+v) for k,v in PAGES.items()]
 items.append(('bandra_official','https://www.incredibleindia.gov.in/en/maharashtra/mumbai/bandra-fort'))
 with ThreadPoolExecutor(max_workers=4) as pool:
  for result in pool.map(run,items):print(result,flush=True)
