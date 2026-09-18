"""Fictional records for local demonstrations only."""
from config import FAMILIES
from campaigns import build_config

def demo_data():
    def sid(prefix, n):
        return prefix + str(n).zfill(15)
    sessions = [dict(Id=sid('701',800+i),Name=name) for i,name in enumerate(['#CoM TH Session-Factory AI','#CoM TH Session-Operations','#CoM BR Session-Supply Chain'])]
    CAMPAIGNS = build_config(sessions)['campaigns']
    companies = ['Aster Manufacturing', 'Northstar Components', 'Meridian Industrial', 'Atlas Precision']
    rows = []
    for n in range(48):
        is_lead = n >= 40
        for c, campaign in enumerate(CAMPAIGNS):
            if (n + c) % 3 != 0:
                continue
            rows.append(dict(id=sid('00v', n*len(CAMPAIGNS)+c), cid=None if is_lead else sid('003', n), lid=sid('00Q', n) if is_lead else None,
                title='Operations Director', ctitle='Operations Director', name=f'{["Alex", "Jordan", "Morgan", "Riley"][n%4]} Example {n+1}', email=f'demo{n+1}@example.com',
                company=companies[n%4], aid=None if is_lead else sid('001', n%4), cname=f'{["Alex", "Jordan", "Morgan", "Riley"][n%4]} Example {n+1}', cemail=f'demo{n+1}@example.com',
                camp=campaign['id'], st='Registered' if n%3 else 'Invited', hr=n%5==0, cd=f'2026-09-{1+n%9:02d}'))
    return dict(sessions=sessions,etmOwners={sid('001',0):[dict(bu='ERP',names='Demo Owner')]},campaigns=[dict(id=f['parentId'], contacts=120 if ev=='namer' else 80, leads=50 if ev=='namer' else 35, convertedLeads=10 if ev=='namer' else 5) for ev,f in FAMILIES.items()],
        sourcedOpps=[dict(id=sid('006', n), campaignId=CAMPAIGNS[n%8]['id'], acv=25000+n*12500, isWon=n%3==0, saHit=n%2==0) for n in range(12)],
        influence=[dict(ic=CAMPAIGNS[n%8]['id'], oi=sid('006', 30+n//2), pc=None, acv=40000+(n//2)*10000, won=n%4==0, sa=n%3!=0) for n in range(10)], rows=rows)
