/* Gemini 3.5 Flash Lite powered conversational queries backed by the local graph and spatial engine. */
(function(root){
'use strict';
const Spatial=typeof module==='object'&&module.exports?require('./spatial_engine.js'):root.SpatialSearch;
const SongTools=typeof module==='object'&&module.exports?require('./song_geo.js'):root.SongGeo;
const normalize=Spatial.normalize;
const help='Ask anything about Indian cinema locations, heritage sites, routes, travel times, polygons, or films — e.g. “Movies within 5 km of Taj Mahal”, “Movies along the route from Delhi to Agra”, “Locations within 60 minutes drive from Mumbai”, “Explore Agra Fort”, or “Tell me about Fanaa 2006”.';

function defaults(years){
 return {radiusKm:10,relation:'filming',genre:'',yearFrom:years[0],yearTo:years[1],heritageOnly:false,excludeBroad:false};
}

function genreName(text,genres){
 if(!text)return '';
 const g=genres.find(g=>normalize(g)===normalize(text));
 if(!g)throw Error('Unknown genre “'+text+'”. Recorded genres: '+genres.join(', ')+'.');
 return g;
}

function validate(plan){
 if(plan.yearFrom>plan.yearTo)throw Error('The start year must not be later than the end year.');
 if(plan.intent==='route'){
  if(!Number.isFinite(plan.corridorKm)||plan.corridorKm<.1||plan.corridorKm>250)throw Error('Choose a route corridor between 0.1 and 250 km.');
 }else if(plan.intent==='isochrone'){
  if(!Number.isFinite(plan.minutes)||plan.minutes<5||plan.minutes>120)throw Error('Choose a travel time between 5 and 120 minutes.');
 }else if(['nearby','catalog','song_nearby'].includes(plan.intent)){
  if(!Number.isFinite(plan.radiusKm)||plan.radiusKm<.1||plan.radiusKm>Spatial.MAX_RADIUS_KM)throw Error('Choose a radius between 0.1 and '+Spatial.MAX_RADIUS_KM+' km.');
 }
 return plan;
}

function planFromToolCall(toolCall,{previous=null,genres=[],years=[1970,2025]}={}){
 const name=toolCall?.name,args=toolCall?.args||{};
 const base=defaults(years);
 const filters=(src)=>({
  relation:['filming','narrative','both'].includes(src.relation)?src.relation:'filming',
  genre:src.genre?genreName(src.genre,genres):'',
  yearFrom:Number.isFinite(Number(src.yearFrom))?Number(src.yearFrom):base.yearFrom,
  yearTo:Number.isFinite(Number(src.yearTo))?Number(src.yearTo):base.yearTo,
  heritageOnly:Boolean(src.heritageOnly),
  excludeBroad:Boolean(src.excludeBroad)
 });

 if(name==='search_movies_nearby'){
  return validate({...base,...filters(args),intent:'nearby',placeText:String(args.placeText||'').trim(),radiusKm:args.radiusKm!=null?Number(args.radiusKm):10});
 }
 if(name==='search_movies_in_region'){
  return validate({...base,...filters(args),intent:'region',regionText:String(args.regionText||'').trim()});
 }
 if(name==='search_heritage_sites_nearby'){
  return validate({...base,intent:'catalog',placeText:String(args.placeText||'').trim(),radiusKm:args.radiusKm!=null?Number(args.radiusKm):100});
 }
 if(name==='search_movies_along_route'){
  const mode=['auto','pedestrian','bicycle'].includes(args.travelMode)?args.travelMode:'auto';
  return validate({...base,...filters(args),intent:'route',startPlace:String(args.startPlace||'').trim(),endPlace:String(args.endPlace||'').trim(),travelMode:mode,corridorKm:args.corridorKm!=null?Number(args.corridorKm):25});
 }
 if(name==='search_reachable_locations'){
  const mode=['auto','pedestrian','bicycle'].includes(args.travelMode)?args.travelMode:'auto';
  return validate({...base,...filters(args),intent:'isochrone',startPlace:String(args.startPlace||'').trim(),travelMode:mode,minutes:args.minutes!=null?Math.round(Number(args.minutes)):60});
 }
 if(name==='search_in_polygon'){
  const coords=Array.isArray(args.coordinates)&&args.coordinates.length>=3?args.coordinates.map(p=>[Number(p[0]),Number(p[1])]):null;
  return validate({...base,...filters(args),intent:'polygon',coordinates:coords,startDrawing:!coords});
 }
 if(name==='inspect_movie'){
  return {intent:'movie',filmText:String(args.filmText||'').trim(),category:args.category||'overview',relation:args.relation||undefined};
 }
 if(name==='inspect_place'){
  return {intent:'place_info',placeText:String(args.placeText||'').trim()};
 }
 if(name==='search_song_locations'){
  if(args.placeText&&args.radiusKm!=null)return validate({...base,intent:'song_nearby',placeText:String(args.placeText).trim(),radiusKm:Number(args.radiusKm),songText:args.songText,filmText:args.filmText});
  if(args.placeText)return {intent:'song_at',placeText:String(args.placeText).trim(),songText:args.songText,filmText:args.filmText};
  return {intent:'song_locations',songText:args.songText,filmText:args.filmText};
 }
 if(name==='search_places_by_genre'){
  return {...base,intent:'genre_places',genre:genreName(String(args.genre||''),genres),relation:['filming','narrative','both'].includes(args.relation)?args.relation:'both',yearFrom:Number.isFinite(Number(args.yearFrom))?Number(args.yearFrom):base.yearFrom,yearTo:Number.isFinite(Number(args.yearTo))?Number(args.yearTo):base.yearTo};
 }
 if(name==='update_previous_search'){
  if(!previous)throw Error('There is no active search to refine yet. Ask a spatial, heritage, route, or movie question first.');
  if(previous.intent==='movie'){
   if(!args.category)throw Error('Specify which film category to show (cast, songs, characters, genres, heritage, or locations).');
   return {...previous,category:args.category};
  }
  const patch={};
  if(args.radiusKm!=null){
   if(previous.intent==='route')patch.corridorKm=Number(args.radiusKm);
   else if(['nearby','catalog','song_nearby'].includes(previous.intent))patch.radiusKm=Number(args.radiusKm);
   else throw Error('A radius applies to a nearby, heritage, or route search.');
  }
  if(args.heritageOnly!=null)patch.heritageOnly=Boolean(args.heritageOnly);
  if(args.excludeBroad!=null)patch.excludeBroad=Boolean(args.excludeBroad);
  if(args.relation!=null)patch.relation=args.relation;
  if(args.genre!=null)patch.genre=args.genre?genreName(args.genre,genres):'';
  if(args.yearFrom!=null)patch.yearFrom=Number(args.yearFrom);
  if(args.yearTo!=null)patch.yearTo=Number(args.yearTo);
  if(previous.intent==='catalog'&&Object.keys(patch).some(k=>k!=='radiusKm'))throw Error('Heritage catalogue questions only support radius follow-ups.');
  return validate({...previous,...patch});
 }
 throw Error('Unsupported tool action: '+name);
}

async function defaultAskLLM({message,history,previous,genres,years}){
 const response=await fetch('/api/chat',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({message,history,context:{previous,genres,years}})
 });
 const payload=await response.json().catch(()=>({}));
 if(!response.ok)throw Error(payload.error||'Chat service unavailable ('+response.status+').');
 return payload;
}

function createAssistant(data,{engine=Spatial.createEngine(data),getRegions=async()=>{throw Error('Region boundaries are unavailable. Open through the local demo server.');},askLLM=defaultAskLLM}={}){
 const nodes=data.nodes,edges=data.edges,years=data.summary.year_range,adj=new Map();
 const songIndex=SongTools.createIndex(data);
 edges.forEach((e,i)=>{for(const n of [e[0],e[2]]){if(!adj.has(n))adj.set(n,[]);adj.get(n).push(i);}});
 const films=nodes.map((n,i)=>({node:i,name:n[1],year:n[3]})).filter(f=>nodes[f.node][2]==='Film');
 const title=s=>normalize(s.replace(/\s*\(.*?\)\s*/g,' '));

 function film(text){
  const year=text.match(/(?:\s|\()(19\d{2}|20\d{2})(?:\s+(?:\p{L}+\s+)?film)?\)?$/u),clean=title(year?text.slice(0,year.index):text);
  const found=films.filter(f=>(normalize(f.name)===normalize(text)||title(f.name)===clean)&&(!year||String(f.year)===year[1]));
  if(!found.length)throw Error('No matching film record for “'+text+'” in this build. Try Fanaa (2006) or another exact title.');
  if(found.length>1)throw Error('Several films match. Include the year: '+found.slice(0,8).map(f=>f.name+' ('+f.year+')').join('; '));
  return found[0];
 }

 function decadeCount(text){
  if(!/\b(?:how many|count|number of)\b/i.test(text)||!/\b(?:movies|films)\b/i.test(text)||
     /\b(?:filmed|shot|shoot|location|place|near|around|within|route|distance|set in|story setting)\b/i.test(text))return null;
  const tokens=[...text.matchAll(/\b(?:(?:19|20)\d0s|\d0s)\b/gi)].map(m=>m[0]);
  if(!tokens.length)return null;
  const decades=[...new Set(tokens.map(token=>{
   const digits=token.match(/\d+/)[0],start=digits.length===4?Number(digits):(Number(digits)>=70?1900:2000)+Number(digits);
   return Math.floor(start/10)*10;
  }))];
  const ranges=decades.map(start=>({start,end:start+9,label:(start%100).toString().padStart(2,'0')+'s'}));
  const counts=ranges.map(range=>({range,count:films.filter(f=>{const y=Number(f.year);return Number.isFinite(y)&&y>=range.start&&y<=range.end;}).length}));
  const total=counts.reduce((sum,item)=>sum+item.count,0);
  const lines=counts.map(({range,count})=>range.start+'s ('+range.start+'–'+range.end+'): '+count).join(' · ');
  return {kind:'text',summary:lines+' · Combined: '+total+' recorded film records. Counts use each film’s recorded release year.',plan:null,clearPrevious:true};
 }

 function resolveSinglePlace(placeText,selectedNode,label='place'){
  const found=engine.findPlaces(placeText);
  if(!found.length)throw Error('No geocoded place matches “'+placeText+'”. Use its recorded name, or choose a point with the map tools.');
  if(found.length>1&&selectedNode==null)throw Object.assign(Error('Several places match “'+placeText+'”. Choose the intended '+label+'.'),{choices:found.slice(0,20)});
  const p=selectedNode==null?found[0]:found.find(item=>item.node===selectedNode);
  if(!p)throw Error('The selected place does not match this question. Please choose again.');
  return p;
 }

 function movie(plan){
  const f=film(plan.filmText),category=plan.category,types={cast:'Person',actors:'Person',songs:'Song',characters:'Character',genres:'Genre',heritage:'Heritage',locations:'Place'};
  const items=[];
  for(const edgeIndex of adj.get(f.node)||[]){const e=edges[edgeIndex],other=e[0]===f.node?e[2]:e[0],n=nodes[other];
   if(category!=='overview'){
    if(category==='locations'){if(!['filming','narrative'].includes(e[1])||(plan.relation&&e[1]!==plan.relation))continue;}
    else if(n[2]!==types[category]||(['cast','actors'].includes(category)&&e[1]!=='cast_member'))continue;
   }
   const role=n[2]==='Character'?(adj.get(other)||[]).map(i=>edges[i]).filter(e=>e[1]==='portrays').map(e=>nodes[e[0]][1]).join(', '):'';
   items.push({node:other,name:n[1],type:n[2],relation:e[1],role,edgeIndex});
  }
  const grouped=new Map();for(const i of items){if(!grouped.has(i.type))grouped.set(i.type,new Set());grouped.get(i.type).add(i.node);}
  const counts=Object.fromEntries([...grouped].map(([kind,ids])=>[kind,ids.size]));
  return {kind:'movie',plan,film:f,items,counts,summary:f.name+' · '+f.year+' · '+items.length+' recorded '+(category==='overview'?'connections':category),note:items.length?'Connections come from the supplied graph. Filming and story settings are distinct; film locations are not inherited by individual songs.':'No corresponding links are recorded in this build. This is a data gap, not evidence that the film has none.'};
 }

async function answer(text,previous=null,selection={},history=[],lastAnswer=null){
  const q=String(text||'').trim();
  if(!q||q.length>1000)throw Error('Enter a question between 1 and 1000 characters.');

  const countAnswer=decadeCount(q);
  if(countAnswer)return countAnswer;

  // Relationship-label questions explain the visible result; they must not launch its search again.
  if(lastAnswer&&['genre_places','spatial'].includes(lastAnswer.kind)&&
     /\b(?:filming|filmed|shot|story|narrative|set in)\b/i.test(q)&&
     /\b(?:location|locations|place|places|these|those|results|count|counts)\b/i.test(q)){
   const rel=lastAnswer.plan?.relation||'both';
   if(lastAnswer.kind==='genre_places'){
    const sample=lastAnswer.items?.[0];
    const example=sample?' For example, '+sample.name+' has '+sample.filmingFilmCount+' filming-location links and '+sample.narrativeFilmCount+' story-setting links across '+sample.filmCount+' distinct linked films.':'';
    return {kind:'text',plan:previous,summary:'These results include '+(rel==='both'?'both filming locations and story settings (narrative locations)':rel==='filming'?'filming locations':'story settings (narrative locations)')+'. “Filming” counts distinct linked films with a filming relationship; “Story setting” counts distinct linked films with a narrative relationship. The same film can appear in both counts, while “linked films” counts each film once.'+example};
   }
   return {kind:'text',plan:previous,summary:'This result includes '+(rel==='both'?'both filming locations and story settings (narrative locations)':rel==='filming'?'filming locations only':'story settings (narrative locations) only')+'. These are separate relationship types recorded in the graph.'};
  }

  let plan=selection.plan||null;
  let llmResponse=null;
  if(!plan){
   llmResponse=await askLLM({message:q,history,previous,genres:engine.genres,years});
   if(!llmResponse.toolCall){
    return {kind:'text',plan:previous,summary:llmResponse.reply||help};
   }
   plan=planFromToolCall(llmResponse.toolCall,{previous,genres:engine.genres,years});
  }

  if(plan.intent==='movie')return movie(plan);

  if(plan.intent==='genre_places'){
   const items=engine.placesByGenre(plan);
   const relationLabel={filming:'filming locations',narrative:'story settings',both:'filming locations and story settings'}[plan.relation];
   return {kind:'genre_places',plan,items,summary:items.length+' places connected to '+plan.genre+' films',interpretation:relationLabel+' · '+plan.yearFrom+'–'+plan.yearTo,note:'Ranked by distinct linked films in the graph. The same film may appear in both relationship counts, so those counts can overlap. A place is included only when a recorded film-to-place relationship and that film’s genre are both present.'};
  }

  if(plan.intent==='place_info'){
   const p=resolveSinglePlace(plan.placeText,selection.placeNode);
   plan.placeNode=p.node;plan.placeText=p.name;
   const mapsUrl='https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(p.lat+','+p.lon);
   return {kind:'place_info',plan,place:p,mapsUrl,summary:'Opened place details for '+p.name,interpretation:Spatial.placeLabel(p)+' · '+(p.locality||p.country||'')+' · '+p.lat.toFixed(4)+', '+p.lon.toFixed(4),note:'Explore recorded films, nearby settlements/landmarks, and Google Maps link in the Place Panel.'};
  }

  if(plan.intent==='route'){
   const start=resolveSinglePlace(plan.startPlace,selection.startNode??selection.placeNode,'starting point');
   const end=resolveSinglePlace(plan.endPlace,selection.endNode,'destination');
   plan.startCenter=[start.lat,start.lon];plan.startPlace=start.name;plan.startNode=start.node;
   plan.endCenter=[end.lat,end.lon];plan.endPlace=end.name;plan.endNode=end.node;
   return {kind:'route',plan,summary:'Calculating '+plan.travelMode+' route from '+start.name+' to '+end.name+' ('+plan.corridorKm+' km corridor)…',interpretation:start.name+' → '+end.name+' · '+plan.corridorKm+' km corridor · '+(plan.genre||'all genres')+' · '+plan.yearFrom+'–'+plan.yearTo,note:'Using the Valhalla road routing service. Results will appear on the map below.'};
  }

  if(plan.intent==='isochrone'){
   const start=resolveSinglePlace(plan.startPlace,selection.placeNode,'starting point');
   plan.center=[start.lat,start.lon];plan.startPlace=start.name;plan.placeNode=start.node;
   return {kind:'isochrone',plan,summary:'Calculating '+plan.minutes+'-minute '+plan.travelMode+' reachable area from '+start.name+'…',interpretation:start.name+' · '+plan.minutes+' min ('+plan.travelMode+') · '+(plan.genre||'all genres')+' · '+plan.yearFrom+'–'+plan.yearTo,note:'Using the Valhalla isochrone service. Reachable locations will appear on the map below.'};
  }

  if(plan.intent==='polygon'){
   return {kind:'polygon',plan,summary:plan.startDrawing?'Opened polygon drawing tool on the map below.':'Searching inside custom polygon ('+plan.coordinates.length+' vertices)…',interpretation:plan.startDrawing?'Click points on the map and press Finish area to search.':'Custom polygon · '+(plan.genre||'all genres')+' · '+plan.yearFrom+'–'+plan.yearTo,note:'Polygon containment includes boundary edges.'};
  }

  if(['song_locations','song_nearby','song_at'].includes(plan.intent)){
   let items=songIndex.locations;
   if(plan.songText){const song=songIndex.resolve(plan.songText,plan.filmText);items=items.filter(l=>l.song===song.node);}
   else if(plan.filmText){const f=film(plan.filmText);items=items.filter(l=>l.film===f.node);}
   if(['song_nearby','song_at'].includes(plan.intent)){
    const p=resolveSinglePlace(plan.placeText,selection.placeNode);
    plan.center=[p.lat,p.lon];plan.placeText=p.name;plan.placeNode=p.node;
    if(plan.intent==='song_at')items=items.filter(l=>l.place===p.node);
    else items=items.filter(l=>!['country_reference','locality_reference','unknown_reference'].includes(l.precision)).map(l=>({...l,distanceKm:engine.byNode.has(l.place)?Spatial.distanceKm(plan.center,[engine.byNode.get(l.place).lat,engine.byNode.get(l.place).lon]):Infinity})).filter(l=>l.distanceKm<=plan.radiusKm);
   }
   return {kind:'song_locations',plan,items,summary:items.length+' source-supported song-location links'+(plan.songText?' for '+plan.songText:plan.filmText?' in '+plan.filmText:''),note:'Song locations use explicit song-level evidence, never inherited film locations. Country/route tags do not identify exact camera positions.'};
  }

  let results;
  if(plan.intent==='nearby'||plan.intent==='catalog'){
   const p=resolveSinglePlace(plan.placeText,selection.placeNode);
   plan.center=[p.lat,p.lon];plan.placeText=p.name;plan.placeNode=p.node;
   if(plan.intent==='catalog'){
    const catalog=engine.heritageNearby(plan);
    return {kind:'catalog',plan,items:catalog.items,total:catalog.total,summary:catalog.total+' heritage references within '+plan.radiusKm+' km of '+p.name,
      interpretation:'Named UNESCO properties and documented historic sites. Components are grouped under their parent property.',
      note:'These are reference sites, not inferred film locations. Counts identify direct recorded film links; zero is a coverage gap. Distances use representative points.'};
   }
   results=engine.search(plan);
  }else if(plan.intent==='region'){
   const r=await getRegions();let textRegion=plan.regionText,level;
   let found=r.features.filter(f=>normalize(f.properties.name)===normalize(textRegion));
   if(!found.length){
    if(/\s+district$/i.test(textRegion)){level='ADM2';textRegion=textRegion.replace(/\s+district$/i,'');}
    if(/\s+state$/i.test(textRegion)){level='ADM1';textRegion=textRegion.replace(/\s+state$/i,'');}
    found=r.features.filter(f=>(!level||f.properties.level===level)&&normalize(f.properties.name)===normalize(textRegion));
   }
   if(!found.length)throw Error('No state or district boundary matches “'+plan.regionText+'”. Use a recorded state/district name; nearby queries use place names.');
   if(found.length>1)throw Error('That boundary name is ambiguous. Add “state” or “district”, or choose it in Regions.');
   const f=found[0];plan.regionId=f.properties.id;plan.regionText=f.properties.name;plan.stateId=f.properties.level==='ADM1'?f.properties.id:f.properties.state_id;
   plan.excludePlaces=f.properties.level==='ADM2'?r.broadReferences:r.countryReferences;
   results=engine.searchArea(plan,f);
  }else{
   throw Error('Unsupported search intent.');
  }

  const count=new Set(results.flatMap(r=>r.matches.map(m=>m.place.node))).size;
  return {kind:'spatial',plan,results,summary:results.length+' distinct movie'+(results.length===1?'':'s')+' · '+count+' matching place'+(count===1?'':'s'),interpretation:(plan.intent==='nearby'?'Within '+plan.radiusKm+' km of '+plan.placeText:'Inside the '+plan.regionText+' boundary')+' · '+({filming:'filming',narrative:'story settings',both:'filming and story settings'}[plan.relation])+' · '+(plan.genre||'all genres')+' · '+plan.yearFrom+'–'+plan.yearTo+(plan.heritageOnly?' · heritage locations only':'')+(plan.excludeBroad?' · broad references hidden':''),note:(plan.intent==='nearby'?'Spherical reference-point distance; proximity does not establish filming at the centre.':'Point-in-polygon overlay using the published research boundaries; these may differ from current boundaries.')+' Missing coordinates and missing relationships cannot appear.'};
 }
 return {answer,engine};
}

const api={planFromToolCall,createAssistant,help};
if(typeof module==='object'&&module.exports)module.exports=api;else root.CinemaChat=api;
})(typeof globalThis!=='undefined'?globalThis:this);
