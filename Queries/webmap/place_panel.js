function initPlacePanel(searchMovies){
 const $=id=>document.getElementById(id), panel=$('placePanel'),out=$('placeItems');
 let selected,tab,request,opener;
 function add(parent,tag,text){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e;}
 function button(parent,text,fn){const b=add(parent,'button',text);b.type='button';b.onclick=fn;}
 function close(){request?.abort();panel.hidden=true;opener?.focus();}
 $('placeClose').onclick=close;
 panel.onkeydown=e=>{if(e.key==='Escape')close();};
 async function show(next){
  tab=next;request?.abort();const ac=request=new AbortController(),p=selected,r=+$('discoveryRadius').value;
  for(const b of panel.querySelectorAll('[data-place-tab]'))b.setAttribute('aria-pressed',String(b.dataset.placeTab===tab));
  $('discoveryLimits').hidden=tab==='profile';$('categoryLabel').hidden=tab!=='nearby';
  out.replaceChildren();
  function movies(place){searchMovies(place,r);$('spatialSummary').scrollIntoView({block:'center'});}
  if(tab==='movies'){add(out,'p','Search the movie graph within '+r+' km of '+p.name+' using your current movie filters.');button(out,'Find movies around here',()=>movies(p));return;}
  $('discoveryStatus').textContent='Looking up places…';
  try{
   const q=new URLSearchParams({action:tab,lat:p.lat.toFixed(5),lng:p.lon.toFixed(5),radius:r,category:$('discoveryCategory').value});
   const response=await fetch('/api/places?'+q,{signal:ac.signal});
   if(!response.headers.get('content-type')?.includes('json'))throw Error('Place details are available on the hosted atlas.');
   const data=await response.json();if(!response.ok)throw Error(data.error||'Lookup unavailable.');
   if(ac.signal.aborted)return;
   $('discoveryStatus').textContent=(data.source||'GeoNames')+' · '+(tab==='profile'?'Nearest listed settlement; details describe this settlement.':data.items.length+' nearby results');
   if(!data.items.length)add(out,'p','No listed places found. Try a wider radius or another category.');
   for(const x of data.items){
    const card=add(out,'article','');const a=add(card,'a',x.name+' ↗');a.href=x.url;a.target='_blank';a.rel='noopener';
    if(x.thumbnail){const img=document.createElement('img');img.alt='';img.src=x.thumbnail;img.loading='lazy';card.append(img);}
    add(card,'p',[x.kind,x.region,x.distanceKm!=null?x.distanceKm.toFixed(1)+' km away':null].filter(Boolean).join(' · '));
    if(x.summary)add(card,'p',x.summary);
    if(tab==='profile'){const facts=[x.population?'Population: '+x.population.toLocaleString():null,x.timezone,x.elevation!=null?'Elevation: '+x.elevation+' m':null,...(x.aliases||[])].filter(Boolean);if(facts.length)add(card,'p',facts.join(' · '));}
    button(card,'Find movies near '+x.name,()=>movies({name:x.name,lat:x.lat,lon:x.lng}));
   }
  }catch(e){if(!ac.signal.aborted)$('discoveryStatus').textContent=e.message;}
 }
 for(const b of panel.querySelectorAll('[data-place-tab]'))b.onclick=()=>{$('discoveryStatus').textContent='';show(b.dataset.placeTab);};
 $('discoveryRadius').onchange=$('discoveryCategory').onchange=()=>show(tab);
 return p=>{opener=document.activeElement;selected=p;panel.hidden=false;$('discoveryName').textContent=p.name;$('discoveryPoint').textContent=p.lat.toFixed(4)+', '+p.lon.toFixed(4);$('discoveryName').focus();panel.scrollIntoView({block:'nearest'});show('profile');};
}
