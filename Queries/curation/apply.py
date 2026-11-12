"""Conservative identity normalization. Uncertain duplicates are exposed for review."""
import collections,hashlib,json,math,re
from pathlib import Path

GENERIC={'the','a','an','monastery','cathedral','church','temple','palace','fort','building','component','unknown','unnamed'}


def apply(graph):
    from build_integrated_graph import norm
    path=graph.data/'../Queries/curation/rules.json'
    rules=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if path.exists():graph.inputs['../Queries/curation/rules.json']=dict(rows=sum(len(v) for v in rules.values() if isinstance(v,list)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    redirects={};changes=[];duplicates=[];aliases=[]
    for pid,p in graph.places.items():
        original=p['place_name'];label=norm(original)
        if not label or label in GENERIC:
            parent=graph.places.get(p.get('heritage_parent_id',''),{})
            p['original_label']=original
            p['place_name']=(parent.get('place_name','Unresolved place')+' — component '+pid.split(':')[-1]) if parent else ('Unresolved place '+pid)
            p['quality_flags']='generic_source_label'
            changes.append(dict(entity_id=pid,kind='Place',original=original,canonical=p['place_name'],method='parent_qualified_display_label',source=p.get('coordinate_source',''),note='Specific original name missing; no historic name guessed.'))
        else:p.setdefault('quality_flags','')
        p.setdefault('original_label',original)
    groups=collections.defaultdict(list)
    for pid,p in graph.places.items():
        if p.get('quality_flags') or pid.startswith('heritage:') or p.get('heritage_parent_id'):continue
        groups[norm(p['place_name'])].append(pid)
    for label,ids in groups.items():
        for index,a in enumerate(ids):
            for b in ids[index+1:]:
                x,y=graph.places[a],graph.places[b]
                exact=(x['latitude']!='' and y['latitude']!='' and abs(x['latitude']-y['latitude'])<1e-7 and abs(x['longitude']-y['longitude'])<1e-7)
                source_same=bool(x['coordinate_source'] and x['coordinate_source']==y['coordinate_source'])
                same_country=bool(x['country_names'] and x['country_names']==y['country_names'])
                strong_conflict=a.startswith('Q') and b.startswith('Q') and a!=b
                compatible=(x.get('heritage_kind','')==y.get('heritage_kind','') and x.get('place_type')==y.get('place_type'))
                auto=exact and source_same and same_country and compatible and not strong_conflict
                canonical,alias=sorted([a,b],key=lambda k:(not k.startswith('Q'),k))
                if auto:redirects[alias]=canonical
                duplicates.append(dict(kind='Place',left_id=a,right_id=b,label=x['place_name'],status='exact_duplicate_merged' if auto else 'needs_identity_review',reason='Same label and identical point/source/country/type' if auto else 'Name alone cannot establish identity'))
    for row in rules.get('place_redirects',[]):
        old,new=row['alias_id'],row['canonical_id']
        if old in graph.places and new in graph.places:
            if not row.get('source_url'):raise ValueError('Reviewed place merge needs a source')
            redirects[old]=new
    for old,new in list(redirects.items()):
        visited={old}
        while new in redirects:
            if new in visited:raise ValueError('Identity redirect cycle')
            visited.add(new);new=redirects[new]
        redirects[old]=new
    for old,new in redirects.items():
        p=graph.places[old];target=graph.places[new]
        names=set(json.loads(target.get('aliases') or '[]'))|{p['place_name']}
        target['aliases']=json.dumps(sorted(names-{target['place_name']}),ensure_ascii=False)
        aliases.append(dict(kind='Place',alias_id=old,canonical_id=new,alias_label=p['place_name'],source=p['coordinate_source']))
    for c in graph.claims.values():
        for column in ['subject_id','object_id']:
            if c[column] in redirects:c['original_'+column]=c[column];c[column]=redirects[c[column]]
    for row in graph.song_locations:
        row['place_id']=redirects.get(row['place_id'],row['place_id'])
    for old in redirects:del graph.places[old]
    song_redirects={}
    for rule in rules.get('song_redirects',[]):
        old,new=rule['alias_id'],rule['canonical_id']
        if old not in graph.songs or new not in graph.songs:raise ValueError('Reviewed song redirect references an unknown song')
        if not rule.get('source_url') or graph.songs[old]['film_id']!=graph.songs[new]['film_id']:raise ValueError('Song merges need a source and the same canonical film')
        if old==new:continue
        song_redirects[old]=new
    for old,new in list(song_redirects.items()):
        visited={old}
        while new in song_redirects:
            if new in visited:raise ValueError('Song redirect cycle')
            visited.add(new);new=song_redirects[new]
        song_redirects[old]=new
    for old,new in song_redirects.items():
        rule=next(r for r in rules['song_redirects'] if r['alias_id']==old)
        aliases.append(dict(kind='Song',alias_id=old,canonical_id=new,alias_label=graph.songs[old]['title'],source=rule['source_url']))
        for c in graph.claims.values():
            for column in ['subject_id','object_id']:
                if c[column]==old:c['original_'+column]=old;c[column]=new
        for row in graph.song_locations:
            if row['song_id']==old:row['song_id']=new
    for old in song_redirects:del graph.songs[old]
    for rule in rules.get('song_aliases',[]):
        fid=graph.lookup('wikidata',rule['film_wikidata_id'])
        found=[s for s in graph.songs.values() if s['film_id']==fid and norm(s['title'])==norm(rule['canonical_title'])]
        if len(found)==1:
            for title in rule['aliases']:aliases.append(dict(kind='Song',alias_id='',canonical_id=found[0]['song_id'],alias_label=title,source=rule['source_url']))
    by_film=collections.defaultdict(list)
    for song in graph.songs.values():by_film[song['film_id']].append(song)
    for fid,songs in by_film.items():
        for i,a in enumerate(songs):
            for b in songs[i+1:]:
                x,y=norm(a['title']),norm(b['title'])
                if x and y and (x.startswith(y+' ') or y.startswith(x+' ')):
                    duplicates.append(dict(kind='Song',left_id=a['song_id'],right_id=b['song_id'],label=a['title']+' / '+b['title'],status='needs_identity_review',reason='Possible short title, remix or language/version; no automatic merge'))
    graph.curation=dict(changes=changes,duplicates=duplicates,aliases=aliases,redirects=redirects)
    graph.place_quality.update(types=dict(collections.Counter(p.get('place_type','unknown') for p in graph.places.values())),precision=dict(collections.Counter(p.get('location_precision','unknown_reference') for p in graph.places.values())),normalized_display_labels=len(changes),merged_exact_duplicates=len(redirects),duplicate_pairs_for_review=sum(d['status']=='needs_identity_review' for d in duplicates))


def export(graph,out):
    import csv
    curation=getattr(graph,'curation',dict(changes=[],duplicates=[],aliases=[]))
    for name,rows,fields in [('identity_changes.csv',curation['changes'],'entity_id,kind,original,canonical,method,source,note'),('identity_duplicates.csv',curation['duplicates'],'kind,left_id,right_id,label,status,reason'),('entity_aliases.csv',curation['aliases'],'kind,alias_id,canonical_id,alias_label,source')]:
        with (out/name).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields.split(','));writer.writeheader();writer.writerows(rows)
