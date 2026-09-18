"""Snapshot-scoped campaign discovery and widget configuration."""
import re
from contextvars import ContextVar
from config import CAMPAIGNS as ORIGINAL
BASE = [dict(next(c for c in ORIGINAL if c['id']==id),label=label) for id,label in [
('701TR00000tTIebYAG','Registration'),('701TR000016ovjzYAA','ERP ROI Calculator'),
('701TR0000179AenYAE','Executive Meeting'),('701TR000016z9X3YAI','Attendee QR Code'),
('701TR000017I31KYAS','On Floor Demo'),('701TR00000ttfUHYAY','Registration'),
('701TR0000179FuaYAE','Executive Meeting'),('701TR000017R4SnYAK','On Floor Demo')]]
BASE.append(dict(id='701TR000017vR5OYAU',event='emea',label='QR Code Scan',abbr='QR'))
def build_config(rows=()):
    sessions=[dict(id=r['Id'],event='namer',label=re.sub(r'^(BR|TH) Session-','',re.sub(r'^#CoM\s+','',r['Name'])),group='breakout' if re.search('BR Session',r['Name'],re.I) else 'theater') for r in rows]
    campaigns=BASE+sessions
    widgets=[]
    for event in ('namer','emea'):
        suffix='NAmer' if event=='namer' else 'EMEA'
        for c in BASE:
            if c['event']==event:
                widgets.append(dict(id=c['id'],event=event,label=c['label']+f' ({suffix})',abbr=c['abbr'],type='individual',campaignIds=[c['id']]))
        if event=='namer':
            for group,label,abbr in [('theater','Theater Session','TH'),('breakout','Breakout Session','BR')]:
                widgets.append(dict(id=group,event=event,label=label+' (NAmer)',abbr=abbr,type='grouped',campaignIds=[c['id'] for c in sessions if c['group']==group]))
    return dict(campaigns=campaigns,widgets=widgets,by_id={c['id']:c for c in campaigns},family={c['id']:c['event'] for c in campaigns})
CURRENT=ContextVar('campaign_config',default=build_config())
def config(): return CURRENT.get()
def widget_engaged(w, memberships):
    from model import engaged
    by={m['campaignId']:m for m in memberships}
    return any(id in by and engaged(by[id]['status'],by[id]['hasResponded']) for id in w['campaignIds'])
def widget_count(memberships): return sum(widget_engaged(w,memberships) for w in config()['widgets'])
def etm_owners(account_id,eligible,associations,owners):
    if eligible not in ('Licensed EU','Remote EU'): return []
    result=[]
    for label,roles,prefixes in [('Supply Chain',('AE',),('Supply',)),('ERP',('AE','Channel Manager'),('Named','ERP','Channel')),('Redzone',('AE',),('Redzone',))]:
        ids={r['Territory2Id'] for r in associations if r['ObjectId']==account_id and (r.get('Territory2') or {}).get('Territory2Model',{}).get('State')=='Active' and (r.get('Territory2') or {}).get('Territory2Type',{}).get('MasterLabel','').startswith(prefixes)}
        names=list(dict.fromkeys(r['User']['Name'] for r in owners if r['Territory2Id'] in ids and r['RoleInTerritory2'] in roles and (r.get('User') or {}).get('Name')))
        if names: result.append(dict(bu=label,names=', '.join(names)))
    return result
