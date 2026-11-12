"""Flexible, inspectable patterns over recorded data; ambiguity is never silently guessed."""
import contextlib,json,re
from build_integrated_graph import norm


def title_reference(text):
    match=re.fullmatch(r'(.+?)\s+\(?((?:19|20)\d{2})(?:\s+(?:\w+\s+)?film)?\)?',text.strip(),flags=re.I)
    return (match[1].strip(),int(match[2])) if match and 1970<=int(match[2])<=2025 else (text.strip(),None)

def resolve(catalog,text,kind):
    clean,year=title_reference(text)
    found=catalog.search(clean,kind,limit=30)['items'];exact=[n for n in found if norm(clean) in [norm(re.sub(r'\s*\([^)]*\)\s*',' ',label)) for label in [n['label']]+n.get('aliases',[])] and (year is None or n['year']==year)]
    if len(exact)==1:return exact[0]
    if not exact and kind in ('Place','Heritage'):
        with contextlib.closing(catalog.connect()) as con:
            for row in con.execute('SELECT payload FROM geometry'):
                p=json.loads(row[0])
                if norm(text) in [norm(a) for a in p.get('aliases',[])]:exact.append(dict(id=p['id'],label=p['name'],kind='Heritage' if p['heritage'] else 'Place',year=None))
    if len(exact)==1:return exact[0]
    return dict(choices=exact or found[:8],error='Choose the intended record' if exact else 'No exact identity match. Select a suggestion or refine the title/year.')


def answer(catalog,question):
    q=question.strip().rstrip('?.!')
    if not q or len(q)>500:raise ValueError('Enter a question up to 500 characters')
    q=re.sub(r'^(?:please\s+)?(?:can you\s+)?','',q,flags=re.I)
    q=re.sub(r'\b(?:tracks|tunes|gaane|गाने)\b','songs',q,flags=re.I)
    q=re.sub(r'\b(?:pictures|cinema movies|films)\b','movies',q,flags=re.I)
    m=re.match(r'^(?:where (?:was|were|is)\s+)(?:the\s+)?(?:(song|movie)\s+)?(.+?)\s+(?:filmed|shot|taken|recorded)$',q,re.I)
    if m:
        kind='Song' if (m[1] or '').lower()=='song' else 'Film';entity=resolve(catalog,m[2],kind)
        if entity.get('error') and not m[1]:kind='Song';entity=resolve(catalog,m[2],kind)
        if entity.get('error'):return entity
        graph=catalog.graph(entity['id']);wanted='song_filming' if kind=='Song' else 'filming'
        edges=[e for e in graph['edges'] if e['subject']==entity['id'] and e['relation']==wanted]
        return dict(intent='recorded_filming',interpretation=f"Explicit {kind.lower()} filming links for {entity['label']}",items=[dict(entity=graph['nodes'][e['object']],edge=e) for e in edges],note='Locations come from explicit relationships. Missing links are coverage gaps; film locations are not inherited by songs.')
    m=re.match(r'^(?:which |show |find |list )?(songs|movies)\s+(?:were )?(?:filmed|shot|taken)\s+(?:in|at|on)\s+(.+)$',q,re.I)
    if m:
        place=resolve(catalog,m[2],'Place')
        if place.get('error'):place=resolve(catalog,m[2],'Heritage')
        if place.get('error'):return place
        graph=catalog.graph(place['id']);wanted='song_filming' if m[1].lower()=='songs' else 'filming'
        edges=[e for e in graph['edges'] if e['object']==place['id'] and e['relation']==wanted]
        return dict(intent='recorded_filming_at',interpretation=f"Explicit {m[1].lower()} links at {place['label']}",items=[dict(entity=graph['nodes'][e['subject']],edge=e) for e in edges],note='A direct place match; nearby-city points are not substituted for named sites.')
    m=re.match(r'^(?:nearest|closest)\s+(?:heritage|heritage sites|sites)\s+(?:to|near)\s+(.+)$',q,re.I)
    if m:
        place=resolve(catalog,m[1],'Place')
        if place.get('error'):return place
        node=catalog.node(place['id']);a=node['attributes']
        if a.get('latitude','')=='':raise ValueError('This place has no coordinate')
        near=catalog.nearest(a['latitude'],a['longitude'],2000,10,heritage=True)
        return dict(intent='nearest_heritage',interpretation='Nearest recorded heritage references to '+place['label'],items=near['items'],note='Spherical distance between reference points; proximity does not establish filming.')
    return dict(intent='help',interpretation='Supported examples',items=[],note='Try “Where was the song Bismil filmed?”, “Which songs were shot in Mumbai?”, “Where was Fanaa 2006 filmed?”, or “Nearest heritage sites to Chennai”. For arbitrary points, areas, regions and road routes use Map & analysis.')
