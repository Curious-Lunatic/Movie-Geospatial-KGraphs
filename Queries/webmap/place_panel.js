function initPlacePanel(searchMovies,{describe,openFilm}){
 const $=id=>document.getElementById(id), panel=$('placePanel'),out=$('placeItems');
 let selected,context,tab,request,opener;
 function add(parent,tag,text){const e=document.createElement(tag);e.textContent=text;parent.append(e);return e;}
 function button(parent,text,fn){const b=add(parent,'button',text);b.type='button';b.onclick=fn;}
 function link(parent,text,url){if(!/^https?:\/\//i.test(url||''))return;const a=add(parent,'a',text);a.href=url;a.target='_blank';a.rel='noopener';return a;}
 function close(){request?.abort();panel.hidden=true;opener?.focus();}
 $('placeClose').onclick=close;
 panel.onkeydown=e=>{if(e.key==='Escape')close();};
 async function show(next){
  tab=next;request?.abort();const ac=request=new AbortController(),p=selected,r=+$('discoveryRadius').value;
  for(const b of panel.querySelectorAll('[data-place-tab]'))b.setAttribute('aria-pressed',String(b.dataset.placeTab===tab));
  $('discoveryLimits').hidden=tab==='profile';$('categoryLabel').hidden=tab!=='nearby';
  out.replaceChildren();
  function movies(place){searchMovies(place,r);$('spatialSummary').scrollIntoView({block:'center'});}
  if(tab==='movies'){
   const films=context?.films||[];
   $('discoveryStatus').textContent=films.length+' movies with recorded connections to this place'+(context?.heritage?' or its documented components.':'.');
   if(!films.length)add(out,'p','No direct movie connection recorded for this selected point. Try a nearby search.');
   for(const film of films){
    const card=add(out,'article','');button(card,film.name+' ('+film.year+')',()=>{openFilm(film.node);$('explore').scrollIntoView({block:'start'});});
    for(const c of film.connections){
     add(card,'p',(c.relation==='filming'?'Filmed at ':'Story set at ')+c.place);
     if(c.evidence)add(card,'p',c.evidence);
     if(c.sourceUrls.length)for(const url of c.sourceUrls)link(card,'Filming / story source ↗',url);else add(card,'small','Dataset record: '+c.sourceRecord);
    }
   }
   add(out,'p','Explore other recorded locations within '+r+' km. Proximity is not evidence of filming at this site.');
   button(out,'Find movies around here',()=>movies(p));return;
  }
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
 return p=>{
  opener=document.activeElement;selected=p;context=describe(p.node);panel.hidden=false;
  $('discoveryName').textContent=p.name;$('discoveryPoint').textContent=p.lat.toFixed(4)+', '+p.lon.toFixed(4);
  const overview=$('placeOverview');overview.replaceChildren();
  if(context?.heritage)add(overview,'span','Heritage collection').className='place-badge';
  if(context?.description)add(overview,'p',context.description);
  else add(overview,'p',context?.heritage?'A heritage place in our sourced collection. Follow the identity source for its history.':'Explore this place’s recorded movie connections and surroundings.');
  const sources=add(overview,'div','');sources.className='place-source-links';
  link(sources,'History & identity ↗',context?.source_url||context?.heritageSource);
  link(sources,'Coordinate source ↗',p.coordinateSource);
  link(sources,'Google Maps ↗','https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(p.lat+','+p.lon));
  add(overview,'small','Map points represent a site or locality, not an exact camera position.');
  $('discoveryName').focus();panel.scrollIntoView({block:'nearest'});show('movies');
 };
}
