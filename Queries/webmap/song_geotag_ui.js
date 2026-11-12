'use strict';
function initSongGeotagging({data,getPoint}){
 const $=id=>document.getElementById(id),index=SongGeo.createIndex(data);let chosen=null;
 $('songReviewCount').textContent=(data.songLocationReview||[]).length+' existing song-location notes remain in the review list. They are not accepted geotags.';
 $('songTagSearch').oninput=()=>{chosen=null;$('songTagSelected').textContent='Choose a matching song below.';$('songTagChoices').replaceChildren();if(!$('songTagSearch').value.trim())return;
  for(const s of index.find($('songTagSearch').value)){const b=document.createElement('button');b.type='button';b.textContent=s.title+' · '+s.filmTitle+' · '+s.year;b.onclick=()=>{chosen=s;$('songTagSelected').textContent=b.textContent;$('songTagChoices').replaceChildren();};$('songTagChoices').append(b);}
 };
 $('songTagUsePoint').onclick=()=>{const p=getPoint();if(!p.center){$('songTagStatus').textContent='Select a point or place on the map first.';return;}$('songTagLat').value=p.center[0];$('songTagLon').value=p.center[1];$('songTagPlace').value=p.name;$('songTagStatus').textContent='Point copied. Select its precision and add song-specific evidence.';};
 $('songTagForm').onsubmit=e=>{e.preventDefault();try{
  if(!chosen)throw Error('Choose a song from the search results first.');
  const value=SongGeo.validateProposal({song_id:chosen.id,film_id:data.nodes[chosen.film][0],place_name:$('songTagPlace').value,latitude:Number($('songTagLat').value),longitude:Number($('songTagLon').value),source_url:$('songTagSource').value,evidence:$('songTagEvidence').value,location_precision:$('songTagPrecision').value,scene_timestamp:$('songTagTime').value,status:'proposed'},data);
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='proposed-song-geotag.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  $('songTagStatus').textContent='Proposal prepared for download. The accepted graph has not changed; review the source before importing it.';
 }catch(error){$('songTagStatus').textContent=error.message;}};
}
