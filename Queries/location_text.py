"""Conservative, auditable relation extraction over a supplied place gazetteer.

No locations are predicted from model memory. Every output must occur in the
source sentence and follow an explicit relationship trigger. Unmatched text is
left for review rather than coerced into a location.
"""
import re

NARRATIVE = re.compile(
    r'\b(?:is|was|are|were|being)\s+(?:primarily\s+|largely\s+|partly\s+)?set\s+(?:in|against\s+the\s+backdrop\s+of)\b'
    r'|\b(?:story|plot|narrative|film)\s+(?:\w+\s+){0,3}(?:takes?\s+place|unfolds?|is\s+based)\s+in\b'
    r'|^Set\s+(?:in|against\s+the\s+backdrop\s+of)\b'
    r'|\b(?:lives?|resides?|settles?|living|residing|works?|stays?|arrives?)\s+in\b'
    r'|\b(?:moves?|relocates?|travels?|returns?|goes?|went)\s+to\b', re.I)
FILMING = re.compile(
    r'\b(?:was|were|is|been)\s+(?:(?:primarily|mostly|entirely|partly|also|mainly|partially|extensively|largely|predominantly)\s+)*'
    r'(?:filmed|shot)\s+(?:on\s+location\s+)?(?:in|at|across)\b'
    r'|\b(?:filming|shooting|principal\s+photography)\s+(?:\w+\s+){0,5}'
    r'(?:took\s+place|commenced|began|started|continued|occurred|completed|conducted|done)\s+(?:in|at|across)\b', re.I)
NEGATIVE = re.compile(r'\b(?:not|never|planned|planning|proposed|cancelled|canceled|scheduled|intended|supposed|would|will)\b', re.I)
NOT_PLACES = {'hindi','tamil','telugu','english','india films','color','colour','black and white',
              'the future','the past','space','outer space','the middle ages','indian'}

def gazetteer_pattern(names):
    # The entries originate from explicit geographic statements/categories.
    clean = {n.strip():n.strip() for n in names if n and len(n.strip())>=3
             and n.lower() not in NOT_PLACES and not re.fullmatch(r'\d+(?:s)?',n.strip())}
    aliases = {}
    for name in sorted(clean):
        aliases[name] = name
        if name.startswith('the '):
            aliases[name[4:]] = name
    # Known historical name variants, only when the modern name is in the source gazetteer.
    for alias, canonical in [('Bombay','Mumbai'),('Calcutta','Kolkata'),('Madras','Chennai'),('Bangalore','Bengaluru'),('Benaras','Varanasi'),('Benares','Varanasi')]:
        if canonical in clean:
            aliases[alias] = canonical
    if not aliases:
        return None, {}
    lookup = {k.casefold():v for k,v in aliases.items()}
    return re.compile(r'(?<!\w)(?:'+ '|'.join(re.escape(n) for n in sorted(aliases,key=lambda s:(-len(s),s))) +r')(?!\w)',re.I), lookup

def sections(text):
    section = 'Lead'
    for chunk in re.split(r'(^={2,6}\s*[^\n]+?\s*={2,6}\s*$)',text,flags=re.M):
        if re.match(r'^={2,6}',chunk):
            section = chunk.strip('= \n')
        else:
            yield section, chunk

def extract(text, names, evidence_only=False):
    pattern, lookup = gazetteer_pattern(names)
    if pattern is None:
        return []
    results = []
    for section, chunk in sections(text):
        plot = bool(re.search(r'plot|synopsis|story',section,re.I))
        production = bool(re.search(r'filming|production|photography|shooting',section,re.I))
        lead = section=='Lead'
        if not (plot or production or lead or evidence_only):
            continue
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])|\s*\|\|\s*|\n+',chunk):
            sentence=sentence.strip()
            if not sentence or NEGATIVE.search(sentence):
                continue
            for relation, trigger in [('narrative',NARRATIVE),('filming',FILMING)]:
                if relation=='filming' and plot:
                    continue
                if relation=='narrative' and production:
                    continue
                for match in trigger.finditer(sentence):
                    # Outside plot, character travel/residence is not reliable evidence.
                    if relation=='narrative' and not plot and re.match(r'(lives?|resides?|settles?|living|residing|works?|stays?|arrives?|moves?|relocates?|travels?|returns?|goes?|went)\b',match.group(),re.I):
                        continue
                    tail=sentence[match.end():]
                    # Do not cross a new clause and attribute its place to this trigger.
                    tail=re.split(r'\b(?:while|whereas|but|although|which|where|before|after|because|with|from)\b|\band\s+(?:(?:it|the film)\s+)?(?:(?:was|is)\s+)?(?:filmed|shot|set)\b|[.;:]|\s[–—]\s',tail,maxsplit=1,flags=re.I)[0][:160]
                    first_clause=tail.split(',')[0]
                    if not pattern.search(first_clause) and not re.search(r'\b(?:locations?|places|areas)\b',first_clause,re.I):
                        continue
                    for place in pattern.finditer(tail):
                        if place.start()>100:
                            continue
                        if re.search(r'\b(?:IIT|IIM|University of|Hotel)\s+$',tail[:place.start()]):
                            continue
                        results.append({'relation':relation,'place_name':lookup[place.group().casefold()],
                                        'evidence':sentence,'section':section})
    return results
