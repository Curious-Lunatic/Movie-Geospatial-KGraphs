const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const Spatial=require('./spatial_engine.js'),{createAssistant,parseQuestion}=require('./chat_engine.js'),Tools=require('./spatial_tools.js');
const nodes=[['f','Example','Film','2006'],['city','Chennai','Place','','','','',{kind:'city',precision:'locality_reference',aliases:['Madras','சென்னை'],locality:'Tamil Nadu, India'}],['fort','Fort St. George','Heritage','','','','https://example.org/fort',{kind:'historic_site',precision:'site_reference',aliases:['Fort Saint George'],locality:'Chennai, Tamil Nadu, India'}],['far','Far heritage','Heritage','','','','',{kind:'heritage_property'}]];
const data={nodes,summary:{year_range:[1970,2025]},geo:[[1,13.0825,80.275,'place_representative_point','India'],[2,13.079722,80.286944,'historic_site_representative_point','India'],[3,15,80,'heritage_property_representative_point','India']],edges:[[0,'filming',1,1,'films:2','https://example.org','City-level source']]};
const filters={center:[13.0825,80.275],radiusKm:10,relation:'filming',genre:'',yearFrom:1970,yearTo:2025};
test('city aliases, Tamil labels and heritage-only search preserve entity identity',()=>{
 const e=Spatial.createEngine(data);for(const q of ['Chennai','Madras','சென்னை'])assert.equal(e.findPlaces(q)[0].node,1);
 assert.equal(e.findPlaces('Chennai',{heritageOnly:true})[0].name,'Fort St. George');
 assert.equal(e.findPlaces('Chennai')[0].heritage,false);assert.match(Spatial.placeLabel(e.byNode.get(1)),/City/);
 assert.match(Spatial.precisionNote(e.byNode.get(1)),/exact filming site is not recorded/);
});
test('reference heritage discovery does not create movie links or promote the city',()=>{
 const e=Spatial.createEngine(data),before=e.search(filters),catalog=e.heritageNearby(filters);
 assert.equal(catalog.total,1);assert.equal(catalog.items[0].name,'Fort St. George');assert.equal(catalog.items[0].directFilmCount,0);
 assert.deepEqual(e.search(filters),before);assert.equal(before[0].matches[0].place.name,'Chennai');
 assert.equal(e.search({...filters,heritageOnly:true}).length,0);
 assert.equal(e.search({...filters,excludeBroad:true}).length,0);
});
test('larger radii include more sites and enforce the new upper bound',()=>{
 const e=Spatial.createEngine(data);assert.equal(e.heritageNearby({...filters,radiusKm:500}).total,2);
 assert.equal(e.heritageNearby({...filters,radiusKm:2000}).total,2);
 assert.throws(()=>e.search({...filters,radiusKm:2001}),/2000/);
 assert.equal(parseQuestion('Movies within 1000 km of Chennai').radiusKm,1000);
 assert.equal(Tools.MAX_CORRIDOR_KM,250);assert(Tools.corridor({type:'LineString',coordinates:[[80,13],[80.1,13.1]]},100));
 assert.throws(()=>Tools.corridor({type:'LineString',coordinates:[[80,13],[80.1,13.1]]},251),/250/);
});
test('heritage chat describes catalogue records and keeps radius context',async()=>{
 const a=createAssistant(data),r=await a.answer('Heritage sites within 100 km of Chennai');assert.equal(r.kind,'catalog');assert.equal(r.items[0].directFilmCount,0);assert.match(r.note,/not inferred film locations/);
 const wider=await a.answer('Within 500 km',r.plan);assert.equal(wider.total,2);
 await assert.rejects(a.answer('Only Romance',r.plan),/Movie genre\/year filters/);
});
test('ambiguous places provide stable choices rather than guessing',async()=>{
 const copy=structuredClone(data);copy.nodes.push(['other','Chennai','Place']);copy.geo.push([4,10,80,'place_representative_point','Other']);const a=createAssistant(copy);
 let error;try{await a.answer('Movies near Chennai');}catch(e){error=e;}
 assert.equal(error.choices.length,2);const answer=await a.answer('Movies near Chennai',null,{placeNode:1});assert.equal(answer.plan.placeNode,1);
 await assert.rejects(a.answer('Movies near Chennai',null,{placeNode:99}),/does not match/);
});
test('real Chennai records distinguish city, official landmark and Mahabalipuram',async()=>{
 const html=fs.readFileSync(path.resolve(__dirname,'../../Dataset/integrated/graph_explorer.html'),'utf8'),start=html.indexOf('const DATA=')+11,end=html.indexOf(';\nif(!DATA',start),data=JSON.parse(html.slice(start,end));
 const a=createAssistant(data),city=a.engine.findPlaces('Chennai')[0];assert.equal(city.kind,'city');assert.equal(city.heritage,false);
 const r=await a.answer('Heritage sites within 100 km of Chennai');assert(r.items.some(p=>p.name==='Fort St. George'&&p.directFilmCount===0));assert(r.items.some(p=>p.name==='Group of Monuments at Mahabalipuram'));assert(r.items.every(p=>p.name!=='Chennai'));
 console.log('Chennai quality benchmark:',r.summary,r.items.map(p=>p.name).join('; '));
});
