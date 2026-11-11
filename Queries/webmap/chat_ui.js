/* Accessible, session-only transcript. Render source strings as text, never HTML. */
'use strict';
function initCinemaChat({data,engine,getRegions,syncSpatial,openFilm}){
 const $=id=>document.getElementById(id),log=$('cinemaChatLog');
 if(!log)return;
 const assistant=CinemaChat.createAssistant(data,{engine,getRegions});
 let previous=null,busy=false,generation=0;
 const initial=log.firstElementChild.cloneNode(true);
 const el=(tag,text,parent)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;parent?.append(e);return e;};
 const labels={filming:'filmed at',narrative:'story set in',genre:'has genre',cast_member:'cast member',director:'directed by',in_film:'song in film',character_in_film:'character in film'};
 function message(who,text){const a=el('article',null,log);a.className='chat-message '+who;el('span',who==='user'?'You':'Cinema atlas',a).className='chat-speaker';if(text)el('p',text,a);return a;}
 function source(parent,index){
  const edge=data.edges[index];if(!edge)return;
  const details=el('details',null,parent);el('summary','Evidence · '+(edge[3]||1)+' source assertion(s)',details);
  el('p',edge[4]||'Source reference not recorded.',details);if(edge[6])el('p',edge[6],details);
  if(/^https?:\/\//i.test(edge[5]||'')){const a=el('a','Open recorded source ↗',details);a.href=edge[5];a.target='_blank';a.rel='noopener';}
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
  }else if(answer.kind==='spatial'){
   const list=el('ul',null,article);
   for(const row of answer.results.slice(0,6)){
    const film=data.nodes[row.film],li=el('li',null,list),go=el('button',film[1]+' · '+film[3],li);go.type='button';go.onclick=()=>openFilm(row.film);
    const match=row.matches[0];el('span',' · '+match.place.name+(match.distanceKm==null?'':' · '+match.distanceKm.toFixed(3)+' km'),li);source(li,match.edgeIndex);
   }
   const a=el('a',answer.results.length?'View all results, map and exports ↓':'Inspect the search area on the map ↓',article);a.href='#spatial';
  }
  article.scrollIntoView({behavior:'smooth',block:'nearest'});
 }
 async function submit(text){
  if(busy||!text.trim())return;busy=true;const token=generation;
  message('user',text);$('cinemaChatInput').value='';$('sendCinemaChat').disabled=true;$('cinemaChatStatus').textContent='Checking the recorded data…';
  try{
   const answer=await assistant.answer(text,previous);if(token!==generation)return;
   if(answer.kind==='spatial'){await syncSpatial(answer);if(token!==generation)return;}
   render(answer);if(answer.kind!=='help')previous=answer.plan;
  }catch(error){if(token===generation){const a=message('assistant',error.message);a.classList.add('chat-error');a.scrollIntoView({block:'nearest'});}}
  finally{if(token===generation){busy=false;$('sendCinemaChat').disabled=false;$('cinemaChatStatus').textContent='';$('cinemaChatInput').focus({preventScroll:true});}}
 }
 $('cinemaChatForm').onsubmit=e=>{e.preventDefault();submit($('cinemaChatInput').value);};
 for(const b of document.querySelectorAll('[data-chat-prompt]'))b.onclick=()=>submit(b.dataset.chatPrompt);
 $('clearCinemaChat').onclick=()=>{generation++;previous=null;busy=false;log.replaceChildren(initial.cloneNode(true));$('sendCinemaChat').disabled=false;$('cinemaChatInput').value='';$('cinemaChatStatus').textContent='';$('cinemaChatInput').focus({preventScroll:true});};
}
