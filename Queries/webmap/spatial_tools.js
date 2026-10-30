/* Geometry and road-network operations shared by the interface and tests. */
(function(root){
'use strict';
const T=typeof module==='object'&&module.exports?require('./vendor/turf.min.js'):root.turf;
function polygon(points){
 if(points.length<3)throw Error('Add at least three points to finish your area.');
 if(points.length>100)throw Error('Use at most 100 points for one area.');
 const ring=points.map(p=>[p[1],p[0]]);ring.push([...ring[0]]);
 const feature=T.polygon([ring]);
 if(T.kinks(feature).features.length||T.area(feature)<1)throw Error('Draw an area without crossing edges and with at least three different points.');
 if(Math.max(...ring.map(p=>p[0]))-Math.min(...ring.map(p=>p[0]))>180)throw Error('Draw an area on one side of the date line.');
 return feature;
}
function contains(geometry,point){return T.booleanPointInPolygon([point.lon,point.lat],geometry);}
function circle(center,radiusKm){return T.circle([center[1],center[0]],radiusKm,{steps:128,units:'kilometers'});}
function corridor(route,width){
 if(!Number.isFinite(width)||width<.1||width>25)throw Error('Choose a corridor width between 0.1 and 25 km.');
 if(route?.type!=='LineString'||route.coordinates.length<2)throw Error('The routing service did not return a usable road route.');
 const area=T.buffer(T.feature(route),width,{units:'kilometers',steps:12});
 if(!area)throw Error('Could not create the route corridor. Try a shorter route.');
 return area;
}
function routeDistance(point,line){return T.pointToLineDistance([point.lon,point.lat],line,{units:'kilometers'});}
function polygonFeatures(collection){
 const features=collection?.features?.filter(f=>['Polygon','MultiPolygon'].includes(f.geometry?.type))||[];
 if(!features.length)throw Error('No reachable area was returned. Try another starting point or travel mode.');
 return features;
}
function createRouter({base='https://valhalla1.openstreetmap.de',fetcher=globalThis.fetch}={}){
 const cache=new Map();let busy=false,lastStarted=0;
 async function request(kind,payload,signal){
  const key=kind+JSON.stringify(payload);
  if(cache.has(key))return cache.get(key);
  if(busy)throw Error('A road calculation is already in progress.');
  if(Date.now()-lastStarted<1500)throw Error('Please wait a moment before another road calculation.');
  busy=true;lastStarted=Date.now();const controller=new AbortController();
  const cancel=()=>controller.abort();signal?.addEventListener('abort',cancel,{once:true});
  const timeout=setTimeout(()=>controller.abort(),30000);
  try{
   const response=await fetcher(base+'/'+kind+'?json='+encodeURIComponent(JSON.stringify(payload)),{signal:controller.signal,headers:{'X-Client-Id':'places-and-stories.vercel.app'}});
   if(!response.ok)throw Error(response.status===429?'The road service is busy. Wait a minute and try again.':'The road service could not complete this request. Try a closer road point or retry later.');
   const body=await response.json();if(body.error||body.error_code)throw Error(body.error||'Road calculation failed.');
   if(cache.size>=20)cache.delete(cache.keys().next().value);cache.set(key,body);return body;
  }catch(err){if(controller.signal.aborted)throw Error('Road calculation cancelled or timed out. Try again when ready.');if(err instanceof TypeError)throw Error('Cannot reach the road service. Check your internet connection and retry.');throw err;}
  finally{clearTimeout(timeout);signal?.removeEventListener('abort',cancel);busy=false;}
 }
 const location=p=>{if(!Array.isArray(p)||p.length!==2||!p.every(Number.isFinite)||Math.abs(p[0])>90||Math.abs(p[1])>180)throw Error('Choose a valid map point.');return {lat:p[0],lon:p[1]};};
 const mode=value=>{if(!['auto','pedestrian','bicycle'].includes(value))throw Error('Choose driving, walking or cycling.');return value;};
 return {
 async route(start,end,costing,signal){
  const body=await request('route',{locations:[location(start),location(end)],costing:mode(costing),format:'osrm',shape_format:'geojson',directions_type:'none'},signal);
  const route=body.routes?.[0];if(!route||route.geometry?.type!=='LineString')throw Error('No road route found between these points.');return route;
 },
 async reachable(start,minutes,costing,signal){
  if(!Number.isFinite(minutes)||minutes<5||minutes>120)throw Error('Choose a travel time between 5 and 120 minutes.');
  const body=await request('isochrone',{locations:[location(start)],costing:mode(costing),contours:[{time:minutes}],polygons:true,denoise:0,generalize:25},signal);
  return {type:'FeatureCollection',features:polygonFeatures(body)};
 }
 };
}
const api={polygon,contains,circle,corridor,routeDistance,polygonFeatures,createRouter};
if(typeof module==='object'&&module.exports)module.exports=api;else root.SpatialTools=api;
})(typeof globalThis!=='undefined'?globalThis:this);
