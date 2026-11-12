/* Song locations require explicit song-level evidence. Film locations are not inherited. */
(function(root){
'use strict';
const Spatial=typeof module==='object'&&module.exports?require('./spatial_engine.js'):root.SpatialSearch;
const precisionLabels={site_reference:'Named-site reference point',route_reference:'Railway/route reference; exact segment unavailable',locality_reference:'City/locality-level reference',country_reference:'Country-level reference; exact site unavailable',unknown_reference:'Precision unknown'};
function createIndex(data){
 const filmBySong=new Map(data.edges.filter(e=>e[1]==='in_film').map(e=>[e[0],e[2]]));
 const songs=data.nodes.map((n,i)=>({node:i,id:n[0],title:n[1],film:filmBySong.get(i)})).filter(s=>data.nodes[s.node][2]==='Song').map(s=>({...s,filmTitle:s.film==null?'Film not recorded':data.nodes[s.film][1],year:s.film==null?'':data.nodes[s.film][3]}));
 const byNode=new Map(songs.map(s=>[s.node,s]));
 const locations=(data.songLocations||[]).map(l=>({...l,songInfo:byNode.get(l.song),placeName:data.nodes[l.place][1]}));
 return {songs,locations,find(text){const q=Spatial.normalize(text);return songs.filter(s=>Spatial.normalize(s.title+' '+s.filmTitle+' '+s.year).includes(q)).slice(0,12);},resolve(text,filmText=''){
  const found=songs.filter(s=>Spatial.normalize(s.title)===Spatial.normalize(text)&&(!filmText||Spatial.normalize(s.filmTitle+' '+s.year).includes(Spatial.normalize(filmText))));
  if(!found.length)throw Error('No matching song record. Try Gerua or Chaiyya Chaiyya.');
  if(found.length>1)throw Error('Several songs share this title. Include the film: '+found.slice(0,6).map(s=>s.title+' from '+s.filmTitle).join('; '));
  return found[0];
 }};
}
function validateProposal(value,data){
 const fail=message=>{throw Error(message);};
 if(value.status&&value.status!=='proposed')fail('New geotags must remain proposed until evidence review.');
 if(!data.nodes.some(n=>n[0]===value.song_id&&n[2]==='Song'))fail('Choose an existing song from the suggestions.');
 if(typeof value.place_name!=='string'||!value.place_name.trim()||value.place_name.length>200)fail('Enter a place name, up to 200 characters.');
 if(typeof value.latitude!=='number'||!Number.isFinite(value.latitude)||Math.abs(value.latitude)>90||typeof value.longitude!=='number'||!Number.isFinite(value.longitude)||Math.abs(value.longitude)>180)fail('Enter valid latitude and longitude.');
 if(typeof value.source_url!=='string'||value.source_url.length>2048)fail('Enter an evidence URL up to 2,048 characters.');
 let url;try{url=new URL(value.source_url);}catch{fail('Enter the source video or evidence URL.');}
 if(!['http:','https:'].includes(url.protocol)||url.username||url.password)fail('Use an HTTP(S) evidence URL without embedded login details.');
 if(typeof value.evidence!=='string'||value.evidence.trim().length<20||value.evidence.length>2000)fail('Explain the song-specific location evidence in 20–2,000 characters.');
 if(!Object.hasOwn(precisionLabels,value.location_precision))fail('Choose the coordinate precision.');
 const timestamp=String(value.scene_timestamp||'');if(timestamp&&!/^(?:\d{1,2}:[0-5]\d:[0-5]\d|\d{1,2}:[0-5]\d)$/.test(timestamp))fail('Use a scene timestamp such as 01:23 or 00:01:23.');
 return {...value,place_name:value.place_name.trim(),source_url:url.href,evidence:value.evidence.trim(),scene_timestamp:timestamp,status:'proposed'};
}
const api={createIndex,validateProposal,precisionLabels};if(typeof module==='object'&&module.exports)module.exports=api;else root.SongGeo=api;
})(typeof globalThis!=='undefined'?globalThis:this);
