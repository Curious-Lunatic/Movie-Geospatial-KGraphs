const test=require('node:test'),assert=require('node:assert/strict'),handler=require('./places');
const q=s=>new URLSearchParams(s);
test('rejects absent coordinates, out-of-range latitudes and unbounded searches',()=>{
 for(const args of ['lat=&lng=0','lat=91&lng=0','lat=0&lng=0&radius=500','lat=0&lng=0&category=constructor'])
 assert.throws(()=>handler.parse(q('action=nearby&'+args)));
});
test('Jaipur settlement resolves from the bundled gazetteer',async()=>{
 delete process.env.GEONAMES_USERNAME;
 const res={setHeader(){},status(n){assert.equal(n,200);return this;},json(body){assert.match(body.items[0].name,/Jaipur/i);assert.ok(Math.abs(body.items[0].distanceKm-3.23)<0.02);}};
 await handler({method:'GET',url:'/api/places?action=profile&lat=26.915&lng=75.820'},res);
});
test('article links must lead to Wikipedia',async()=>{
 const result=await handler.lookup({action:'articles',lat:1,lng:2,radius:5},'test',async()=>({ok:true,json:async()=>({geonames:['en.wikipedia.org/wiki/Test','untrusted.example/x'].map(wikipediaUrl=>({title:'Test',lat:1,lng:2,wikipediaUrl}))})}));
 assert.equal(result.items.length,1);assert.equal(result.items[0].distanceKm,0);
});
