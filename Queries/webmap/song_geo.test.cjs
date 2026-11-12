const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const Song=require('./song_geo.js'),{createAssistant,parseQuestion}=require('./chat_engine.js');
const data={summary:{year_range:[1970,2025]},nodes:[['f','Film','Film','2015'],['s','Song','Song'],['p','City','Place','','','','',{kind:'city'}]],edges:[[1,'in_film',0],[0,'filming',2]],geo:[[2,13,80,'place_representative_point']],songLocations:[]};
const draft={song_id:'s',place_name:'Test railway',latitude:13,longitude:80,source_url:'https://example.org/evidence',evidence:'The video explicitly identifies this song and railway.',location_precision:'route_reference',scene_timestamp:'00:01:23',status:'proposed'};
test('film filming links never become song filming links',async()=>{const a=createAssistant(data);assert.equal((await a.answer('Song locations')).items.length,0);assert.equal((await a.answer('Where was the song Song filmed?')).items.length,0);assert.equal(data.edges.length,2);});
test('song proposal validates identity, coordinate bounds, evidence and timestamps',()=>{
 assert.equal(Song.validateProposal(draft,data).status,'proposed');
 for(const patch of [{song_id:'unknown'},{latitude:91},{longitude:Infinity},{source_url:'javascript:alert(1)'},{source_url:'https://user:pass@example.org'},{evidence:'short'},{scene_timestamp:'00:99:23'},{status:'source_supported'},{location_precision:'camera_position'}])assert.throws(()=>Song.validateProposal({...draft,...patch},data));
 assert.equal(data.songLocations.length,0);
});
test('song nearby queries validate the radius before evaluating evidence',()=>{assert.equal(parseQuestion('Songs within 100 km of Chennai').intent,'song_nearby');assert.throws(()=>parseQuestion('Songs within 2001 km of Chennai'),/2000/);});
test('real explicit song evidence retains route/country precision and pending notes',async()=>{
 const html=fs.readFileSync(path.resolve(__dirname,'../../Dataset/integrated/graph_explorer.html'),'utf8'),start=html.indexOf('const DATA=')+11,end=html.indexOf(';\nif(!DATA',start),snapshot=JSON.parse(html.slice(start,end)),a=createAssistant(snapshot);
 const all=await a.answer('Which songs were taken where?');assert.equal(all.items.length,2);
 const gerua=await a.answer('Where was the song Gerua filmed?');assert.equal(gerua.items.length,1);assert.equal(gerua.items[0].precision,'country_reference');assert.match(gerua.items[0].source,/filminiceland/);
 assert.equal((await a.answer('Which songs were shot in Iceland?')).items.length,1);assert.equal((await a.answer('Where was Gerua song filmed?')).items.length,1);assert.equal((await a.answer('Songs filmed in Chennai')).items.length,0);
 const train=await a.answer('Where was the song Chaiyya Chaiyya filmed?');assert.equal(train.items[0].precision,'route_reference');assert.match(snapshot.nodes[train.items[0].place][1],/Nilgiri/);
 assert.equal((await a.answer('Song locations for Fanaa')).items.length,0);assert.equal(snapshot.songLocationReview.length,48);
 const near=await a.answer('Songs within 2000 km of Iceland');assert.equal(near.items.some(l=>l.precision==='country_reference'),false);
});
