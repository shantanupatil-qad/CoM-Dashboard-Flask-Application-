"""Original business rules, executed deterministically in Python."""
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
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

def abbreviate(value):
    # Matches Salesforce dashboard metrics' "auto" display units (e.g. 16,550,903 -> "17M").
    if value is None:
        return '—'
    amount = float(value)
    for divisor, suffix in ((1_000_000_000, 'B'), (1_000_000, 'M'), (1_000, 'K')):
        if abs(amount) >= divisor:
            return f'{amount / divisor:,.0f}{suffix}'
    return f'{amount:,.0f}'

def sf_refresh_label(iso_value):
    if not iso_value:
        return None
    normalized = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', iso_value.replace('Z', '+00:00'))
    try:
        dt = datetime.fromisoformat(normalized).astimezone(ZoneInfo('America/Los_Angeles'))
    except ValueError:
        return None
    return f"As of {dt.strftime('%b %-d, %Y %-I:%M %p')}"

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
    from campaigns import config, widget_count, widget_engaged
    family = config()['family']
    widgets = config()['widgets']
    for p in result:
        p['engagedCount'] = widget_count(p['memberships'])
        p['namerEngaged'] = sum(widget_engaged(w, p['memberships']) for w in widgets if w['event'] == 'namer')
        p['emeaEngaged'] = sum(widget_engaged(w, p['memberships']) for w in widgets if w['event'] == 'emea')
        p['opportunities'] = data.get('personOpportunities', {}).get(p['id'], [])
    result.sort(key=lambda p: (p['latest'], p['id']), reverse=True)
    # NAMER-engaged people first, then EMEA-only; within each group, most engagements
    # in that group's region come first, ties broken by the recency order above.
    def region_rank(p):
        is_namer = any(family.get(m['campaignId']) == 'namer' for m in p['memberships'])
        return (0, -p['namerEngaged']) if is_namer else (1, -p['emeaEngaged'])
    result.sort(key=region_rank)
    return result

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
        a['personOpportunities'] = data.get('personOpportunities', {})
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
