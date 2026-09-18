"""Original business rules, executed deterministically in Python."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from config import CAMPAIGNS, FAMILY_MAP, ENGAGED_STATUSES, PAGE_SIZE

def engaged(status, responded):
    return responded is True or str(status or '').lower() in ENGAGED_STATUSES

def fmt_date(value):
    if not value:
        return '—'
    try:
        d = datetime.fromisoformat(value[:10])
        return f'{d:%b} {d.day}, {d.year}'
    except (ValueError, TypeError):
        return str(value)

def money(value):
    amount = Decimal(str(value or 0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return f'-${abs(amount):,}' if amount < 0 else f'${amount:,}'

def empty_bucket():
    return dict(count=0, value=Decimal(0), wonCount=0, wonValue=Decimal(0), saCount=0, saValue=Decimal(0))

def add(bucket, value, won, sa):
    # Original app treats missing ACV as zero for the displayed sums.
    amount = Decimal(str(value or 0))
    bucket['count'] += 1
    bucket['value'] += amount
    if won:
        bucket['wonCount'] += 1
        bucket['wonValue'] += amount
    if sa:
        bucket['saCount'] += 1
        bucket['saValue'] += amount

def event_stats(data):
    from campaigns import config
    FAMILY_MAP = config()["family"]
    events = {ev: dict(contacts=0, leads=0, convertedLeads=0, totalMembers=0,
                       sourced=empty_bucket(), influenced=empty_bucket()) for ev in ('namer', 'emea')}
    for c in data['campaigns']:
        ev = FAMILY_MAP[c['id']]
        contacts, leads, converted = c['contacts'], c['leads'], c['convertedLeads']
        events[ev].update(contacts=contacts, leads=leads, convertedLeads=converted,
                          totalMembers=contacts + leads - converted)
    for o in data['sourcedOpps']:
        add(events[FAMILY_MAP[o['campaignId']]]['sourced'], o['acv'], o['isWon'], o['saHit'])
    seen = {ev: set() for ev in events}
    for i in data['influence']:
        ev = FAMILY_MAP[i['ic']]
        if FAMILY_MAP.get(i['pc']) == ev or i['oi'] in seen[ev]:
            continue
        seen[ev].add(i['oi'])
        add(events[ev]['influenced'], i['acv'], i['won'], i['sa'])
    return events

def people(data):
    grouped = {}
    # Preserve the original grouping by ContactId, LeadId, choosing ContactId where available.
    for r in data['rows']:
        key = (r['cid'], r['lid'])
        p = grouped.setdefault(key, dict(id=r['cid'] or r['lid'], type='Contact' if r['cid'] else 'Lead',
            name=r['name'], title=r.get('title'), email=r['email'], company=r['company'], latest=r['cd'], memberships=[]))
        p['latest'] = max(p['latest'], r['cd'])
        p['memberships'].append(dict(campaignId=r['camp'], status=r['st'], hasResponded=r['hr'], createdDate=r['cd']))
    result = list(grouped.values())
    for p in result:
        from campaigns import widget_count
        p['engagedCount'] = widget_count(p['memberships'])
    return sorted(result, key=lambda p: (p['latest'], p['id']), reverse=True)

def accounts(data):
    grouped = {}
    for r in data['rows']:
        if not r['cid'] or not r['aid']:
            continue
        a = grouped.setdefault(r['aid'], dict(aid=r['aid'], aname=r.get('accountName', r['company']) or '—', latest=r['cd'], rows=[]))
        a['latest'] = max(a['latest'], r['cd'])
        a['rows'].append(r)
    result = list(grouped.values())
    for a in result:
        a['etmOwners'] = data.get('etmOwners', {}).get(a['aid'], [])
        a['contactCount'] = len({r['cid'] for r in a['rows']})
        a['engagedTouchpoints'] = sum(engaged(r['st'], r['hr']) for r in a['rows'])
    return sorted(result, key=lambda a: (a['latest'], a['aid']), reverse=True)

def page_items(items, page, term='', fields=()):
    if type(page) is not int or not 0 <= page <= 10000 or not isinstance(term, str) or len(term) > 120:
        raise ValueError('Invalid page or filter')
    term = term.strip().lower()
    rows = [r for r in items if not term or any(term in str(r.get(k) or '').lower() for k in fields)]
    start = page * PAGE_SIZE
    return rows[start:start + PAGE_SIZE], len(rows) > start + PAGE_SIZE
