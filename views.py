"""Dash page definitions: port of the original JSX with its inline styles and labels."""
from dash import html, dcc
from config import CAMPAIGNS, CAMPAIGN_BY_ID, FAMILIES, RED, NAVY, STEEL, GREEN, AMBER, PLUM
from model import engaged, fmt_date, money
from campaigns import config, widget_count, widget_engaged

MAIN = dict(maxWidth=1600, margin='0 auto', padding='32px 48px 60px')
CARD = dict(background='white', borderRadius=12, padding=32, boxShadow='0 1px 4px rgba(0,0,0,0.06)')
TH = dict(padding='10px 14px', textAlign='left', fontSize=10, fontWeight=700, color='rgba(255,255,255,0.85)', letterSpacing=.6)
TD = dict(padding='10px 14px', verticalAlign='middle')
TH_SUB = dict(padding='6px 10px', textAlign='center', fontSize=10, fontWeight=700, color='rgba(255,255,255,0.6)', letterSpacing=.4)
BUTTON = dict(padding='6px 14px', background=NAVY, color='white', border='none', borderRadius=6, cursor='pointer', fontSize=11, fontWeight=600, whiteSpace='nowrap')
BACK = dict(background='none', border='none', color=STEEL, cursor='pointer', fontSize=13, marginBottom=18, padding=0)

def div(children=None, className=None, **style):
    return html.Div(children, className=className, style=style)

def action(label, scope, name, key='', style=None, **kwargs):
    return html.Button(label, id={'scope':scope,'action':name,'key':key}, n_clicks=0, style=style or BUTTON, **kwargs)

def section_label(label):
    return div(label, fontSize=10, fontWeight=700, color=NAVY, letterSpacing=1.2, marginBottom=10)

def stat(label, value, color=NAVY, small=False):
    return div([div(value, fontSize=18 if small else 26, fontWeight=700, color=color),
                div(label, fontSize=11, color='#9CA3AF', marginTop=2)])

def spinner(label):
    return div([div(width=28,height=28,borderRadius='50%',border=f'3px solid {RED}33',borderTopColor=RED,animation='spin 0.8s linear infinite',flexShrink=0),
                html.Span(label,style=dict(color='#6B7280',fontSize=13))],display='flex',alignItems='center',gap=14,padding='60px 0',justifyContent='center')

def error_box(message, scope):
    return div([html.P('Failed to load: '+message,style=dict(margin='0 0 10px',color=RED,fontSize=13)),
                action('Retry',scope,'retry',style=dict(padding='8px 20px',background=RED,color='white',border='none',borderRadius=6,cursor='pointer',fontSize=12,fontWeight=600))],
               background='#FEF2F2',borderRadius=12,padding=20,border='1px solid #FECACA',textAlign='center')

def pipeline(title, bg, accent, data):
    return div([section_label(title),
        div([stat('Opportunities',data['count'],accent,True),stat('Net ACV',money(data['value']),accent,True)],display='flex',justifyContent='space-between',marginBottom=16,paddingRight='10%'),
        div([stat('Won',f"{data['wonCount']} · {money(data['wonValue'])}",GREEN,True),stat('SA',f"{data['saCount']} · {money(data['saValue'])}",AMBER,True)],display='flex',justifyContent='space-between',paddingRight='10%')],
        flex=1,background=bg,borderRadius=10,padding=20,className='qad-pipeline')

def event_card(ev, data):
    family=FAMILIES[ev]
    return div([div(family['label'],fontSize=17,fontWeight=700,color=NAVY),div(family['dates'],fontSize=13,color='#9CA3AF',marginBottom=22),
        div([pipeline('SOURCED (Primary Campaign)','#EFF6FF',NAVY,data['sourced']),pipeline('INFLUENCED (Touched, Sourced Elsewhere)','#F5F3FF',PLUM,data['influenced'])],display='flex',gap=20)],
        **{**CARD,'flex':1,'minWidth':420,'className':'qad-event-card'})

