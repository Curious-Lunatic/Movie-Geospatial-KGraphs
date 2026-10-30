const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const S=require('./spatial_tools');
const {createEngine}=require('./spatial_engine');
const T=require('./vendor/turf.min');
const square={type:'Polygon',coordinates:[[[0,0],[2,0],[2,2],[0,2],[0,0]],[[.5,.5],[.5,1.5],[1.5,1.5],[1.5,.5],[.5,.5]]]};
const fixture={nodes:[['f1','First','Film','2001'],['f2','Second','Film','2002'],['p1','Near','Place'],['p2','Far','Place'],['p3','In hole','Heritage']],geo:[[2,.1,.1,'','',''],[3,3,3,'','',''],[4,1,1,'','','']],edges:[[0,'filming',2],[0,'filming',3],[1,'narrative',2],[1,'filming',4]]};
const filters={relation:'filming',yearFrom:1970,yearTo:2025,genre:'',heritageOnly:false};
test('polygon containment respects holes, multipolygons and outer boundaries',()=>{
 assert(S.contains(square,{lat:.1,lon:.1}));assert(!S.contains(square,{lat:1,lon:1}));assert(S.contains(square,{lat:0,lon:1}));
 const multi={type:'MultiPolygon',coordinates:[square.coordinates,[[[4,4],[5,4],[5,5],[4,5],[4,4]]]]};assert(S.contains(multi,{lat:4.5,lon:4.5}));assert(!S.contains(multi,{lat:3,lon:3}));
});
test('draw rejects crossed/degenerate rings and closes valid rings',()=>{
 assert.throws(()=>S.polygon([[0,0],[1,1]]));assert.throws(()=>S.polygon([[0,0],[2,2],[0,2],[2,0]]));assert.throws(()=>S.polygon([[0,0],[0,1],[0,2]]));
 const p=S.polygon([[0,0],[0,1],[1,1]]);assert.deepEqual(p.geometry.coordinates[0][0],p.geometry.coordinates[0].at(-1));
});
test('area selection shares movie filters and keeps distance undefined for areas',()=>{
 const engine=createEngine(fixture),matches=engine.searchArea(filters,square);assert.equal(matches.length,1);assert.equal(matches[0].film,0);assert.equal(matches[0].distanceKm,null);assert.equal(matches[0].matches.length,1);
 assert.equal(engine.searchArea({...filters,relation:'both'},square).length,2);assert.equal(engine.searchArea({...filters,yearFrom:2002},square).length,0);
});
test('route corridor follows bent roads, not the endpoint straight line',()=>{
 const line={type:'LineString',coordinates:[[0,0],[0,1],[1,1]]};const area=S.corridor(line,2);
 assert(S.contains(area,{lat:.5,lon:.01}));assert(!S.contains(area,{lat:.5,lon:.5}));assert(S.routeDistance({lat:.5,lon:.01},line)<1.2);assert.throws(()=>S.corridor(line,0));
});
test('overlapping analysis polygons deduplicate each movie-place edge',()=>{
 const engine=createEngine(fixture);const p=T.polygon([[[0,0],[2,0],[2,2],[0,2],[0,0]]]);const found=engine.searchArea(filters,[p,p]);assert.equal(found.find(r=>r.film===0).matches.length,1);
});
test('routing handles rate limits and malformed shapes without fake results',async()=>{
 const r=S.createRouter({fetcher:async()=>({ok:false,status:429})});await assert.rejects(r.route([1,2],[2,3],'auto'),/busy/);
 const bad=S.createRouter({fetcher:async()=>({ok:true,json:async()=>({routes:[]})})});await assert.rejects(bad.route([1,2],[2,3],'auto'),/No road route/);
 assert.throws(()=>S.polygonFeatures({features:[{geometry:{type:'Point'}}]}),/No reachable/);
});
test('routing validates time, caches repeated work and forwards cancellation',async()=>{
 let calls=0;const router=S.createRouter({fetcher:async(url,options)=>{calls++;assert(url.includes('costing'));assert.equal(options.headers['X-Client-Id'],'places-and-stories.vercel.app');return {ok:true,json:async()=>({routes:[{geometry:{type:'LineString',coordinates:[[0,0],[1,1]]},distance:10,duration:20}]})};}});
 const a=await router.route([0,0],[1,1],'auto'),b=await router.route([0,0],[1,1],'auto');assert.equal(calls,1);assert.deepEqual(a,b);await assert.rejects(router.reachable([0,0],500,'auto'),/5 and 120/);
 const abort=new AbortController();const pending=S.createRouter({fetcher:async(url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(new Error('aborted'))))}).route([0,0],[1,1],'auto',abort.signal);abort.abort();await assert.rejects(pending,/cancelled/);
});
test('published boundaries and precomputed joins agree for Jaipur and Agra',()=>{
 const base=path.join(__dirname,'data'),regions=JSON.parse(fs.readFileSync(path.join(base,'india_regions.geojson'))),membership=JSON.parse(fs.readFileSync(path.join(base,'region_membership.json')));
 assert.equal(regions.features.filter(f=>f.properties.level==='ADM1').length,36);assert.equal(regions.features.filter(f=>f.properties.level==='ADM2').length,735);
 const rajasthan=regions.features.find(f=>f.properties.name==='Rajasthan'&&f.properties.level==='ADM1');assert(rajasthan);assert(S.contains(rajasthan,{lat:26.9124,lon:75.7873}));assert(!S.contains(rajasthan,{lat:27.179806,lon:78.021528}));
 const agra=regions.features.find(f=>f.properties.level==='ADM2'&&f.properties.name==='Agra');assert(agra);assert(membership['heritage:251'].includes(agra.properties.id));
});
test('broad-reference exclusions apply before movie aggregation',()=>{
 const engine=createEngine(fixture);assert.equal(engine.searchArea({...filters,excludePlaces:['p1']},square).length,0);
});
