/* Accessible, session-only transcript. Render source strings as text, never HTML. */
'use strict';
function initCinemaChat({data,engine,getRegions,syncSpatial,syncCatalog,syncSongs,openFilm,openPlace}){
 const $=id=>document.getElementById(id),log=$('cinemaChatLog');
 if(!log)return;
 const assistant=CinemaChat.createAssistant(data,{engine,getRegions});
 let previous=null,busy=false,generation=0,history=[];
 const initial=log.firstElementChild.cloneNode(true);
 const el=(tag,text,parent)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;parent?.append(e);return e;};
 const labels={filming:'filmed at',narrative:'story set in',genre:'has genre',cast_member:'cast member',director:'directed by',in_film:'song in film',character_in_film:'character in film'};
 function message(who,text){const a=el('article',null,log);a.className='chat-message '+who;el('span',who==='user'?'You':'Cinema atlas',a).className='chat-speaker';if(text)el('p',text,a);return a;}
 function source(parent,index){
  const edge=data.edges[index];if(!edge)return;
  const details=el('details',null,parent);el('summary','Evidence · '+(edge[3]||1)+' source assertion(s)',details);
  el('p',edge[4]||'Source reference not recorded.',details);if(edge[6])el('p',edge[6],details);
  for(const url of [...new Set([edge[5],...(edge[7]||[])])].filter(url=>/^https?:\/\//i.test(url||''))){const a=el('a','Open recorded source ↗',details);a.href=url;a.target='_blank';a.rel='noopener';}
  el('small','Showing the first supporting record. claims.csv retains the source assertions.',details);
 }
 function render(answer){
  const article=message('assistant',answer.summary);
  if(answer.interpretation)el('p',answer.interpretation,article).className='chat-interpretation';
  if(answer.note)el('p',answer.note,article).className='chat-note';
  if(answer.kind==='movie'){
   if(answer.plan.category==='overview')el('p','Connected entities: '+Object.entries(answer.counts).map(([kind,count])=>kind+' '+count).join(' · '),article).className='chat-interpretation';
   const go=el('button','Open '+answer.film.name+' in the graph ↗',article);go.type='button';go.onclick=()=>openFilm(answer.film.node);
   const items=el('ul',null,article);let shown=0;
   const more=el('button','Show more connections',article);more.type='button';
   const append=()=>{for(const item of answer.items.slice(shown,shown+8)){
     const li=el('li',item.name+' · '+item.type+' · '+(labels[item.relation]||item.relation)+(item.role?' · portrayed by '+item.role:''),items);source(li,item.edgeIndex);
    }shown+=8;more.hidden=shown>=answer.items.length;};
   more.onclick=append;append();
  }else if(answer.kind==='song_locations'){
   for(const item of answer.items){const box=el('div',null,article);box.className='song-location-card';el('strong',data.nodes[item.song][1]+' · '+data.nodes[item.film][1],box);const p=engine.byNode.get(item.place),b=el('button',item.placeName,box);b.type='button';b.disabled=!p;b.onclick=()=>openPlace(p);el('p',SongGeo.precisionLabels[item.precision]||item.precision,box);el('p',item.evidence,box);if(item.timestamp)el('p','Scene timestamp: '+item.timestamp,box);const a=el('a','Song-location evidence ↗',box);a.href=item.source;a.target='_blank';a.rel='noopener';}
   if(answer.items.length){const b=el('button','Download song locations · GeoJSON',article);b.type='button';b.onclick=()=>{const features=answer.items.filter(l=>engine.byNode.has(l.place)).map(l=>{const p=engine.byNode.get(l.place);return {type:'Feature',geometry:{type:'Point',coordinates:[p.lon,p.lat]},properties:{role:'song_location_reference',song_id:data.nodes[l.song][0],song:data.nodes[l.song][1],film:data.nodes[l.film][1],place_id:data.nodes[l.place][0],place:p.name,location_precision:l.precision,source_url:l.source,evidence:l.evidence,status:l.status}};});const url=URL.createObjectURL(new Blob([JSON.stringify({type:'FeatureCollection',features})],{type:'application/geo+json'})),a=el('a');a.href=url;a.download='song-location-references.geojson';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};}
   const a=el('a','Propose another song geotag for review ↓',article);a.href='#songTagPanel';
  }else if(answer.kind==='catalog'){
   const list=el('ul',null,article);let shown=0;const more=el('button','Show more heritage sites',article);more.type='button';
   const append=()=>{for(const p of answer.items.slice(shown,shown+8)){const li=el('li',null,list),b=el('button',p.name,li);b.type='button';b.onclick=()=>openPlace(p);el('p',SpatialSearch.placeLabel(p)+' · '+(p.locality||p.country)+' · '+p.distanceKm.toFixed(2)+' km',li);el('small',p.directFilmCount+' direct recorded film connections',li);if(/^https?:/.test(p.identitySource)){const a=el('a','Site identity source ↗',li);a.href=p.identitySource;a.target='_blank';a.rel='noopener';}}shown+=8;more.hidden=shown>=answer.items.length;};more.onclick=append;append();
   const exportButton=el('button','Download heritage references · GeoJSON',article);exportButton.type='button';exportButton.onclick=()=>{const payload={type:'FeatureCollection',features:answer.items.map(p=>({type:'Feature',geometry:{type:'Point',coordinates:[p.lon,p.lat]},properties:{role:'heritage_reference',place_id:data.nodes[p.node][0],name:p.name,place_type:p.kind,location_precision:p.precision,identity_source:p.identitySource,distance_km:p.distanceKm,direct_film_count:p.directFilmCount}}))};const url=URL.createObjectURL(new Blob([JSON.stringify(payload)],{type:'application/geo+json'})),a=el('a');a.href=url;a.download='heritage-reference-sites.geojson';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  }else if(answer.kind==='place_info'){
   const b=el('button','Open '+answer.place.name+' in Place Panel ↗',article);b.type='button';b.onclick=()=>openPlace(answer.place);
   if(answer.mapsUrl){const gm=el('a','Open in Google Maps ↗',article);gm.href=answer.mapsUrl;gm.target='_blank';gm.rel='noopener';}
  }else if(['route','isochrone','polygon'].includes(answer.kind)){
   const a=el('a','View map analysis and results ↓',article);a.href='#spatial';
  }else if(answer.kind==='spatial'){
   const list=el('ul',null,article);
   let shown=0;const more=el('button','Show more films',article);more.type='button';const append=()=>{for(const row of answer.results.slice(shown,shown+6)){
    const film=data.nodes[row.film],li=el('li',null,list),go=el('button',film[1]+' · '+film[3],li);go.type='button';go.onclick=()=>openFilm(row.film);
    const match=row.matches[0];el('span',' · '+match.place.name+(match.distanceKm==null?'':' · '+match.distanceKm.toFixed(3)+' km'),li);el('small',SpatialSearch.placeLabel(match.place)+' · '+SpatialSearch.precisionNote(match.place),li);source(li,match.edgeIndex);
   }shown+=6;more.hidden=shown>=answer.results.length;};more.onclick=append;append();
   const a=el('a',answer.results.length?'View all results, map and exports ↓':'Inspect the search area on the map ↓',article);a.href='#spatial';
  }
  log.scrollTo({top:log.scrollHeight,behavior:'auto'});
 }
 async function submit(text,selection={}){
  if(busy||!text.trim())return;busy=true;const token=generation;
  message('user',text);$('cinemaChatInput').value='';$('sendCinemaChat').disabled=true;$('cinemaChatStatus').textContent='Thinking with Gemini 3.5 Flash Lite…';
  try{
   const answer=await assistant.answer(text,previous,selection,history);if(token!==generation)return;
   if(['spatial','route','isochrone','polygon'].includes(answer.kind)){await syncSpatial(answer);if(token!==generation)return;}
   if(answer.kind==='catalog'){await syncCatalog(answer);if(token!==generation)return;}
   if(answer.kind==='song_locations'){await syncSongs(answer);if(token!==generation)return;}
   if(answer.kind==='place_info'){openPlace(answer.place);}
   render(answer);
   history.push({role:'user',text},{role:'model',text:answer.summary});
   if(history.length>24)history=history.slice(-24);
   if(answer.plan)previous=answer.plan;
  }catch(error){if(token===generation){const a=message('assistant',error.message);a.classList.add('chat-error');for(const p of error.choices||[]){const b=el('button',p.name+' · '+SpatialSearch.placeLabel(p)+' · '+(p.locality||p.country)+' · '+p.lat.toFixed(3)+', '+p.lon.toFixed(3),a);b.type='button';b.onclick=()=>submit(text,{...selection,placeNode:p.node});}log.scrollTo({top:log.scrollHeight,behavior:'auto'});}}
  finally{if(token===generation){busy=false;$('sendCinemaChat').disabled=false;$('cinemaChatStatus').textContent='';$('cinemaChatInput').focus({preventScroll:true});}}
 }
 $('cinemaChatForm').onsubmit=e=>{e.preventDefault();submit($('cinemaChatInput').value);};
 for(const b of document.querySelectorAll('[data-chat-prompt]'))b.onclick=()=>submit(b.dataset.chatPrompt);
 $('clearCinemaChat').onclick=()=>{generation++;previous=null;history=[];busy=false;log.replaceChildren(initial.cloneNode(true));$('sendCinemaChat').disabled=false;$('cinemaChatInput').value='';$('cinemaChatStatus').textContent='';$('cinemaChatInput').focus({preventScroll:true});};
}
