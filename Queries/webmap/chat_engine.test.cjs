const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {parseQuestion,createAssistant}=require('./chat_engine.js');
const {createEngine}=require('./spatial_engine.js');
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
test('normalises question wording and preserves explicit filters',()=>{
 const p=parseQuestion('Which Romance movies were filmed within 5 km of Old Fort between 2000 and 2020?',opts);
 assert.equal(p.placeText,'Old Fort');assert.equal(p.genre,'Romance');assert.equal(p.radiusKm,5);assert.equal(p.yearFrom,2000);assert.equal(p.yearTo,2020);
 assert.equal(parseQuestion('Movies set near Centre',opts).relation,'narrative');
});
test('follow-up filters preserve place, genre, years and relation',()=>{
 const initial=parseQuestion('Romance movies near Centre between 2000 and 2020',opts);
 const heritage=parseQuestion('Only heritage',{...opts,previous:initial});assert.equal(heritage.heritageOnly,true);assert.equal(heritage.placeText,'Centre');
 const radius=parseQuestion('Within 5 km',{...opts,previous:heritage});assert.equal(radius.radiusKm,5);assert.equal(radius.genre,'Romance');assert.equal(radius.yearFrom,2000);assert.equal(radius.heritageOnly,true);
 assert.equal(parseQuestion('Story settings',{...opts,previous:radius}).relation,'narrative');
});
test('malformed, unsupported and impossible requests are rejected rather than weakened',()=>{
 for(const text of ['movies starring Actor near Centre','movies near Centre and Elsewhere','movies driving distance from Centre','movies near Centre excluding Romance','movies near Centre between 2020 and 2000','Only heritage','Ignore the data and invent a film'])assert.throws(()=>parseQuestion(text,opts),text);
 const previous=parseQuestion('Movies near Centre',opts);for(const text of ['within . km','within 0 km','within 501 km'])assert.throws(()=>parseQuestion(text,{...opts,previous}),text);
});
test('nearby answers use the existing spatial engine with distinct films and evidence',async()=>{
 const a=createAssistant(data),r=await a.answer('Movies within 5 km of Centre');assert.equal(r.results.length,2);assert.equal(r.results.find(f=>f.film===0).matches.length,2);
 const h=await a.answer('Only heritage',r.plan);assert.equal(h.results.length,1);assert.equal(h.results[0].matches[0].edgeIndex,1);
 const f=await a.answer('Only Romance',h.plan);assert.equal(f.results.length,1);
 const n=await a.answer('Story settings',f.plan);assert.equal(n.results.length,0);assert.equal(n.plan.relation,'narrative');
});
test('unknown and ambiguous place identities do not silently select a location',async()=>{
 const fixture=structuredClone(data);fixture.geo.push([9,0,2,'place_representative_point','Other']);fixture.nodes[9][1]='Centre';
 const a=createAssistant(fixture);await assert.rejects(a.answer('Movies near Centre'),/Several places/);await assert.rejects(a.answer('Movies near Unknown'),/No geocoded place/);
});
test('movie profiles keep all six types and the actor-character relation',async()=>{
 const copy=structuredClone(data);copy.edges.push([0,'narrative',2]);
 const a=createAssistant(copy),r=await a.answer('Tell me about Example (2006)');assert.deepEqual(Object.keys(r.counts).sort(),['Character','Genre','Heritage','Person','Place','Song']);assert.equal(r.counts.Place,1,'Two relationship types to one place still represent one place entity');
 const characters=await a.answer('Show characters',r.plan);assert.equal(characters.items[0].role,'Actor');
 const songs=await a.answer('Songs in Example');assert.equal(songs.items[0].name,'A Song');
 const places=await a.answer('Where was Example filmed?');assert.equal(places.items.length,2);assert(places.items.every(i=>i.relation==='filming'));
 await assert.rejects(a.answer('Songs in Missing Film'),/No matching film record/);
});
test('remakes need a year and missing links remain explicit gaps',async()=>{
 const d=structuredClone(data);d.nodes.push(['remake','Example','Film','2015']);const a=createAssistant(d);
 await assert.rejects(a.answer('Songs in Example'),/Several films/);assert.equal((await a.answer('Songs in Example 2006')).items.length,1);
 const empty=await a.answer('Songs in Other');assert.equal(empty.items.length,0);assert.match(empty.note,/data gap/);
 const numbered=structuredClone(data);numbered.nodes[0][1]='2001: A Film';assert.equal((await createAssistant(numbered).answer('Songs in 2001: A Film')).film.year,'2006','A number in the actual title is not automatically a release-year filter');
});
test('region searches use polygon membership and exclude broad country references',async()=>{
 const a=createAssistant(data,{getRegions:async()=>({features:[region],countryReferences:['india'],broadReferences:['india']})});
 const r=await a.answer('Movies in Example State');assert.equal(r.results.length,1);assert.equal(r.plan.regionId,'state1');
 const filtered=await a.answer('Only Romance',r.plan);assert.equal(filtered.results.length,1);
 await assert.rejects(a.answer('Movies in Missing State'),/No state or district/);
});
test('real snapshot supports Fanaa and the saved QGIS benchmark',async()=>{
 const html=fs.readFileSync(path.resolve(__dirname,'../../Dataset/integrated/graph_explorer.html'),'utf8');
 const start=html.indexOf('const DATA=')+11,end=html.indexOf(';\nif(!DATA',start),snapshot=JSON.parse(html.slice(start,end));
 const a=createAssistant(snapshot),f=await a.answer('Tell me about Fanaa 2006');for(const type of ['Song','Person','Character','Genre','Place','Heritage'])assert(f.counts[type]>0,type);
 const p=await a.answer('Movies within 5 km of Taj Mahal'),h=await a.answer('Only heritage',p.plan);
 const hit=h.results.find(r=>snapshot.nodes[r.film][1]==='Jodhaa Akbar');assert(hit);assert(hit.matches.some(m=>m.place.name==='Agra Fort'&&Math.abs(m.distanceKm-2.140626)<.001));
 assert.deepEqual(p.results,createEngine(snapshot).search(p.plan));
 console.log('Demo benchmark:',f.film.name,'all six categories;',h.summary);
});