def campaign_page(events):
    return [div([event_card('namer',events['namer']),event_card('emea',events['emea'])],display='flex',gap=28,flexWrap='wrap',className='qad-event-grid'),
        html.P("Sourced = Opportunity's Primary Campaign Source is this event. Influenced = this event touched the deal via Campaign Influence, but the deal was primary-sourced elsewhere. The two never overlap. Dollar values reflect Solutions Rev ACV (Net), not the standard Amount field.",
               style=dict(marginTop=24,fontSize=11,color='#9CA3AF',textAlign='center'))]

def pill(campaign, membership):
    if campaign.get('type') == 'grouped':
        n = membership['groupEngaged']; total = membership['groupTotal']
        return div([div(f'{n}/{total}',fontSize=16,fontWeight=700,color=GREEN if n else '#9CA3AF',marginBottom=4),div(campaign['label'],fontSize=11,fontWeight=600,color=NAVY)],background='#F0FDF4' if n else '#F3F4F6',border=f'1px solid {GREEN}55' if n else '1px solid #E5E7EB',borderRadius=10,padding='10px 14px',minWidth=130,textAlign='center')
    yes=membership and engaged(membership['status'],membership['hasResponded'])
    bg,color,border,icon='#F3F4F6','#9CA3AF','1px solid #E5E7EB','–'
    if membership and yes:
        bg,color,border,icon='#F0FDF4',GREEN,f'1px solid {GREEN}55','✓'
    elif membership:
        bg,color,border,icon='#FFFBEB','#B45309','1px solid #FDE68A55','•'
    contents=[div(icon,fontSize=16,fontWeight=700,color=color,marginBottom=4),div(campaign['label']+(' (reg.)' if campaign.get('isParent') else ''),fontSize=11,fontWeight=600,color=NAVY)]
    if membership:
        contents.append(div(fmt_date(membership['createdDate']),fontSize=10,color='#9CA3AF',marginTop=2))
    return html.Div(contents,title=f"{membership['status']} ({fmt_date(membership['createdDate'])})" if membership else 'No membership',
                    style=dict(background=bg,border=border,borderRadius=10,padding='10px 14px',minWidth=130,textAlign='center'))

def cell_icon(membership):
    if membership and 'groupTotal' in membership:
        n,t=membership['groupEngaged'],membership['groupTotal']
        return html.Span(f'{n}/{t}',title=f'{n} of {t} sessions engaged',style=dict(color=GREEN if n else '#9CA3AF',fontWeight=700,fontSize=12))
    yes=membership and engaged(membership['status'],membership['hasResponded'])
    color,char=(GREEN,'✓') if yes else ('#B45309','•') if membership else ('#D1D5DB','–')
    return html.Span(char,title=f"{membership['status']} ({fmt_date(membership['createdDate'])})" if membership else 'No membership',style=dict(color=color,fontWeight=700,fontSize=15))

def timeline(memberships, account=False):
    CAMPAIGN_BY_ID = config()['by_id']
    ordered=sorted(memberships,key=lambda m:m['createdDate'])
    if not ordered:
        return html.P('No campaign membership records found for this account.' if account else 'No campaign membership records found.',style=dict(margin=0,color='#9CA3AF',fontSize=13))
    rows=[]
    for i,m in enumerate(ordered):
        campaign=CAMPAIGN_BY_ID.get(m['campaignId'],{})
        label=campaign.get('label',m['campaignId'])+(' (registration)' if campaign.get('isParent') else '')
        if account:
            label=m['contactName']+' — '+label
        yes=engaged(m['status'],m['hasResponded'])
        rows.append(div([div(position='absolute',left=-25,top=3,width=10,height=10,borderRadius='50%',background=GREEN if yes else '#D1D5DB',border='2px solid white',boxShadow='0 0 0 1px #E5E7EB'),
            div(fmt_date(m['createdDate']),fontSize=12,color='#9CA3AF'),div(label,fontSize=14,fontWeight=600,color=NAVY,marginTop=1),div(m['status'],fontSize=12,color=GREEN if yes else STEEL,marginTop=1)],
            position='relative',paddingBottom=0 if i==len(ordered)-1 else 18))
    return div(rows,borderLeft='2px solid #E5E7EB',paddingLeft=20)

