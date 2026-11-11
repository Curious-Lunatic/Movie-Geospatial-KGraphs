/* Dataset-backed conversational queries. Parsing and answers are deterministic. */
(function(root){
'use strict';
const Spatial=typeof module==='object'&&module.exports?require('./spatial_engine.js'):root.SpatialSearch;
const normalize=s=>String(s).normalize('NFKD').replace(/\p{M}/gu,'').toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();
const help='Try “Movies within 5 km of Taj Mahal”, “Romance movies in Rajasthan”, “Where was Fanaa filmed?” or “Songs in Fanaa”. Follow a spatial search with “within 10 km”, “only heritage”, “only Romance” or “between 2000 and 2020”. Road routes and travel-time questions use the map tools.';
function defaults(years){return {radiusKm:10,relation:'filming',genre:'',yearFrom:years[0],yearTo:years[1],heritageOnly:false};}
function genreName(text,genres){const g=genres.find(g=>normalize(g)===normalize(text));if(!g)throw Error('Unknown genre. Recorded genres: '+genres.join(', ')+'.');return g;}
function validate(plan){
 if(plan.yearFrom>plan.yearTo)throw Error('The start year must not be later than the end year.');
 if(!Number.isFinite(plan.radiusKm)||plan.radiusKm<.1||plan.radiusKm>500)throw Error('Choose a radius between 0.1 and 500 km.');
 return plan;
}
function parseQuestion(text,{previous=null,genres=[],years=[1970,2025]}={}){
 let q=String(text).trim().replace(/[?.!]+$/,'').trim();
 if(!q||q.length>500)throw Error('Enter a question between 1 and 500 characters.');
 if(/^(help|examples|what can (?:you|i) (?:do|ask))$/i.test(q))return {intent:'help'};
 const base=defaults(years),spatial=previous&&['nearby','region'].includes(previous.intent);
 let m;
 if((m=q.match(/^(?:show\s+)?(cast|actors|songs|characters|genres|heritage(?: sites)?|locations)$/i))&&previous?.intent==='movie')return {...previous,category:normalize(m[1]).split(' ')[0]};
 if(spatial){
  let patch=null;
  if((m=q.match(/^(?:within|radius(?: of)?|make (?:it|that))\s+([\d.]+)\s*km$/i))){if(previous.intent!=='nearby')throw Error('A radius applies to a nearby search. Ask for movies near a named place first.');patch={radiusKm:Number(m[1])};}
  else if(/^(?:only )?heritage(?: (?:locations|sites))?(?: only)?$/i.test(q))patch={heritageOnly:true};
  else if(/^(?:all|any) (?:locations|places)$/i.test(q))patch={heritageOnly:false};
  else if(/^(?:only )?(?:filming(?: locations)?|shot)$/i.test(q))patch={relation:'filming'};
  else if(/^(?:only )?(?:story settings|narrative(?: locations)?|set)$/i.test(q))patch={relation:'narrative'};
  else if(/^(?:both|both relationships)$/i.test(q))patch={relation:'both'};
  else if(/^(?:all|any) genres$/i.test(q))patch={genre:''};
  else if((m=q.match(/^(?:between|from) (\d{4}) (?:and|to) (\d{4})$/i)))patch={yearFrom:+m[1],yearTo:+m[2]};
  else if((m=q.match(/^(after|before|in) (\d{4})$/i)))patch=m[1].toLowerCase()==='after'?{yearFrom:+m[2]+1}:m[1].toLowerCase()==='before'?{yearTo:+m[2]-1}:{yearFrom:+m[2],yearTo:+m[2]};
  else if((m=q.match(/^only (.+?)(?: movies| films)?$/i)))patch={genre:genreName(m[1],genres)};
  if(patch)return validate({...previous,...patch});
 }
 if((m=q.match(/^where (?:was|is|were) (.+?) (filmed|shot|set)$/i)))return {intent:'movie',filmText:m[1],category:'locations',relation:m[2].toLowerCase()==='set'?'narrative':'filming'};
 if((m=q.match(/^(?:show\s+)?(?:the\s+)?(cast|actors|songs|characters|genres|heritage(?: sites)?|locations) (?:of|in|for) (.+)$/i)))return {intent:'movie',filmText:m[2],category:normalize(m[1]).split(' ')[0]};
 if((m=q.match(/^(?:tell me about|show (?:the )?connections (?:of|for)|explore) (.+)$/i)))return {intent:'movie',filmText:m[1],category:'overview'};
 q=q.replace(/^(which|what)\s+/i,'').replace(/\b(movies|films)\s+(?:were|are)\s+/i,'$1 ');
 let yearFrom=base.yearFrom,yearTo=base.yearTo;
 if((m=q.match(/\s+(?:between|from)\s+(\d{4})\s+(?:and|to)\s+(\d{4})$/i))){yearFrom=+m[1];yearTo=+m[2];q=q.slice(0,m.index);}
 else if((m=q.match(/\s+(after|before|in)\s+(\d{4})$/i))){if(m[1].toLowerCase()==='after')yearFrom=+m[2]+1;else if(m[1].toLowerCase()==='before')yearTo=+m[2]-1;else yearFrom=yearTo=+m[2];q=q.slice(0,m.index);}
 if((m=q.match(/^(?:(?:show|find|list)\s+)?(?:(.+?)\s+)?(?:movies|films)(?:\s+(filmed|shot|set))?\s+in\s+(.+)$/i))){
  if(/\b(?:and|or|except|excluding|starring|without)\b/i.test(m[3]))throw Error('Use one state or district and the supported genre/year filters.');
  return validate({...base,intent:'region',regionText:m[3],genre:m[1]?genreName(m[1],genres):'',relation:m[2]?.toLowerCase()==='set'?'narrative':'filming',yearFrom,yearTo});
 }
 if(/\b(?:near|around|within)\b/i.test(q)){
  const parsed=Spatial.parseQuery(q,genres,years);
  if(parsed.place===null)throw Error('Use a place name in chat, for example “Movies within 5 km of Taj Mahal”.');
  return validate({...parsed,intent:'nearby',placeText:parsed.place,yearFrom,yearTo});
 }
 throw Error(help);
}
function createAssistant(data,{engine=Spatial.createEngine(data),getRegions=async()=>{throw Error('Region boundaries are unavailable. Open through the local demo server.');}}={}){
 const nodes=data.nodes,edges=data.edges,years=data.summary.year_range,adj=new Map();
 edges.forEach((e,i)=>{for(const n of [e[0],e[2]]){if(!adj.has(n))adj.set(n,[]);adj.get(n).push(i);}});
 const films=nodes.map((n,i)=>({node:i,name:n[1],year:n[3]})).filter(f=>nodes[f.node][2]==='Film');
 const title=s=>normalize(s.replace(/\s*\(.*?\)\s*/g,' '));
 function film(text){
  const year=text.match(/(?:\s|\()(19\d{2}|20\d{2})(?:\s+(?:\p{L}+\s+)?film)?\)?$/u),clean=title(year?text.slice(0,year.index):text);
  const found=films.filter(f=>(normalize(f.name)===normalize(text)||title(f.name)===clean)&&(!year||String(f.year)===year[1]));
  if(!found.length)throw Error('No matching film record for “'+text+'” in this build. Try Fanaa (2006) or another exact title. Missing records do not establish that a film has no locations.');
  if(found.length>1)throw Error('Several films match. Include the year: '+found.slice(0,8).map(f=>f.name+' ('+f.year+')').join('; '));
  return found[0];
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
 async function answer(text,previous=null){
  const plan=parseQuestion(text,{previous,genres:engine.genres,years});
  if(plan.intent==='help')return {kind:'help',plan,summary:help};
  if(plan.intent==='movie')return movie(plan);
  let results;
  if(plan.intent==='nearby'){
   const found=engine.findPlaces(plan.placeText);
   if(!found.length)throw Error('No geocoded place matches “'+plan.placeText+'”. Use its recorded name, or choose a point with the map tools.');
   if(found.length>1)throw Error('Several places match “'+plan.placeText+'”. Refine the name: '+found.slice(0,6).map(p=>p.name+' ('+(p.country||'country not recorded')+', '+p.lat.toFixed(3)+', '+p.lon.toFixed(3)+')').join('; '));
   const p=found[0];plan.center=[p.lat,p.lon];plan.placeText=p.name;plan.placeNode=p.node;
   results=engine.search(plan);
  }else{
   const r=await getRegions();let text=plan.regionText,level;
   let found=r.features.filter(f=>normalize(f.properties.name)===normalize(text));
   if(!found.length){
    if(/\s+district$/i.test(text)){level='ADM2';text=text.replace(/\s+district$/i,'');}
    if(/\s+state$/i.test(text)){level='ADM1';text=text.replace(/\s+state$/i,'');}
    found=r.features.filter(f=>(!level||f.properties.level===level)&&normalize(f.properties.name)===normalize(text));
   }
   if(!found.length)throw Error('No state or district boundary matches “'+plan.regionText+'”. Use a recorded state/district name; nearby queries use place names.');
   if(found.length>1)throw Error('That boundary name is ambiguous. Add “state” or “district”, or choose it in Regions.');
   const f=found[0];plan.regionId=f.properties.id;plan.regionText=f.properties.name;plan.stateId=f.properties.level==='ADM1'?f.properties.id:f.properties.state_id;
   plan.excludePlaces=f.properties.level==='ADM2'?r.broadReferences:r.countryReferences;
   results=engine.searchArea(plan,f);
  }
  const count=new Set(results.flatMap(r=>r.matches.map(m=>m.place.node))).size;
  return {kind:'spatial',plan,results,summary:results.length+' distinct movie'+(results.length===1?'':'s')+' · '+count+' matching place'+(count===1?'':'s'),interpretation:(plan.intent==='nearby'?'Within '+plan.radiusKm+' km of '+plan.placeText:'Inside the '+plan.regionText+' boundary')+' · '+({filming:'filming',narrative:'story settings',both:'filming and story settings'}[plan.relation])+' · '+(plan.genre||'all genres')+' · '+plan.yearFrom+'–'+plan.yearTo+(plan.heritageOnly?' · heritage locations only':''),note:(plan.intent==='nearby'?'Spherical reference-point distance; proximity does not establish filming at the centre.':'Point-in-polygon overlay using the published research boundaries; these may differ from current boundaries.')+' Missing coordinates and missing relationships cannot appear.'};
 }
 return {answer,engine};
}
const api={parseQuestion,createAssistant,help};if(typeof module==='object'&&module.exports)module.exports=api;else root.CinemaChat=api;
})(typeof globalThis!=='undefined'?globalThis:this);
