const {test}=require('node:test');
const assert=require('node:assert/strict');
const {planFromToolCall,createAssistant}=require('./chat_engine.js');
const data={summary:{year_range:[1970,2025]},nodes:[
 ['f1','Example (2006 film)','Film','2006'],['f2','Other','Film','2018'],
 ['p1','Centre','Place'],['h1','Old Fort','Heritage'],['g1','Romance','Genre'],
 ['s1','A Song','Song'],['a1','Actor','Person'],['c1','A Character','Character'],
 ['india','India','Place'],['p2','Far Point','Place']
],geo:[[2,0,0,'place_representative_point','India'],[3,0,.01,'heritage_property_representative_point','India'],[8,0,0,'place_representative_point','India'],[9,0,2,'place_representative_point','India']],edges:[
 [0,'filming',2,1,'source.csv:2','',''],[0,'filming',3,2,'heritage.csv:3','https://example.org/source','Recorded filming evidence'],[0,'genre',4],
 [5,'in_film',0,1,'songs.csv:4'],[0,'cast_member',6],[6,'portrays',7],[7,'character_in_film',0],
 [1,'narrative',2],[1,'filming',8],[1,'filming',9]
]};
const region={type:'Feature',properties:{id:'state1',name:'Example State',level:'ADM1'},geometry:{type:'Polygon',coordinates:[[[-.1,-.1],[.1,-.1],[.1,.1],[-.1,.1],[-.1,-.1]]]}};
const opts={genres:['Romance','Drama'],years:[1970,2025]};

test('planFromToolCall normalizes nearby, route, isochrone, polygon, and follow-up plans',()=>{
 const p=planFromToolCall({name:'search_movies_nearby',args:{placeText:'Old Fort',genre:'Romance',radiusKm:5,yearFrom:2000,yearTo:2020}},opts);
 assert.equal(p.intent,'nearby');assert.equal(p.placeText,'Old Fort');assert.equal(p.genre,'Romance');assert.equal(p.radiusKm,5);

 const follow=planFromToolCall({name:'update_previous_search',args:{heritageOnly:true}},{...opts,previous:p});
 assert.equal(follow.heritageOnly,true);assert.equal(follow.placeText,'Old Fort');

 const route=planFromToolCall({name:'search_movies_along_route',args:{startPlace:'Centre',endPlace:'Far Point',corridorKm:15,travelMode:'auto'}},opts);
 assert.equal(route.intent,'route');assert.equal(route.corridorKm,15);

 const iso=planFromToolCall({name:'search_reachable_locations',args:{startPlace:'Centre',minutes:45,travelMode:'bicycle'}},opts);
 assert.equal(iso.intent,'isochrone');assert.equal(iso.minutes,45);assert.equal(iso.travelMode,'bicycle');

 const poly=planFromToolCall({name:'search_in_polygon',args:{}},opts);
 assert.equal(poly.intent,'polygon');assert.equal(poly.startDrawing,true);
});

test('planFromToolCall validates bounds and rejects invalid updates',()=>{
 assert.throws(()=>planFromToolCall({name:'search_movies_nearby',args:{placeText:'Centre',radiusKm:2001}},opts));
 assert.throws(()=>planFromToolCall({name:'search_movies_along_route',args:{startPlace:'Centre',endPlace:'Far Point',corridorKm:300}},opts));
 assert.throws(()=>planFromToolCall({name:'search_reachable_locations',args:{startPlace:'Centre',minutes:200}},opts));
 assert.throws(()=>planFromToolCall({name:'update_previous_search',args:{heritageOnly:true}},opts));
});

test('assistant executes LLM tool calls against spatial engine, region, movie, place_info, and text replies',async()=>{
 const queue=[
  {toolCall:{name:'search_movies_nearby',args:{placeText:'Centre',radiusKm:5}}},
  {toolCall:{name:'update_previous_search',args:{heritageOnly:true}}},
  {toolCall:{name:'search_movies_in_region',args:{regionText:'Example State'}}},
  {toolCall:{name:'inspect_movie',args:{filmText:'Example 2006',category:'overview'}}},
  {toolCall:{name:'inspect_place',args:{placeText:'Old Fort'}}},
  {toolCall:{name:'search_movies_along_route',args:{startPlace:'Centre',endPlace:'Far Point',corridorKm:20}}},
  {toolCall:null,reply:'Distances use spherical coordinates on the web map.'}
 ];
 const a=createAssistant(data,{
  getRegions:async()=>({features:[region],countryReferences:['india'],broadReferences:['india']}),
  askLLM:async()=>queue.shift()
 });

 const r=await a.answer('Movies within 5 km of Centre');
 assert.equal(r.kind,'spatial');assert.equal(r.results.length,2);

 const h=await a.answer('Only heritage',r.plan);
 assert.equal(h.results.length,1);assert.equal(h.results[0].matches[0].edgeIndex,1);

 const reg=await a.answer('Movies in Example State');
 assert.equal(reg.kind,'spatial');assert.equal(reg.plan.regionId,'state1');

 const mov=await a.answer('Tell me about Example 2006');
 assert.equal(mov.kind,'movie');assert.deepEqual(Object.keys(mov.counts).sort(),['Character','Genre','Heritage','Person','Place','Song']);

 const plc=await a.answer('Explore Old Fort');
 assert.equal(plc.kind,'place_info');assert.match(plc.mapsUrl,/google\.com\/maps/);

 const rt=await a.answer('Route from Centre to Far Point');
 assert.equal(rt.kind,'route');assert.equal(rt.plan.startPlace,'Centre');assert.equal(rt.plan.endPlace,'Far Point');

 const txt=await a.answer('How are distances calculated?');
 assert.equal(txt.kind,'text');assert.match(txt.summary,/spherical/);
});