def person_detail(person, scope='person'):
    CAMPAIGNS = config()['widgets']
    memberships=person['memberships']
    by_campaign=widget_memberships(memberships)
    count=widget_count(memberships)
    subtitle=('Contact' if scope=='account' else person['type']+' · '+(person.get('company') or 'No company on file'))+(' · '+person['email'] if person.get('email') else '')
    children=[action('← Back to account' if scope=='account' else '← Back to all people',scope,'back-contact' if scope=='account' else 'back',style=BACK),
        div([div([div(source_anchor(person['name'],'Contact' if scope=='account' else person['type'],person['id']),fontSize=18,fontWeight=700,color=NAVY),div(person.get('title'),fontSize=13,color='#6B7280',marginTop=2) if person.get('title') else None,div(subtitle,fontSize=13,color='#9CA3AF',marginTop=2)]),
            div([div(f'{count} / {len(CAMPAIGNS)}',fontSize=26,fontWeight=700,color=GREEN),div('touchpoints engaged',fontSize=11,color='#9CA3AF')],textAlign='right')],
            display='block',marginBottom=24)]
    for ev in ('namer','emea'):
        camps=[c for c in CAMPAIGNS if c['event']==ev]
        any_membership=any(any(m['campaignId'] in c['campaignIds'] for m in memberships) for c in camps)
        children.append(div([div(FAMILIES[ev]['label'].upper()+(' — NO ACTIVITY' if not any_membership else ''),fontSize=10,fontWeight=700,color=NAVY,letterSpacing=1.2,marginBottom=10),
            div([pill(c,by_campaign.get(c['id'])) for c in camps],display='flex',gap=12,flexWrap='wrap')],marginBottom=26,opacity=1 if any_membership else .45))
    children.extend([div('TIMELINE',fontSize=10,fontWeight=700,color=NAVY,letterSpacing=1.2,margin='8px 0 14px'),timeline(memberships)])
    return div(children,**CARD)

def pagination(scope,page,has_next,has_rows):
    if not has_rows:
        return None
    return div([action('← Prev',scope,'prev',disabled=page==0,style=dict(padding='8px 18px',background='#E5E7EB' if page==0 else 'white',color='#9CA3AF' if page==0 else NAVY,border='1px solid #D1D5DB',borderRadius=8,cursor='default' if page==0 else 'pointer',fontSize=13,fontWeight=600)),
        html.Span(f'Page {page+1}',style=dict(fontSize=13,color='#6B7280')),
        action('Next →',scope,'next',disabled=not has_next,style=dict(padding='8px 18px',background=NAVY if has_next else '#E5E7EB',color='white' if has_next else '#9CA3AF',border='none',borderRadius=8,cursor='pointer' if has_next else 'default',fontSize=13,fontWeight=600))],
        display='flex',justifyContent='center',alignItems='center',gap=16,marginTop=20)

