// Vercel Function. UI and future conversational clients share this contract.
const cache=new Map(), pending=new Map();
const categories={towns:'P',landmarks:'S',water:'H',terrain:'T',areas:'L'};
const fail=(message,status)=>Object.assign(new Error(message),{status});
function number(q,key,min,max){
 const raw=q.get(key),n=Number(raw);
 if(!raw?.trim()||!Number.isFinite(n)||n<min||n>max)throw fail('Invalid '+key,400);
 return n;
}
function parse(q){
 const action=q.get('action');
 if(!['profile','nearby','articles'].includes(action))throw fail('Unknown place operation.',400);
 const lat=number(q,'lat',-90,90),lng=number(q,'lng',-180,180),radius=Number(q.get('radius')??5),category=q.get('category')??'towns';
 if(![1,5,10].includes(radius)||!Object.hasOwn(categories,category))throw fail('Invalid radius or category.',400);
 return {action,lat,lng,radius,category};
}
async function lookup(tool,user,fetcher=fetch){
 const {action,lat,lng,radius,category}=tool;
 const endpoint=action==='articles'?'findNearbyWikipediaJSON':action==='profile'?'findNearbyPlaceNameJSON':'findNearbyJSON';
 const params={lat,lng,radius:action==='profile'?30:radius,maxRows:action==='profile'?1:12,lang:'en',username:user};
 if(action==='nearby')params.featureClass=categories[category];
 if(action!=='articles')params.style='FULL';
 const r=await fetcher('https://secure.geonames.org/'+endpoint+'?'+new URLSearchParams(params),{signal:AbortSignal.timeout(9000)});
 if(!r.ok)throw fail('GeoNames is temporarily unavailable.',502);
 const d=await r.json();
 if(d.status||!Array.isArray(d.geonames))throw fail('GeoNames could not complete this lookup.',503);
 const items=d.geonames.map(x=>{
  if(action==='articles'){
   let url;try{url=new URL(/^https?:/.test(x.wikipediaUrl)?x.wikipediaUrl:'https://'+x.wikipediaUrl);if(!url.hostname.endsWith('.wikipedia.org'))return null;url.protocol='https:';}catch{return null;}
   const thumb=String(x.thumbnailImg||'').replace(/^http:/,'https:');
   return {name:x.title,summary:x.summary,url:url.href,thumbnail:/^https:\/\/upload\.wikimedia\.org\//.test(thumb)?thumb:null,lat:Number(x.lat),lng:Number(x.lng)};
  }
  return {name:x.name,id:x.geonameId,kind:x.fcodeName||x.fcode,region:[x.adminName2,x.adminName1,x.countryName].filter(Boolean).join(', '),population:Number(x.population)||null,elevation:x.elevation??null,timezone:x.timezone?.timeZoneId||null,aliases:(x.alternateNames||[]).filter(a=>['hi','en'].includes(a.lang)).slice(0,5).map(a=>a.name),lat:Number(x.lat),lng:Number(x.lng),url:'https://www.geonames.org/'+Number(x.geonameId)};
 }).filter(x=>x&&x.name&&Number.isFinite(x.lat)&&Number.isFinite(x.lng));
 for(const x of items)x.distanceKm=distance(lat,lng,x.lat,x.lng);
 return {version:1,action,source:'GeoNames',items};
}
function distance(a,b,c,d){
 const rad=Math.PI/180,h=Math.sin((c-a)*rad/2)**2+Math.cos(a*rad)*Math.cos(c*rad)*Math.sin((d-b)*rad/2)**2;
 return 12742*Math.asin(Math.sqrt(Math.min(1,h)));
}
function settlements({action,lat,lng,radius}){
 const limit=action==='profile'?30:radius;
 const items=[];
 for(const [id,name,y,x,country,population,timezone] of require('./cities.json')){
  if(Math.abs(y-lat)>limit/110)continue;
  const km=distance(lat,lng,y,x);if(km<=limit)items.push({id,name,lat:y,lng:x,region:country,population,timezone,kind:'Settlement',distanceKm:km,url:'https://www.geonames.org/'+id});
 }
 items.sort((a,b)=>a.distanceKm-b.distanceKm);
 return {version:1,action,source:'GeoNames cities15000 index',items:items.slice(0,action==='profile'?1:12)};
}
async function handler(req,res){
 try{
  if(req.method!=='GET'){res.setHeader('Allow','GET');throw fail('GET required.',405);}
  const tool=parse(new URL(req.url,'http://local').searchParams),key=JSON.stringify(tool);
  const canUseIndex=tool.action==='profile'||(tool.action==='nearby'&&tool.category==='towns');
  if(!process.env.GEONAMES_USERNAME&&!canUseIndex)throw fail('Live GeoNames lookups are not enabled yet. Explore settlements or movies nearby instead.',503);
  let entry=cache.get(key);
  if(!entry||entry.until<Date.now()){
   if(!pending.has(key))pending.set(key,(async()=>{
    if(process.env.GEONAMES_USERNAME){try{return await lookup(tool,process.env.GEONAMES_USERNAME);}catch(e){if(!canUseIndex)throw e;}}
    return settlements(tool);
   })().finally(()=>pending.delete(key)));
   entry={value:await pending.get(key),until:Date.now()+3600000};
   if(cache.size>=256)cache.delete(cache.keys().next().value);cache.set(key,entry);
  }
  res.setHeader('Cache-Control','public, s-maxage=86400, stale-while-revalidate=604800');res.status(200).json(entry.value);
 }catch(e){res.setHeader('Cache-Control','no-store');res.status(e.status||502).json({error:e.status?e.message:'Place lookup temporarily unavailable.'});}
}
module.exports=handler;
module.exports.parse=parse;module.exports.lookup=lookup;
