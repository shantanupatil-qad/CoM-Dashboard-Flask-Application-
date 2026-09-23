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
    demo_breaks = [dict(color='#c23934', lowerBound=None, upperBound=0), dict(color='#ca8501', lowerBound=0, upperBound=1), dict(color='#00716b', lowerBound=1, upperBound=None)]
    demo_refresh = '2026-09-23T14:55:39.000+0000'
    demo_common = dict(reportId=sid('00O', 1), reportName='Demo Report - Fictional', refreshDate=demo_refresh)
    sf_dashboard = dict(
        notes=[[dict(text='Influenced Opportunities', bold=True, underline=False), dict(text=' are fictional demo figures.', bold=False, underline=False)],
               [dict(text='Sourced Opportunities', bold=True, underline=False), dict(text=' are fictional demo figures.', bold=False, underline=False)]],
        metrics=[dict(**demo_common, header='Total Influenced Opportunities', value=42, label='42', breaks=demo_breaks, aggregateLabel='Unique Count of Opportunity ID'),
                 dict(**demo_common, header='Total Influenced Solutions Revenue', value=1250000, label='1,250,000', breaks=demo_breaks, aggregateLabel='Sum of Solutions Rev'),
                 dict(**demo_common, header='Total Sourced Opportunities', value=18, label='18', breaks=demo_breaks, aggregateLabel='Unique Count of Opportunity ID'),
                 dict(**demo_common, header='Total Sourced Solutions Revenue', value=650000, label='650,000', breaks=demo_breaks, aggregateLabel='Sum of Solutions Rev')],
        bars=[dict(**demo_common, header='Influenced Opportunities by Region', groupingLabel='#CoM Grouping', aggregateLabel='Unique Count of Opportunity ID',
                   groups=[dict(label='#Chicago (Main)', value=25, valueLabel='25'), dict(label='#Munich (Main)', value=17, valueLabel='17')]),
              dict(**demo_common, header='Influenced Solutions Revenue by Region', groupingLabel='#CoM Grouping', aggregateLabel='Sum of Solutions Rev',
                   groups=[dict(label='#Chicago (Main)', value=800000, valueLabel='800,000'), dict(label='#Munich (Main)', value=450000, valueLabel='450,000')]),
              dict(**demo_common, header='Sourced Opportunities by Region', groupingLabel='#CoM Grouping', aggregateLabel='Unique Count of Opportunity ID',
                   groups=[dict(label='#Chicago (Main)', value=12, valueLabel='12'), dict(label='#Munich (Main)', value=6, valueLabel='6')]),
              dict(**demo_common, header='Sourced Solutions Revenue by Region', groupingLabel='#CoM Grouping', aggregateLabel='Sum of Solutions Rev',
                   groups=[dict(label='#Chicago (Main)', value=420000, valueLabel='420,000'), dict(label='#Munich (Main)', value=230000, valueLabel='230,000')])],
        gauges=[dict(**demo_common, header='Influence Pipeline - Services Revenue Target', value=1250000,
                     breaks=[dict(color='#c23934', lowerBound=2000000, upperBound=2000001), dict(color='#ca8501', lowerBound=2000001, upperBound=2000002), dict(color='#00716b', lowerBound=2000002, upperBound=2000003)]),
                dict(**demo_common, header='Sourced Pipeline - Services Revenue Target', value=650000,
                     breaks=[dict(color='#c23934', lowerBound=1000000, upperBound=1000001), dict(color='#ca8501', lowerBound=1000001, upperBound=1000002), dict(color='#00716b', lowerBound=1000002, upperBound=1000003)])],
    )
    return dict(sessions=sessions,etmOwners={sid('001',0):[dict(bu='ERP',names='Demo Owner')]},campaigns=[dict(id=f['parentId'], contacts=120 if ev=='namer' else 80, leads=50 if ev=='namer' else 35, convertedLeads=10 if ev=='namer' else 5) for ev,f in FAMILIES.items()],
        sourcedOpps=[dict(id=sid('006', n), campaignId=CAMPAIGNS[n%8]['id'], acv=25000+n*12500, isWon=n%3==0, saHit=n%2==0) for n in range(12)],
        influence=[dict(ic=CAMPAIGNS[n%8]['id'], oi=sid('006', 30+n//2), pc=None, acv=40000+(n//2)*10000, won=n%4==0, sa=n%3!=0) for n in range(10)], rows=rows,
        sfDashboard=sf_dashboard)