def person_table(people,page,has_next,term):
    CAMPAIGNS = config()['widgets']
    if not people:
        content=div('No people found'+(f' matching "{term}"' if term else '')+'.',padding='48px 24px',textAlign='center',color='#9CA3AF',fontSize=13)
    else:
        header1=[html.Th('Person',rowSpan=2,style=TH),html.Th('Company',rowSpan=2,style=TH)]
        for ev in ('namer','emea'):
            header1.append(html.Th(ev.upper(),colSpan=sum(c['event']==ev for c in CAMPAIGNS),style={**TH,'textAlign':'center','borderLeft':'1px solid rgba(255,255,255,0.15)'}))
        header1.extend([html.Th('Engaged',rowSpan=2,style={**TH,'textAlign':'center'}),html.Th('',rowSpan=2,style=TH)])
        first_ids={next(c['id'] for c in CAMPAIGNS if c['event']==ev) for ev in ('namer','emea')}
        header2=[html.Th(c['abbr'],title=c['label'],style={**TH_SUB,'borderLeft':'1px solid rgba(255,255,255,0.15)' if c['id'] in first_ids else 'none'}) for c in CAMPAIGNS]
        rows=[]
        for i,p in enumerate(people):
            by_campaign=widget_memberships(p['memberships'])
            cells=[html.Td([div(source_anchor(p['name'],p['type'],p['id']),fontWeight=600,color=NAVY),div(p.get('title'),fontSize=11,color='#6B7280') if p.get('title') else None,div(p['type'],fontSize=11,color='#9CA3AF')],style=TD),html.Td(p['company'] or '—',style={**TD,'color':'#6B7280'})]
            cells.extend(html.Td(cell_icon(by_campaign.get(c['id'])),style={**TD,'textAlign':'center','borderLeft':'1px solid #F3F4F6' if c['id'] in first_ids else 'none'}) for c in CAMPAIGNS)
            cells.extend([html.Td(f"{p['engagedCount']}/{len(CAMPAIGNS)}",style={**TD,'textAlign':'center','fontWeight':700,'color':GREEN}),html.Td(action('View Timeline','person','select',p['id']),style=TD)])
            rows.append(html.Tr(cells,style=dict(borderBottom='1px solid #F3F4F6',background='white' if i%2==0 else '#FAFAFA')))
        content=div(html.Table([html.Thead([html.Tr(header1,style=dict(background=NAVY)),html.Tr(header2,style=dict(background=NAVY))]),html.Tbody(rows)],style=dict(width='100%',borderCollapse='collapse',fontSize=13)),overflowX='auto')
    return [div(content,background='white',borderRadius=12,boxShadow='0 1px 4px rgba(0,0,0,0.06)',overflow='hidden'),pagination('person',page,has_next,bool(people))]

def account_table(accounts,page,has_next,term):
    if not accounts:
        content=div('No accounts found'+(f' matching "{term}"' if term else '')+'.',padding='48px 24px',textAlign='center',color='#9CA3AF',fontSize=13)
    else:
        header=[html.Th('Account',style=TH),html.Th('Contacts Touched',style={**TH,'textAlign':'center'}),html.Th('Total Engaged Touchpoints',style={**TH,'textAlign':'center'}),html.Th('Most Recent Activity',style=TH),html.Th('ETM Owners',style=TH),html.Th('',style=TH)]
        rows=[]
        for i,a in enumerate(accounts):
            rows.append(html.Tr([html.Td(source_anchor(a['aname'],'Account',a['aid']),style={**TD,'fontWeight':600,'color':NAVY}),html.Td(a['contactCount'],style={**TD,'textAlign':'center'}),html.Td(a['engagedTouchpoints'],style={**TD,'textAlign':'center','fontWeight':700,'color':GREEN}),
                html.Td(fmt_date(a['latest']),style={**TD,'color':'#6B7280'}),html.Td(etm_line(a.get('etmOwners',[])),style=TD),html.Td(action('View Account','account','select',a['aid']),style=TD)],style=dict(borderBottom='1px solid #F3F4F6',background='white' if i%2==0 else '#FAFAFA')))
        content=html.Table([html.Thead(html.Tr(header,style=dict(background=NAVY))),html.Tbody(rows)],style=dict(width='100%',borderCollapse='collapse',fontSize=13))
    return [div(content,background='white',borderRadius=12,boxShadow='0 1px 4px rgba(0,0,0,0.06)',overflow='hidden'),pagination('account',page,has_next,bool(accounts))]

def account_contacts(account):
    by_contact={}
    for r in account['rows']:
        c=by_contact.setdefault(r['cid'],dict(id=r['cid'],name=r['cname'] or r['name'],email=r['cemail'],title=r.get('ctitle'),memberships=[]))
        c['memberships'].append(dict(campaignId=r['camp'],status=r['st'],hasResponded=r['hr'],createdDate=r['cd']))
    return list(by_contact.values())

