/* Shared, deterministic radius/query engine. No network or AI calls. */
(function(root){
'use strict';
const EARTH_KM=6371.0088;
const normalize=s=>String(s).normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
function distanceKm(a,b){
 const rad=x=>x*Math.PI/180, dlat=rad(b[0]-a[0]),dlon=rad(b[1]-a[1]);
 const h=Math.sin(dlat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dlon/2)**2;
 return 2*EARTH_KM*Math.asin(Math.sqrt(Math.max(0,Math.min(1,h))));
}
function validate(options){
 const {center,radiusKm,yearFrom,yearTo}=options;
 if(!Array.isArray(center)||center.length!==2||!center.every(Number.isFinite)||Math.abs(center[0])>90||Math.abs(center[1])>180)throw Error('Choose a valid point on the map or a place from the list.');
 if(!Number.isFinite(radiusKm)||radiusKm<0.1||radiusKm>500)throw Error('Choose a radius between 0.1 and 500 km.');
 if(!Number.isInteger(yearFrom)||!Number.isInteger(yearTo)||yearFrom>yearTo)throw Error('Enter a valid year range, with the start before the end.');
 if(!['filming','narrative','both'].includes(options.relation))throw Error('Choose filming locations, story settings or both.');
}
function createEngine(data){
 const nodes=data.nodes,edges=data.edges;
 const places=(data.geo||[]).map(p=>({node:p[0],lat:p[1],lon:p[2],scope:p[3],country:p[4],coordinateSource:p[5],name:nodes[p[0]][1],heritage:nodes[p[0]][2]==='Heritage'}));
 const byNode=new Map(places.map(p=>[p.node,p])),genres=new Map(),links=[];
 edges.forEach((e,index)=>{if(e[1]==='genre'){if(!genres.has(e[0]))genres.set(e[0],new Set());genres.get(e[0]).add(nodes[e[2]][1]);}if(['filming','narrative'].includes(e[1])&&nodes[e[0]][2]==='Film'&&byNode.has(e[2]))links.push({film:e[0],place:e[2],relation:e[1],edgeIndex:index});});
 function findPlaces(text){const q=normalize(text);if(!q)return [];const exact=places.filter(p=>normalize(p.name)===q);return (exact.length?exact:places.filter(p=>normalize(p.name).includes(q))).sort((a,b)=>a.name.localeCompare(b.name)||a.node-b.node);}
 function allowed(link,o){if(o.excludePlaces?.includes(nodes[link.place][0]))return false;const year=Number(nodes[link.film][3]);return (o.relation==='both'||link.relation===o.relation)&&year>=o.yearFrom&&year<=o.yearTo&&(!o.genre||genres.get(link.film)?.has(o.genre))&&(!o.heritageOnly||byNode.get(link.place).heritage)&&(o.film==null||o.film===link.film);}
 function visiblePlaces(o){const counts=new Map();for(const link of links){if(!allowed(link,o))continue;if(!counts.has(link.place))counts.set(link.place,new Set());counts.get(link.place).add(link.film);}return [...counts].map(([id,films])=>({...byNode.get(id),filmCount:films.size}));}
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

 return {places,byNode,findPlaces,search,searchArea,selected,visiblePlaces,genres:[...new Set([...genres.values()].flatMap(s=>[...s]))].sort()};
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
const api={distanceKm,createEngine,parseQuery,normalize};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SpatialSearch=api;
})(typeof globalThis!=='undefined'?globalThis:this);
