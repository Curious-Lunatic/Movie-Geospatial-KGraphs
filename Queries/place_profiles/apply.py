"""Attach auditable place identity/precision metadata without inventing film links."""
import collections,hashlib,json

COUNTRIES={'country','sovereign state','island country','landlocked country'}
CITIES={'city','big city','metropolis','megacity','town','village','capital city','national capital','port city','human settlement'}
REGIONS={'continent','subcontinent','geographic region','historical region','state of India','state','province','district','district of India','union territory of India','union territory','administrative territorial entity'}
VENUES={'fort','palace','temple','Hindu temple','museum','railway station','airport','building','monument','archaeological site','beach','bridge','garden','park','lake','waterfall','mountain'}


def classify(place,record):
    scope=place['coordinate_scope']
    if scope=='heritage_property_representative_point': return 'heritage_property'
    if scope=='heritage_component_representative_point': return 'heritage_component'
    if place.get('heritage_kind')=='historic_component': return 'historic_component'
    if place.get('heritage_kind') or scope=='historic_site_representative_point': return 'historic_site'
    types={t['label'] for t in record.get('instance_of',[])}
    for kind,accepted in [('country',COUNTRIES),('city',CITIES),('region',REGIONS),('venue',VENUES)]:
        if types & accepted: return kind
    return 'unknown'


def apply(graph):
    prefix='../Queries/place_profiles/'
    snapshots={}
    for name in ['wikidata.json','reviewed.json']:
        path=graph.data/prefix/name
        if path.exists():
            raw=path.read_bytes();snapshots[name]=json.loads(raw)
            graph.inputs[prefix+name]=dict(rows=len(snapshots[name]['records']),sha256=hashlib.sha256(raw).hexdigest())
    metadata=snapshots.get('wikidata.json',{}).get('records',{})
    reviewed=snapshots.get('reviewed.json',{}).get('records',{})
    for pid,record in reviewed.items():
        if record.get('create_reference') and pid not in graph.places:
            source=metadata.get(pid,{})
            candidates=source.get('coordinates',[])
            if not candidates:
                graph.issue('reference_site_without_coordinate',prefix+'reviewed.json','',pid)
                continue
            from build_integrated_graph import coordinates
            candidate=candidates[0]
            point=coordinates(candidate['latitude'],candidate['longitude'])
            if not point: raise ValueError('Invalid reference-site coordinate: '+pid)
            graph.add_place(pid,record['name'],point,'historic_site_representative_point',source['source'])
            graph.places[pid].update(heritage_kind=record['heritage_kind'],heritage_source=record['identity_source'],country_codes='IN',country_names='India')
    for pid,p in graph.places.items():
        source=metadata.get(pid,{})
        review=reviewed.get(pid,{})
        kind=review.get('type') or classify(p,source)
        precision={'city':'locality_reference','country':'country_reference','region':'region_reference','heritage_property':'site_reference','heritage_component':'site_reference','historic_site':'site_reference','historic_component':'site_reference','venue':'site_reference'}.get(kind,'unknown_reference')
        aliases=sorted(set(source.get('aliases',[])+review.get('aliases',[]))-{p['place_name']})
        p.update(place_type=kind,location_precision=precision,aliases=json.dumps(aliases,ensure_ascii=False),
            locality=review.get('locality') or ', '.join(source.get('localities',[])[:2]),
            description=review.get('description') or source.get('description',''),
            identity_source=review.get('identity_source') or source.get('source','') or p.get('heritage_source','') or p['coordinate_source'],
            classification_source=review.get('identity_source') or source.get('source',''),
            wikidata_revision=source.get('revision',''))
        if not p['country_names'] and source.get('countries'): p['country_names']=' | '.join(source['countries'])
    graph.place_quality=dict(types=dict(collections.Counter(p['place_type'] for p in graph.places.values())),
        precision=dict(collections.Counter(p['location_precision'] for p in graph.places.values())),
        wikidata_profile_records=len(metadata),reviewed_profile_records=len(reviewed),
        method='Existing geometry retained. Classification uses exact Wikidata instance-of labels or explicitly reviewed identities. Reference sites add no movie assertions.')