def account_detail(account):
    CAMPAIGNS = config()['widgets']
    contacts=account_contacts(account)
    total=sum(engaged(m['status'],m['hasResponded']) for c in contacts for m in c['memberships'])
    children=[action('← Back to all accounts','account','back',style=BACK),
        div([div([div(source_anchor(account['aname'],'Account',account['aid']),fontSize=18,fontWeight=700,color=NAVY),div(f"{len(contacts)} contact{'s' if len(contacts)!=1 else ''} touched by CoM",fontSize=13,color='#9CA3AF',marginTop=2)]),
             div([div(total,fontSize=26,fontWeight=700,color=GREEN),div('total touchpoints engaged',fontSize=11,color='#9CA3AF')],textAlign='right')],display='flex',justifyContent='space-between',alignItems='flex-start',marginBottom=12),
        div([div('ETM OWNERS',fontSize=10,fontWeight=700,color=NAVY,letterSpacing=1.2,marginBottom=6),etm_line(account.get('etmOwners',[]))],marginBottom=24),section_label('CAMPAIGN COVERAGE — DISTINCT CONTACTS ENGAGED')]
    coverage=[]
    for camp in CAMPAIGNS:
        count=sum(widget_engaged(camp,c['memberships']) for c in contacts)
        coverage.append(div([div(count,fontSize=20,fontWeight=700,color=PLUM if count else '#D1D5DB'),div(camp['label']+(' (reg.)' if camp.get('isParent') else ''),fontSize=11,fontWeight=600,color=NAVY)],
            background='#F5F3FF' if count else '#F9FAFB',border=f'1px solid {PLUM}33' if count else '1px solid #E5E7EB',borderRadius=10,padding='10px 16px',minWidth=120,textAlign='center'))
    children.extend([div(coverage,display='flex',gap=12,flexWrap='wrap',marginBottom=28),section_label('CONTACTS')])
    hstyle=dict(padding='8px 12px',textAlign='left',fontSize=10,fontWeight=700,color='#9CA3AF',letterSpacing=.6)
    header=[html.Th('Name',style=hstyle),html.Th('Email',style=hstyle),html.Th('Engaged',style={**hstyle,'textAlign':'center'}),html.Th('',style=dict(padding='8px 12px'))]
    rows=[]
    for i,c in enumerate(contacts):
        count=widget_count(c['memberships'])
        rows.append(html.Tr([html.Td([source_anchor(c['name'],'Contact',c['id']),div(c.get('title'),fontSize=11,color='#9CA3AF',fontWeight=400) if c.get('title') else None],style=dict(padding='10px 12px',fontWeight=600,color=NAVY)),html.Td(c['email'] or '—',style=dict(padding='10px 12px',color='#6B7280')),
            html.Td(f'{count}/{len(CAMPAIGNS)}',style=dict(padding='10px 12px',textAlign='center',fontWeight=700,color=GREEN)),html.Td(action('View Timeline','account','contact',c['id']),style=dict(padding='10px 12px',textAlign='right'))],style=dict(borderTop='1px solid #F3F4F6',background='white' if i%2==0 else '#FAFAFA')))
    children.append(div(html.Table([html.Thead(html.Tr(header,style=dict(background='#F9FAFB'))),html.Tbody(rows)],style=dict(width='100%',borderCollapse='collapse',fontSize=13)),marginBottom=28))
    merged=[{**m,'contactName':c['name']} for c in contacts for m in c['memberships']]
    children.extend([div('ACCOUNT TIMELINE — ALL CONTACTS MERGED',fontSize=10,fontWeight=700,color=NAVY,letterSpacing=1.2,margin='8px 0 14px'),timeline(merged,True)])
    return div(children,**CARD)

def filter_controls(scope):
    return html.Div([dcc.Input(id=scope+'-input',value='',type='text',debounce=False,n_submit=0,maxLength=120,placeholder='Filter by name, email, or company...' if scope=='person' else 'Filter by account name...',
                      style=dict(flex=1,padding='10px 14px',borderRadius=8,border='1px solid #D1D5DB',fontSize=14,outline='none')),
        action('Filter',scope,'filter',style=dict(padding='10px 22px',background=RED,color='white',border='none',borderRadius=8,cursor='pointer',fontWeight=600,fontSize=13,whiteSpace='nowrap')),
        html.Div(action('Clear',scope,'clear',style=dict(padding='10px 18px',background='white',color=STEEL,border='1px solid #D1D5DB',borderRadius=8,cursor='pointer',fontSize=13)),id=scope+'-clear',style=dict(display='none'))],
        id=scope+'-filter-wrap',style=dict(display='flex',gap=10,marginBottom=20,maxWidth=500))

