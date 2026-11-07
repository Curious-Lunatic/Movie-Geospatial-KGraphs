/* Six spatial tools, one movie-selection engine and one map. */
'use strict';
function initSpatialExplorer({data,openFilm}){
 const $=id=>document.getElementById(id),engine=SpatialSearch.createEngine(data),S=SpatialTools;
 const nodes=data.nodes,edges=data.edges,years=data.summary.year_range,router=S.createRouter();
 const descriptions={
  nearby:['Point + buffer','Nearby movies','Find movies around a place or a point on the map.','Nearby exploration'],
  heritage:['Heritage + proximity','Near a heritage site','Choose a heritage site, then explore recorded filming and story locations nearby.','Heritage proximity'],
  region:['Overlay + spatial join','States & districts','Explore a state, then compare its districts by distinct movies and recorded locations.','States & districts'],
  polygon:['Draw + spatial selection','Draw a search area','Draw an area on the map to discover the movies connected to places inside it.','Custom area'],
  route:['Road route + corridor','Along your route','Choose your start and destination. Find movie locations near the road between them.','Route corridor'],
  time:['Road network + reachable area','Within travel time','Choose a starting point and travel time to explore a modelled reachable area.','Travel-time exploration']
 };
 let mode='nearby',center=null,centerName='',end=null,endName='',target='start';
 let map,markers,analysisLayer,contextLayer,drawingLayer,pointLayer,drawPoints=[],drawn=null,drawing=false;
 let results=[],shown=0,last=null,revision=0,controller=null,regions=null,regionPromise=null;
 let analysisFeatures=[];
 const el=(tag,text,parent)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(parent)parent.append(e);return e;};
 const link=(parent,text,url)=>{const a=el('a',text,parent);a.href=url;a.target='_blank';a.rel='noopener';return a;};
 const mapsUrl=p=>'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(p.lat+','+p.lon);
 const scope=p=>p.heritage?'Heritage reference point':'City / region reference point';
 const point=p=>[p.lat,p.lon];
 const explore=initPlacePanel((p,r)=>{switchTool('nearby');choose(point(p),p.name);$('radiusKm').value=r;run(true);},{describe:createPlaceContext(data),openFilm});
 const discover=(parent,p)=>{const b=el('button','Explore this place',parent);b.type='button';b.onclick=()=>explore(p);};
 $('discoverCenter').onclick=()=>{if(center)explore(engine.places.find(p=>p.name===centerName&&p.lat===center[0]&&p.lon===center[1])||{name:centerName,lat:center[0],lon:center[1]});};
 function error(message){$('spatialError').hidden=!message;$('spatialError').textContent=message||'';}
 function controls(){return {center,radiusKm:Number($('radiusKm').value),relation:$('spatialRelation').value,genre:$('spatialGenre').value,yearFrom:Number($('yearFrom').value),yearTo:Number($('yearTo').value),heritageOnly:$('heritageOnly').checked};}
 function apply(o){for(const [id,key] of [['radiusKm','radiusKm'],['spatialRelation','relation'],['spatialGenre','genre'],['yearFrom','yearFrom'],['yearTo','yearTo']])$(id).value=o[key];$('heritageOnly').checked=!!o.heritageOnly;}
 function empty(title,text){$('spatialResults').replaceChildren();const box=el('div',null,$('spatialResults'));box.className='atlas-empty';el('span','◎',box).ariaHidden='true';el('h4',title,box);el('p',text,box);}
 function invalidate(message='Ready when you are.'){
  revision++;controller?.abort();controller=null;$('runSpatial').disabled=false;$('cancelSpatial').hidden=true;
  results=[];shown=0;last=null;analysisFeatures=[];analysisLayer?.clearLayers();$('downloadSpatial').disabled=true;$('downloadAnalysis').disabled=true;$('moreSpatial').hidden=true;$('districtRanking').hidden=true;
  $('spatialSummary').textContent=message;$('interpretedQuery').textContent='Choose your area and select Find movies.';error('');empty('Your next discovery','Run a search to see movies connected to this area.');
 }
 function initializeMap(){
  if(map)return;
  map=L.map('cinemaMap',{preferCanvas:true,scrollWheelZoom:false}).setView([22.5,79],5);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on('tileerror',()=>{$('mapStatus').textContent='Background tiles unavailable. Stored locations and spatial searches still work.';}).addTo(map);
  contextLayer=L.featureGroup().addTo(map);analysisLayer=L.featureGroup().addTo(map);drawingLayer=L.featureGroup().addTo(map);markers=L.layerGroup().addTo(map);pointLayer=L.layerGroup().addTo(map);
  map.on('click',e=>{
   const p=[e.latlng.lat,((e.latlng.lng+180)%360+360)%360-180];
   if(mode==='polygon'){if(drawing)addDrawPoint(p);return;}
   if(mode==='heritage'){$('mapStatus').textContent='Choose a heritage site using the place search.';return;}
   if(mode==='region')return;
   choose(p,'Selected map point');if(mode==='nearby')run(false);
  });
  map.getContainer().addEventListener('keydown',e=>{if(e.key==='Escape'&&drawing){drawing=false;map.getContainer().classList.remove('drawing-map');$('drawStatus').textContent='Drawing paused. Finish your area or start again.';}});
  drawMarkers(engine.visiblePlaces(controls()));$('mapStatus').textContent='Choose a place or click the map to begin.';
 }
 function drawMarkers(places){
  markers.clearLayers();for(const p of places){
   const story=$('spatialRelation').value==='narrative';
   const marker=L.circleMarker(point(p),{radius:5,color:story?'#80678f':'#28564d',fillColor:story?'#b99dca':'#649b8e',fillOpacity:.9,weight:1.5,bubblingMouseEvents:false}).addTo(markers);
   const popup=el('div');el('strong',p.name,popup);el('p',scope(p),popup);if(p.filmCount!=null)el('p',p.filmCount+' connected movies',popup);
   const use=el('button',mode==='route'?(target==='end'?'Use as destination':'Use as start'):'Explore nearby',popup);use.type='button';use.onclick=()=>{map.closePopup();if(mode!=='route'&&mode!=='time')switchTool('nearby');choose(point(p),p.name);if(mode==='nearby')run(true);};
   discover(popup,p);link(popup,'Google Maps ↗',mapsUrl(p));marker.bindPopup(popup);
  }
 }
 function renderPoints(){
  if(!map)return;pointLayer.clearLayers();
  for(const [p,name,color] of [[center,centerName,'#b98740'],[mode==='route'?end:null,endName,'#2a7787']])if(p)L.circleMarker(p,{radius:7,color,fillColor:color,fillOpacity:1,weight:3,interactive:false}).bindTooltip(name).addTo(pointLayer);
 }
 function choose(p,name,heritage=false){
  if(mode==='heritage'&&!heritage){error('Choose a heritage site from the search results.');return;}
  invalidate();if(mode==='route'&&target==='end'){end=p;endName=name;}else{center=p;centerName=name;}
  $('placeSearch').value=name;updatePointLabels();$('placeChoices').replaceChildren();renderPoints();
 }
 function updatePointLabels(){
  $('discoverCenter').hidden=!center; $('centerLabel').textContent=center?(mode==='route'?'Start: ':'')+centerName+' · '+center.map(v=>v.toFixed(4)).join(', '):'Choose a place or click the map.';
  $('endLabel').textContent=end?'To: '+endName+' · '+end.map(v=>v.toFixed(4)).join(', '):'Destination not selected.';
 }
 function resolvePlace(text,after){
  error('');let matches=engine.findPlaces(text);if(mode==='heritage')matches=matches.filter(p=>p.heritage);
  $('placeChoices').replaceChildren();
  const accept=p=>{choose(point(p),p.name,p.heritage);after?.();};
  if(!matches.length){error(mode==='heritage'?'No matching heritage site. Try Taj Mahal, Agra Fort or Amber Fort.':'No matching place in the stored data. Try another name or select a map point.');return;}
  if(matches.length===1){accept(matches[0]);return;}
  el('p','Choose a place ('+matches.length+' matches):',$('placeChoices')).className='control-note';
  for(const p of matches.slice(0,30)){const b=el('button',p.name+' · '+(p.country||'')+' · '+p.lat.toFixed(3)+', '+p.lon.toFixed(3),$('placeChoices'));b.type='button';b.onclick=()=>accept(p);}
  if(matches.length>30)el('p','Refine the name to narrow these matches.',$('placeChoices')).className='control-note';
 }
 async function loadRegions(){
  if(regions)return regions;if(regionPromise)return regionPromise;
  regionPromise=(async()=>{
   const responses=await Promise.all(['india_regions.geojson','region_membership.json'].map(url=>fetch(url)));if(responses.some(r=>!r.ok))throw Error('Region boundaries could not be loaded. Check your connection and try Regions again.');
   const [collection,membership]=await Promise.all(responses.map(r=>r.json()));
   regions={features:collection.features,membership,byId:new Map(collection.features.map(f=>[f.properties.id,f]))};
   const stateNames=new Set(collection.features.filter(f=>f.properties.level==='ADM1').map(f=>SpatialSearch.normalize(f.properties.name)));
   regions.countryReferences=engine.places.filter(p=>SpatialSearch.normalize(p.name)==='india').map(p=>nodes[p.node][0]);
   regions.broadReferences=engine.places.filter(p=>stateNames.has(SpatialSearch.normalize(p.name))||SpatialSearch.normalize(p.name)==='india').map(p=>nodes[p.node][0]);
   const state=$('stateRegion');state.replaceChildren();option(state,'','Choose a state…');for(const f of regions.features.filter(f=>f.properties.level==='ADM1').sort((a,b)=>a.properties.name.localeCompare(b.properties.name)))option(state,f.properties.id,f.properties.name);
   return regions;
  })().catch(err=>{regionPromise=null;throw err;});return regionPromise;
 }
 function option(select,value,text){const o=el('option',text,select);o.value=value;}
 function populateDistricts(){
  $('districtRegion').replaceChildren();option($('districtRegion'),'','All districts');
  for(const f of districts())option($('districtRegion'),f.properties.id,f.properties.name);
 }
 function districts(){return regions?regions.features.filter(f=>f.properties.level==='ADM2'&&f.properties.state_id===$('stateRegion').value).sort((a,b)=>a.properties.name.localeCompare(b.properties.name)):[];}
 function regionContext(fit=false){
  if(!map||!regions||mode!=='region')return;contextLayer.clearLayers();
  const state=regions.byId.get($('stateRegion').value);
  const features=state?[state,...districts()]:regions.features.filter(f=>f.properties.level==='ADM1');
  L.geoJSON(features,{style:f=>({color:f.properties.level==='ADM1'?'#52796f':'#889b95',weight:f.properties.level==='ADM1'?2:1,fillOpacity:.04}),onEachFeature:(f,layer)=>{
   layer.bindTooltip(f.properties.name);layer.on('click',e=>{L.DomEvent.stopPropagation(e);invalidate();if(f.properties.level==='ADM1'){$('stateRegion').value=f.properties.id;populateDistricts();}else $('districtRegion').value=f.properties.id;regionContext();run(true);});
  }}).addTo(contextLayer);
  if(fit&&contextLayer.getLayers().length)map.fitBounds(contextLayer.getBounds(),{padding:[20,20]});
 }
 async function switchTool(next){
  $('tajExample').hidden=next!=='heritage';
  mode=next;invalidate();initializeMap();drawing=false;map.getContainer().classList.remove('drawing-map');drawingLayer.clearLayers();contextLayer.clearLayers();
  document.querySelectorAll('[data-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tool===mode)));
  const d=descriptions[mode];['toolOperation','toolTitle','toolDescription','activeMapTool'].forEach((id,i)=>$(id).textContent=d[i]);
  $('pointControls').hidden=['region','polygon'].includes(mode);$('regionControls').hidden=mode!=='region';$('drawControls').hidden=mode!=='polygon';$('routeTarget').hidden=mode!=='route';$('endLabel').hidden=mode!=='route';
  $('radiusControl').hidden=!['nearby','heritage','route'].includes(mode);$('radiusKm').disabled=$('radiusControl').hidden;
  $('radiusKm').max=mode==='route'?25:500;if(mode==='route'&&Number($('radiusKm').value)>25)$('radiusKm').value=3;
  $('radiusLabel').textContent=mode==='route'?'Distance from route · km':'Search radius · km';
  $('travelControls').hidden=!['route','time'].includes(mode);$('timeControl').hidden=mode!=='time';$('travelMinutes').disabled=mode!=='time';
  $('placeSearchLabel').textContent=mode==='heritage'?'Find a heritage site':'Find a place';$('placeSearch').placeholder=mode==='heritage'?'Taj Mahal, Agra Fort…':'Jaipur, Agra Fort…';$('placeChoices').replaceChildren();
  if(mode==='heritage'){center=null;centerName='';$('radiusKm').value=5;}
  target='start';$('pickStart').setAttribute('aria-pressed','true');$('pickEnd').setAttribute('aria-pressed','false');$('placeSearch').value=centerName;
  document.querySelector('.atlas-controls').scrollTop=0;updatePointLabels();renderPoints();drawMarkers(engine.visiblePlaces(controls()));
  $('mapStatus').textContent=mode==='polygon'?'Start drawing, then click around your area.':mode==='region'?'Choose a state or click a boundary.':mode==='heritage'?'Find a heritage site using the search.':mode==='route'?'Choose start and destination using search or the map.':'Choose a place or click the map.';
  if(mode==='polygon')renderDrawing();
  if(mode==='region'){try{await loadRegions();if(mode==='region')regionContext(true);}catch(e){if(mode==='region')error(e.message);}}
 }
 function renderDrawing(){
  drawingLayer.clearLayers();map.getContainer().classList.toggle('drawing-map',drawing);
  if(drawPoints.length>1)(drawn?L.polygon(drawPoints,{color:'#b98740',fillOpacity:.12,interactive:false}):L.polyline(drawPoints,{color:'#b98740',dashArray:'5 5',interactive:false})).addTo(drawingLayer);
  drawPoints.forEach(p=>L.circleMarker(p,{radius:4,color:'#b98740',fillOpacity:1,interactive:false}).addTo(drawingLayer));
  $('drawStatus').textContent=drawPoints.length+' point'+(drawPoints.length===1?'':'s')+(drawn?' · area ready':drawing?' · click the map to add more':'');
 }
 function addDrawPoint(p){if(!p.every(Number.isFinite)||Math.abs(p[0])>90||Math.abs(p[1])>180){error('Enter valid latitude and longitude.');return;}if(drawPoints.length>=100){error('Use at most 100 points.');return;}invalidate();drawn=null;drawPoints.push(p);renderDrawing();}
 function finishDrawing(){try{drawn=S.polygon(drawPoints);drawing=false;renderDrawing();error('');run(true);}catch(e){error(e.message);}}
 function fitSelection(){if(analysisLayer?.getLayers().length)map.fitBounds(analysisLayer.getBounds(),{padding:[28,28],maxZoom:14});else if(drawingLayer?.getLayers().length)map.fitBounds(drawingLayer.getBounds(),{padding:[28,28],maxZoom:14});else if(center)map.setView(center,11);}
 async function run(fit=true){
  invalidate('Searching your area…');initializeMap();const token=revision,o=controls(),searchMode=mode;
  // Validate shared movie filters before any external road request.
  try{engine.selected({...o,radiusKm:1},new Map());}catch(e){error(e.message);return;}
  let selected=[],features=[],label='',metric='',notes='',road=null;
  try{
   if(['nearby','heritage'].includes(searchMode)){
    selected=engine.search(o);features=[S.circle(center,o.radiusKm)];label=centerName+' · within '+o.radiusKm+' km';metric='distance from centre';
    notes=searchMode==='heritage'?'Near this heritage reference point; proximity does not prove filming at the site.':'Straight-line distance from the selected reference point.';
   }else if(searchMode==='polygon'){
    if(!drawn)throw Error('Draw and finish an area first.');selected=engine.searchArea(o,drawn);features=[drawn];label='Your drawn area';notes='Locations inside your polygon, including its boundary.';
   }else if(searchMode==='region'){
    const r=await loadRegions();if(token!==revision)return;
    const feature=r.byId.get($('districtRegion').value||$('stateRegion').value);if(!feature)throw Error('Choose a state or district first.');
    o.excludePlaces=feature.properties.level==='ADM2'?r.broadReferences:r.countryReferences;
    selected=engine.searchArea(o,feature);features=[feature];label=feature.properties.name+' · '+(feature.properties.level==='ADM1'?'state / union territory':'district');notes='Published boundary overlay. Known country references are excluded; district searches also exclude state references.';
   }else{
    if(!center)throw Error('Choose a starting point first.');if(searchMode==='route'&&!end)throw Error('Choose a destination first.');
    const costing=$('travelMode').value,minutes=Number($('travelMinutes').value),travelLabel=$('travelMode').selectedOptions[0].textContent;
    if(searchMode==='route'&&SpatialSearch.distanceKm(center,end)>1500)throw Error('Choose a route under 1,500 km between endpoints.');
    if(searchMode==='route'&&(!Number.isFinite(o.radiusKm)||o.radiusKm<.1||o.radiusKm>25))throw Error('Choose a route corridor between 0.1 and 25 km.');
    controller=new AbortController();$('runSpatial').disabled=true;$('cancelSpatial').hidden=false;$('mapStatus').textContent='Calculating on the road network…';
    if(searchMode==='route'){
     road=await router.route([...center],[...end],costing,controller.signal);if(token!==revision)return;
     const area=S.corridor(road.geometry,o.radiusKm);selected=engine.searchArea(o,area,p=>S.routeDistance(p,road.geometry));features=[area,{type:'Feature',geometry:road.geometry,properties:{role:'road_route'}}];
     label=centerName+' → '+endName+' · '+(road.distance/1000).toFixed(1)+' km route · '+Math.round(road.duration/60)+' min';metric='distance from route';notes=o.radiusKm+' km corridor on each side · '+travelLabel+'. Corridor distance is not a driving detour.';
    }else{
     const area=await router.reachable([...center],minutes,costing,controller.signal);if(token!==revision)return;
     selected=engine.searchArea(o,area.features);features=area.features;label=centerName+' · '+minutes+' minutes · '+travelLabel;notes='Estimated reachable area from the road network. No live traffic or per-location arrival-time guarantee.';
    }
   }
   if(token!==revision)return;
   results=selected;shown=0;analysisFeatures=features;last={mode:searchMode,label,metric,notes,options:{...o,center:center?[...center]:null},stateId:$('stateRegion').value,districtId:$('districtRegion').value,travelMode:$('travelMode').value,travelMinutes:Number($('travelMinutes').value)};
   analysisLayer.clearLayers();drawingLayer.clearLayers();
   features.forEach(f=>L.geoJSON(f,{style:{color:f.geometry.type==='LineString'?'#286e82':'#b98740',weight:f.geometry.type==='LineString'?3:2,fillColor:'#c7a16c',fillOpacity:.13},interactive:false}).addTo(analysisLayer));
   const places=new Map();for(const row of results)for(const m of row.matches){if(!places.has(m.place.node))places.set(m.place.node,{...m.place,films:new Set()});places.get(m.place.node).films.add(row.film);}
   drawMarkers([...places.values()].map(p=>({...p,filmCount:p.films.size})));renderPoints();if(fit)fitSelection();
   $('spatialSummary').textContent=results.length+' movie'+(results.length===1?'':'s')+' · '+places.size+' location'+(places.size===1?'':'s');
   const relation={filming:'Filming locations',narrative:'Story settings',both:'Filming + story settings'}[o.relation];
   $('interpretedQuery').textContent=label+' · '+relation+' · '+(o.genre||'All genres')+' · '+o.yearFrom+'–'+o.yearTo+(o.heritageOnly?' · Heritage locations only':'')+'. '+notes;
   $('mapStatus').textContent=searchMode==='route'||searchMode==='time'?'Road analysis: Valhalla / FOSSGIS · © OpenStreetMap contributors':'Selection complete · '+places.size+' matching locations';
   $('downloadSpatial').disabled=!results.length;$('downloadAnalysis').disabled=false;$('spatialResults').replaceChildren();
   if(!results.length)empty('No recorded matches here.','Try a wider area or different movie filters. Locations without coordinates cannot appear.');more();
   if(searchMode==='region')renderRanking(o);
  }catch(e){if(token!==revision)return;error(e.message);$('spatialSummary').textContent='Search could not be completed.';$('mapStatus').textContent='Adjust your selection and try again.';}
  finally{if(token===revision){$('runSpatial').disabled=false;$('cancelSpatial').hidden=true;controller=null;}}
 }
 function renderRanking(o){
  const container=$('districtRanking');container.replaceChildren();const list=districts();if(!list.length)return;
  el('h4','Districts in this state · known state/country references excluded',container);const buttons=el('div',null,container);
  const districtFilters={...o,excludePlaces:regions.broadReferences};
  const places=engine.visiblePlaces(districtFilters),ranked=list.map(f=>{const selection=new Map(places.filter(p=>regions.membership[nodes[p.node][0]]?.includes(f.properties.id)).map(p=>[p.node,null]));return {feature:f,count:engine.selected(districtFilters,selection).length,places:selection.size};}).sort((a,b)=>b.count-a.count||a.feature.properties.name.localeCompare(b.feature.properties.name));
  const displayed=ranked.filter(row=>row.count>0).slice(0,10);
  if(!displayed.length)el('p','No districts have recorded matches for these filters.',container).className='control-note';
  else el('p','Top matching districts. Use the district selector to explore any of the '+list.length+' districts.',container).className='control-note';
  for(const row of displayed){const b=el('button',row.feature.properties.name,buttons);b.type='button';el('strong',row.count+' film'+(row.count===1?'':'s')+' · '+row.places+' place'+(row.places===1?'':'s'),b);b.onclick=()=>{$('districtRegion').value=row.feature.properties.id;run(true);};}
  container.hidden=false;
 }
 function more(){
  const next=results.slice(shown,shown+18);
  for(const row of next){const n=nodes[row.film],card=el('article',null,$('spatialResults'));card.className='spatial-card';const head=el('div',null,card);head.className='spatial-card-head';
   if(n[5]){const img=el('img',null,head);img.src=n[5];img.alt='Poster for '+n[1];img.loading='lazy';img.width=64;img.height=96;img.onerror=()=>img.remove();}
   const body=el('div',null,head);el('h4',n[1],body);el('p',n[3]+(row.distanceKm==null?' · Inside selected area':' · '+row.distanceKm.toFixed(2)+' km '+last.metric),body);
   const go=el('button','Open movie graph ↗',body);go.type='button';go.onclick=()=>openFilm(row.film);const list=el('ul',null,card);
   for(const m of row.matches.slice(0,4)){const p=m.place,li=el('li',p.name+(m.distanceKm==null?'':' · '+m.distanceKm.toFixed(2)+' km'),list);el('small',(m.relation==='filming'?'Filmed at':'Story set in')+' · '+scope(p),li);const actions=el('div',null,li);actions.className='result-actions';discover(actions,p);link(actions,'Google Maps ↗',mapsUrl(p));const edge=edges[m.edgeIndex];if(/^https?:\/\//.test(edge[5]))link(actions,'Source ↗',edge[5]);else el('small','Source: '+edge[4],actions);}
   if(last.mode==='heritage'){
    const credits=el('details',null,card);
    const cast=Array.from(castByFilm.get(row.film)||[]).sort();
    el('summary','Credited cast ('+cast.length+')',credits);
    el('p',cast.join(', ')||'No cast credits recorded.',credits);
   }
   if(row.matches.length>4)el('p','+'+(row.matches.length-4)+' connections included in the export.',card);
  }
  shown+=next.length;$('moreSpatial').hidden=shown>=results.length;
 }
 function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=el('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 $('downloadSpatial').onclick=()=>{
  if(!last)return;const cell=v=>{let s=String(v??'');if(/^[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
  const rows=[['movie_id','movie','year','place_id','place','relationship','latitude','longitude','distance_km','distance_type','coordinate_scope','source_url','source_reference','analysis','search','filters']];
  for(const row of results)for(const m of row.matches){const n=nodes[row.film],p=m.place,e=edges[m.edgeIndex];rows.push([n[0],n[1],n[3],nodes[p.node][0],p.name,m.relation,p.lat,p.lon,m.distanceKm==null?'':m.distanceKm.toFixed(4),last.metric,p.scope,e[5],e[4],last.mode,last.label,JSON.stringify(last.options)]);}
  download('cinema-'+last.mode+'-results.csv','\uFEFF'+rows.map(row=>row.map(cell).join(',')).join('\r\n'),'text/csv;charset=utf-8');
 };
 $('downloadAnalysis').onclick=()=>{
  if(!last)return;const features=analysisFeatures.map(f=>({...f,properties:{...f.properties,role:f.properties?.role||'search_area',analysis:last.mode,search:last.label,filters:JSON.stringify(last.options),method:last.notes}}));
  for(const row of results)for(const m of row.matches){const p=m.place,n=nodes[row.film],e=edges[m.edgeIndex];features.push({type:'Feature',geometry:{type:'Point',coordinates:[p.lon,p.lat]},properties:{role:'movie_location',movie_id:n[0],movie:n[1],year:n[3],place_id:nodes[p.node][0],place:p.name,relationship:m.relation,distance_km:m.distanceKm,distance_type:last.metric,coordinate_scope:p.scope,source_url:e[5],source_reference:e[4]}});}
  download('cinema-'+last.mode+'-analysis.geojson',JSON.stringify({type:'FeatureCollection',features}),'application/geo+json');
 };
 const taj=engine.places.find(place=>nodes[place.node][0]==='heritage:252');
 const castByFilm=new Map();
 for(const [film,relation,person] of edges){
  if(relation!=='cast_member')continue;
  if(!castByFilm.has(film))castByFilm.set(film,new Set());
  castByFilm.get(film).add(nodes[person][1]);
 }
 for(const button of document.querySelectorAll('[data-taj]')){
  button.disabled=!taj;
  button.onclick=()=>{
   apply({radiusKm:5,relation:'filming',genre:'',yearFrom:years[0],yearTo:years[1],heritageOnly:button.dataset.taj==='heritage'});
   $('filterSummary').textContent='All genres · '+years.join('–');
   choose(point(taj),taj.name,true);
   run(true);
   $('spatialSummary').scrollIntoView({block:'center'});
  };
 }
 $('tajQuery').onclick=()=>{
  const query=$('tajQueryText').textContent.replace('VALUES ?heritageOnly { false }','VALUES ?heritageOnly { '+$('heritageOnly').checked+' }');
  download('taj-mahal-5km-filming-cast.rq',query,'application/sparql-query');
 };
 $('placeForm').onsubmit=e=>{e.preventDefault();resolvePlace($('placeSearch').value);};
 $('radiusForm').onsubmit=e=>{e.preventDefault();run(true);};
 $('spatialQueryForm').onsubmit=e=>{e.preventDefault();try{const parsed=SpatialSearch.parseQuery($('spatialQuery').value,engine.genres,years);switchTool('nearby');apply(parsed);if(parsed.place===null){if(!center)throw Error('Choose a point before asking about “here”.');run(true);}else{$('placeSearch').value=parsed.place;resolvePlace(parsed.place,()=>run(true));}}catch(err){error(err.message);}};
 $('stateRegion').onchange=()=>{invalidate();populateDistricts();regionContext(true);};$('districtRegion').onchange=()=>invalidate();
 document.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>switchTool(b.dataset.tool));
 document.querySelectorAll('[data-radius]').forEach(b=>b.onclick=()=>{$('radiusKm').value=b.dataset.radius;invalidate();});
 for(const id of ['radiusKm','spatialRelation','spatialGenre','yearFrom','yearTo','heritageOnly','travelMode','travelMinutes'])$(id).addEventListener('change',()=>{invalidate();$('filterSummary').textContent=($('spatialGenre').value||'All genres')+' · '+$('yearFrom').value+'–'+$('yearTo').value;});
 function setTarget(value){target=value;$('pickStart').setAttribute('aria-pressed',String(value==='start'));$('pickEnd').setAttribute('aria-pressed',String(value==='end'));$('placeSearch').value='';$('mapStatus').textContent='Choose '+(value==='start'?'the starting point':'the destination')+' using search or the map.';}
 $('pickStart').onclick=()=>setTarget('start');$('pickEnd').onclick=()=>setTarget('end');
 $('drawStart').onclick=()=>{invalidate();drawPoints=[];drawn=null;drawing=true;renderDrawing();};
 $('drawUndo').onclick=()=>{invalidate();drawPoints.pop();drawn=null;drawing=true;renderDrawing();};
 $('drawFinish').onclick=finishDrawing;$('drawClear').onclick=()=>{invalidate();drawPoints=[];drawn=null;drawing=false;renderDrawing();};
 $('drawAdd').onclick=()=>{if(!$('drawLat').value||!$('drawLon').value){error('Enter both latitude and longitude.');return;}drawing=true;addDrawPoint([Number($('drawLat').value),Number($('drawLon').value)]);};
 $('cancelSpatial').onclick=()=>invalidate('Calculation cancelled.');$('fitAnalysis').onclick=()=>{initializeMap();fitSelection();};
 $('resetMap').onclick=()=>{center=end=null;centerName=endName='';drawPoints=[];drawn=null;drawing=false;apply({radiusKm:10,relation:'filming',genre:'',yearFrom:years[0],yearTo:years[1]});$('placeSearch').value='';$('spatialQuery').value='';switchTool('nearby');map.setView([22.5,79],5);};
 $('moreSpatial').onclick=more;apply({radiusKm:10,relation:'filming',genre:'',yearFrom:years[0],yearTo:years[1]});for(const genre of engine.genres)option($('spatialGenre'),genre,genre);$('spatialControls').disabled=false;
 if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){initializeMap();observer.disconnect();}},{rootMargin:'100px'});observer.observe($('cinemaMap'));}else initializeMap();
 return {engine,focusPlace(node){const p=engine.byNode.get(node);if(!p)return;switchTool('nearby');choose(point(p),p.name);$('spatial').scrollIntoView({behavior:'smooth'});run(true);}};
}
