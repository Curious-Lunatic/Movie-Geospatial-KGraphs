/* Shared, deterministic radius/query engine. No network or AI calls. */
(function(root){
'use strict';
const EARTH_KM=6371.0088;
const MAX_RADIUS_KM=2000;
const normalize=s=>String(s).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^\p{L}\p{M}\p{N}]+/gu,' ').trim();
const kindLabels={city:'City reference',country:'Country reference',region:'Region reference',venue:'Named place reference',heritage_property:'UNESCO heritage property',heritage_component:'UNESCO heritage component',historic_site:'Historic landmark reference',unknown:'Place · precision not classified'};
function placeLabel(p){return kindLabels[p.kind]||(p.heritage?'Heritage reference':'Place reference');}
function precisionNote(p){return p.broad?'This point represents a city, country or region. The exact filming site is not recorded.':'Representative coordinates; not a verified filming address or camera position.';}
function distanceKm(a,b){
 const rad=x=>x*Math.PI/180, dlat=rad(b[0]-a[0]),dlon=rad(b[1]-a[1]);
 const h=Math.sin(dlat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dlon/2)**2;
 return 2*EARTH_KM*Math.asin(Math.sqrt(Math.max(0,Math.min(1,h))));
}
function validate(options){
 const {center,radiusKm,yearFrom,yearTo}=options;
 if(!Array.isArray(center)||center.length!==2||!center.every(Number.isFinite)||Math.abs(center[0])>90||Math.abs(center[1])>180)throw Error('Choose a valid point on the map or a place from the list.');
 if(!Number.isFinite(radiusKm)||radiusKm<0.1||radiusKm>MAX_RADIUS_KM)throw Error('Choose a radius between 0.1 and '+MAX_RADIUS_KM+' km.');
 if(!Number.isInteger(yearFrom)||!Number.isInteger(yearTo)||yearFrom>yearTo)throw Error('Enter a valid year range, with the start before the end.');
 if(!['filming','narrative','both'].includes(options.relation))throw Error('Choose filming locations, story settings or both.');
}
function createEngine(data){
 const nodes=data.nodes,edges=data.edges;
 const places=(data.geo||[]).map(p=>{const m=nodes[p[0]][7]||{};return {node:p[0],lat:p[1],lon:p[2],scope:p[3],country:p[4],coordinateSource:p[5],name:nodes[p[0]][1],heritage:nodes[p[0]][2]==='Heritage',kind:m.kind||(nodes[p[0]][2]==='Heritage'?'historic_site':'unknown'),precision:m.precision||'unknown_reference',aliases:m.aliases||[],locality:m.locality||'',identitySource:m.identitySource||nodes[p[0]][6]||'',parentId:m.parentId||'',broad:['city','country','region'].includes(m.kind)};});
 const byNode=new Map(places.map(p=>[p.node,p])),genres=new Map(),links=[];
 edges.forEach((e,index)=>{if(e[1]==='genre'){if(!genres.has(e[0]))genres.set(e[0],new Set());genres.get(e[0]).add(nodes[e[2]][1]);}if(['filming','narrative'].includes(e[1])&&nodes[e[0]][2]==='Film'&&byNode.has(e[2]))links.push({film:e[0],place:e[2],relation:e[1],edgeIndex:index});});
 const searchIndex=places.map(p=>({place:p,names:[p.name,...p.aliases].map(normalize),context:normalize(p.locality)}));
 function findPlaces(text,{heritageOnly=false}={}){const q=normalize(text);if(!q)return [];const candidates=searchIndex.filter(r=>!heritageOnly||r.place.heritage);const exact=candidates.filter(r=>r.names.includes(q));return (exact.length?exact:candidates.filter(r=>r.names.some(n=>n.includes(q))||r.context.includes(q))).map(r=>r.place).sort((a,b)=>a.name.localeCompare(b.name)||a.node-b.node);}
 function allowed(link,o){if(o.excludePlaces?.includes(nodes[link.place][0])||(o.excludeBroad&&byNode.get(link.place).broad))return false;const year=Number(nodes[link.film][3]);return (o.relation==='both'||link.relation===o.relation)&&year>=o.yearFrom&&year<=o.yearTo&&(!o.genre||genres.get(link.film)?.has(o.genre))&&(!o.heritageOnly||byNode.get(link.place).heritage)&&(o.film==null||o.film===link.film);}
 function visiblePlaces(o){const counts=new Map();for(const link of links){if(!allowed(link,o))continue;if(!counts.has(link.place))counts.set(link.place,new Set());counts.get(link.place).add(link.film);}return [...counts].map(([id,films])=>({...byNode.get(id),filmCount:films.size}));}
 function placesByGenre({genre,relation='both',yearFrom=1970,yearTo=2025}={}){
  const counts=new Map();
  for(const link of links){
   const year=Number(nodes[link.film][3]);
   if(year<yearFrom||year>yearTo||(relation!=='both'&&link.relation!==relation)||!genres.get(link.film)?.has(genre))continue;
   if(!counts.has(link.place))counts.set(link.place,{films:new Set(),filmingFilms:new Set(),narrativeFilms:new Set()});
   const row=counts.get(link.place);row.films.add(link.film);row[link.relation==='filming'?'filmingFilms':'narrativeFilms'].add(link.film);
  }
  return [...counts].map(([id,row])=>({...byNode.get(id),filmCount:row.films.size,filmingFilmCount:row.filmingFilms.size,narrativeFilmCount:row.narrativeFilms.size}))
   .sort((a,b)=>b.filmCount-a.filmCount||a.name.localeCompare(b.name));
 }
 function selected(o, selections){
 validate({...o,center:o.center||[0,0],radiusKm:o.radiusKm||1});
 const films=new Map();
 for(const link of links){
  if(!selections.has(link.place)||!allowed(link,o))continue;
  if(!films.has(link.film))films.set(link.film,{film:link.film,matches:[]});
  films.get(link.film).matches.push({...link,place:byNode.get(link.place),distanceKm:selections.get(link.place)});
 }
 return [...films.values()].map(f=>{
  f.matches.sort((a,b)=>(a.distanceKm??0)-(b.distanceKm??0)||a.place.name.localeCompare(b.place.name));
  return {...f,distanceKm:f.matches[0].distanceKm};
 }).sort((a,b)=>(a.distanceKm??0)-(b.distanceKm??0)||nodes[a.film][1].localeCompare(nodes[b.film][1]));
 }
 function search(o){
 validate(o);const distances=new Map();
 for(const place of places){const d=distanceKm(o.center,[place.lat,place.lon]);if(d<=o.radiusKm)distances.set(place.node,d);}
 return selected(o,distances);
 }
 function searchArea(o,areas,distance){
 const tools=typeof module==='object'&&module.exports?require('./spatial_tools.js'):root.SpatialTools;
 const geometries=Array.isArray(areas)?areas:[areas];
 const selection=new Map();
 for(const p of visiblePlaces(o))if(geometries.some(g=>tools.contains(g,p)))selection.set(p.node,distance?distance(p):null);
 return selected(o,selection);
 }

 function heritageNearby({center,radiusKm,limit=2000}){
  validate({center,radiusKm,relation:'both',yearFrom:1970,yearTo:2025});
  const linked=new Map();for(const l of links){if(!linked.has(l.place))linked.set(l.place,new Set());linked.get(l.place).add(l.film);}
  const all=places.filter(p=>p.heritage&&!p.parentId&&!nodes[p.node][0].startsWith('heritage-component:')).map(p=>({...p,distanceKm:distanceKm(center,[p.lat,p.lon]),directFilmCount:linked.get(p.node)?.size||0})).filter(p=>p.distanceKm<=radiusKm).sort((a,b)=>a.distanceKm-b.distanceKm||a.name.localeCompare(b.name));
  return {items:all.slice(0,limit),total:all.length};
 }
 return {places,byNode,findPlaces,search,searchArea,selected,visiblePlaces,placesByGenre,heritageNearby,genres:[...new Set([...genres.values()].flatMap(s=>[...s]))].sort()};
}
function parseQuery(text,genres,years=[1970,2025]){
 let q=String(text).trim().replace(/[?.!]+$/,'').trim(),yearFrom=years[0],yearTo=years[1];
 const yearMatch=q.match(/\s+(?:between|from)\s+(\d{4})\s+(?:and|to)\s+(\d{4})$/i);
 if(yearMatch){yearFrom=+yearMatch[1];yearTo=+yearMatch[2];q=q.slice(0,yearMatch.index);}
 else {const single=q.match(/\s+(after|before|in)\s+(\d{4})$/i);if(single){const y=+single[2];if(single[1].toLowerCase()==='after')yearFrom=y+1;else if(single[1].toLowerCase()==='before')yearTo=y-1;else yearFrom=yearTo=y;q=q.slice(0,single.index);}}
 const match=q.match(/^(?:(?:show|list|find)\s+)?(?:all\s+)?(?:(.+?)\s+)?(?:movies|films)(?:\s+(filmed|shot|set))?\s+(?:within\s+([\d.]+)\s*(?:km|kilometers|kilometres)\s+(?:of|around)|near|around)\s+(.+)$/i);
 if(!match)throw Error('Try “Movies within 10 km of Agra Fort” or “Romance movies near Jaipur between 2000 and 2020”. Use a place name or “here” for the selected point.');
 let genre='';if(match[1]){genre=genres.find(g=>normalize(g)===normalize(match[1]));if(!genre)throw Error('That genre or query filter is not supported. Choose a genre from the controls, or use one of the examples.');}
 const radiusKm=match[3]?Number(match[3]):10,relation=match[2]?.toLowerCase()==='set'?'narrative':'filming';
 const place=match[4].trim();if(/\b(?:starring|except|excluding|not|and|or|with|without|after|before|between|from)\b/i.test(place))throw Error('Please use one place and the supported year/genre filters. Actor, exclusion and multiple-place queries are not supported yet.');
 const options={radiusKm,yearFrom,yearTo,genre,relation,heritageOnly:false};validate({...options,center:[0,0]});
 return {...options,place:/^(here|this point|this area|selected point|selected area)$/i.test(place)?null:place};
}
const api={MAX_RADIUS_KM,distanceKm,createEngine,parseQuery,normalize,placeLabel,precisionNote};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SpatialSearch=api;
})(typeof globalThis!=='undefined'?globalThis:this);