def nav_style(active):
    return dict(padding='12px 20px',borderRadius='8px 8px 0 0',border='none',cursor='pointer',fontSize=13,fontWeight=600,
                background='#F5F6F7' if active else 'rgba(255,255,255,0.08)',color=NAVY if active else 'rgba(255,255,255,0.75)')

def layout():
    labels=[('campaign','Campaign Performance'),('person','Person Engagement'),('account','Account Engagement')]
    tabs=div([html.Button(label,id='nav-'+key,n_clicks=0,style=nav_style(key=='campaign'),className='qad-tab') for key,label in labels],display='flex',gap=4,className='qad-tabs')
    header=html.Header(div([html.Img(src='/assets/qad-redzone-logo.png',alt='QAD | Redzone',style=dict(height=28,marginBottom=14,display='block')),
        div('QAD MARKETING OPERATIONS',fontSize=11,fontWeight=700,color=RED,letterSpacing=.5,marginBottom=4,className='qad-eyebrow'),
        html.H1('Champions of Manufacturing — FY27',style=dict(margin=0,fontSize=22,fontWeight=700,color='white')),
        html.P('Campaign performance, person engagement, and account rollups across both FY27 events',style=dict(margin='4px 0 20px',fontSize=13,color='rgba(255,255,255,0.6)')),
        div([div('LIVE OPERATIONS CONSOLE',className='qad-status-label'),div(className='qad-status-dot'),tabs],className='qad-header-bottom')],maxWidth=1600,margin='0 auto'),style=dict(background=NAVY,padding='24px 48px 0'),className='qad-header')
    panels=[]
    for scope,_ in labels:
        contents=[] if scope=='campaign' else [filter_controls(scope)]
        label='Pulling live data from Salesforce...' if scope=='campaign' else 'Loading people...' if scope=='person' else 'Loading accounts...'
        contents.append(dcc.Loading(html.Div(id=scope+'-content'),custom_spinner=spinner(label),delay_show=0))
        panels.append(html.Div(html.Main(contents,style=MAIN,className='qad-main'),id=scope+'-panel',style=dict(display='block' if scope=='campaign' else 'none'),className='qad-panel'))
    return div([dcc.Store(id='active-tab',data='campaign'),dcc.Interval(id='live-poll',interval=15*1000,n_intervals=0)]+[dcc.Store(id=key+'-state',data=dict(page=0,filter='',selected=None,contact=None,revision=0)) for key,_ in labels]+[header]+panels,
        fontFamily='IBM Plex Sans, system-ui, sans-serif',background='#F5F6F7',minHeight='100vh',className='qad-shell')

def source_anchor(label, kind, id):
    from salesforce import check_id
    check_id(id)
    return html.A(label, href=f'https://qad.lightning.force.com/lightning/r/{kind}/{id}/view', target='_blank', rel='noreferrer', title=f'{kind} record', style=dict(color='inherit', borderBottom='1px dotted #9CA3AF'))

def widget_memberships(memberships):
    by={m['campaignId']:m for m in memberships}
    for w in config()['widgets']:
        if w['type']=='grouped':
            n=sum(id in by and engaged(by[id]['status'],by[id]['hasResponded']) for id in w['campaignIds'])
            by[w['id']]=dict(groupEngaged=n,groupTotal=len(w['campaignIds']))
    return by

def etm_line(owners):
    if not owners: return html.Span('—',style=dict(color='#D1D5DB'))
    children=[]
    for i,o in enumerate(owners):
        if i: children.append(' · ')
        children.extend([html.Strong(o['bu']+':',style=dict(color=STEEL)),' '+o['names']])
    return html.Span(children,style=dict(fontSize=11,color='#6B7280'))
