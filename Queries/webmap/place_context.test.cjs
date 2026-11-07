const test=require('node:test'),assert=require('node:assert/strict');
const {createPlaceContext}=require('./place_context.js');
test('Keeps direct filming distinct from story settings and includes documented components once',()=>{
 const nodes=[['f','Film','Film','2001'],['p','Palace','Heritage','','','', 'https://example.org/site'],['c','Court','Heritage'],['g','Another film','Film','2002']];
 const describe=createPlaceContext({nodes,edges:[[2,'part_of_heritage',1],[0,'filming',2,2,'record','https://example.org/film','Court filmed'],[0,'narrative',1,1,'record','','Story'],[3,'filming',1,1,'record','','Palace']],placeDetails:{p:{description:'Historic palace'}}});
 const result=describe(1);assert.equal(result.films.length,2);assert.equal(result.description,'Historic palace');
 assert.deepEqual(result.films.find(f=>f.node===0).connections.map(c=>c.relation).sort(),['filming','narrative']);
 assert.equal(result.films.find(f=>f.node===0).connections.find(c=>c.relation==='filming').place,'Court');
 assert.equal(describe(undefined),null);assert.equal(describe(2).films.length,1);
});
test('No connection inferred from geographic proximity or missing node',()=>{
 const describe=createPlaceContext({nodes:[['p','Site','Place']],edges:[]});
 assert.deepEqual(describe(0).films,[]);assert.equal(describe(99),null);
});
