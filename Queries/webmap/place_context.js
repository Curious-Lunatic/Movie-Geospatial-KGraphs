/* Local, structured place context shared by the panel and future query clients. */
(function(root){
'use strict';
function createPlaceContext(data){
 const nodes=data.nodes,children=new Map(),links=new Map();
 for(const edge of data.edges){
  if(edge[1]==='part_of_heritage'){if(!children.has(edge[2]))children.set(edge[2],[]);children.get(edge[2]).push(edge[0]);}
  if(['filming','narrative'].includes(edge[1])&&nodes[edge[0]][2]==='Film'){
   if(!links.has(edge[2]))links.set(edge[2],[]);links.get(edge[2]).push(edge);
  }
 }
 return function describe(node){
  if(!Number.isInteger(node)||!nodes[node])return null;
  const n=nodes[node],ids=new Set(),queue=[node];
  while(queue.length){const id=queue.pop();if(ids.has(id))continue;ids.add(id);queue.push(...(children.get(id)||[]));}
  const films=new Map();
  for(const id of ids)for(const e of links.get(id)||[]){
   if(!films.has(e[0]))films.set(e[0],{node:e[0],name:nodes[e[0]][1],year:nodes[e[0]][3],connections:[]});
   films.get(e[0]).connections.push({relation:e[1],place:nodes[e[2]][1],sourceUrl:e[5],sourceUrls:[...new Set([e[5],...(e[7]||[])].filter(Boolean))],sourceRecord:e[4],evidence:e[6],assertions:e[3]});
  }
  return {id:n[0],name:n[1],heritage:n[2]==='Heritage',heritageSource:n[6]||'',...(data.placeDetails?.[n[0]]||{}),films:[...films.values()].sort((a,b)=>a.name.localeCompare(b.name))};
 };
}
if(typeof module==='object'&&module.exports)module.exports={createPlaceContext};else root.createPlaceContext=createPlaceContext;
})(typeof globalThis!=='undefined'?globalThis:this);
