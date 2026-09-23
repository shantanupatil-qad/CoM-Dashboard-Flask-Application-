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
    sf_dashboard = dict(
        notes=[[dict(text='Influenced Opportunities', bold=True, underline=False), dict(text=' are fictional demo figures.', bold=False, underline=False)],
               [dict(text='Sourced Opportunities', bold=True, underline=False), dict(text=' are fictional demo figures.', bold=False, underline=False)]],
        metrics=[dict(header='Total Influenced Opportunities', value=42, label='42'),
                 dict(header='Total Influenced Solutions Revenue', value=1250000, label='1,250,000'),
                 dict(header='Total Sourced Opportunities', value=18, label='18'),
                 dict(header='Total Sourced Solutions Revenue', value=650000, label='650,000')],
        bars=[dict(header='Influenced Opportunities by Region', groups=[dict(label='#Chicago (Main)', value=25), dict(label='#Munich (Main)', value=17)]),
              dict(header='Influenced Solutions Revenue by Region', groups=[dict(label='#Chicago (Main)', value=800000), dict(label='#Munich (Main)', value=450000)]),
              dict(header='Sourced Opportunities by Region', groups=[dict(label='#Chicago (Main)', value=12), dict(label='#Munich (Main)', value=6)]),
              dict(header='Sourced Solutions Revenue by Region', groups=[dict(label='#Chicago (Main)', value=420000), dict(label='#Munich (Main)', value=230000)])],
        gauges=[dict(header='Influence Pipeline - Services Revenue Target', value=1250000, target=2000000),
                dict(header='Sourced Pipeline - Services Revenue Target', value=650000, target=1000000)],
    )
    return dict(sessions=sessions,etmOwners={sid('001',0):[dict(bu='ERP',names='Demo Owner')]},campaigns=[dict(id=f['parentId'], contacts=120 if ev=='namer' else 80, leads=50 if ev=='namer' else 35, convertedLeads=10 if ev=='namer' else 5) for ev,f in FAMILIES.items()],
        sourcedOpps=[dict(id=sid('006', n), campaignId=CAMPAIGNS[n%8]['id'], acv=25000+n*12500, isWon=n%3==0, saHit=n%2==0) for n in range(12)],
        influence=[dict(ic=CAMPAIGNS[n%8]['id'], oi=sid('006', 30+n//2), pc=None, acv=40000+(n//2)*10000, won=n%4==0, sa=n%3!=0) for n in range(10)], rows=rows,
        sfDashboard=sf_dashboard)
