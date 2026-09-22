import base64
import json
import tempfile
import unittest
from unittest.mock import Mock
from werkzeug.security import generate_password_hash
from app import create_app, initial_state, transition, render_view
from config import CAMPAIGNS
from demo import demo_data
from model import event_stats, people, accounts, page_items, engaged, money
from bigquery import Repository, BigQuery, DataError
import views
LIVE = dict(DATA_MODE='live',BQ_PROJECT='test-project',BQ_DATASET='dashboard')
def encoded(value):
    from plotly.utils import PlotlyJSONEncoder
    return json.dumps(value,cls=PlotlyJSONEncoder)
class Tests(unittest.TestCase):
    def test_hierarchy(self):
        result=event_stats(demo_data())
        self.assertEqual(result['namer']['totalMembers'],160)
        self.assertEqual(result['emea']['totalMembers'],110)
    def test_influence(self):
        data=demo_data(); n,e=CAMPAIGNS[0]['id'],CAMPAIGNS[5]['id']
        row=dict(ic=n,oi='006000000000000001',pc=e,acv=10.25,won=True,sa=False)
        data['influence']=[row,row,{**row,'oi':'006000000000000002','pc':n}]
        result=event_stats(data)['namer']['influenced']
        self.assertEqual((result['count'],result['value']),(1,10.25))
    def test_paging(self):
        data=demo_data()
        self.assertEqual(len(people(data)),48)
        self.assertEqual(len(accounts(data)),4)
        rows,more=page_items(people(data),0)
        self.assertEqual((len(rows),more),(20,True))
        self.assertEqual(len(page_items(people(data),2)[0]),8)
        self.assertFalse(page_items(people(data),0,"' OR Name LIKE '%'",('name',))[0])
        self.assertTrue(all(r['cid'] for a in accounts(data) for r in a['rows']))
    def test_rules(self):
        self.assertTrue(engaged('REGISTERED',False))
        self.assertTrue(engaged('Invited',True))
        self.assertFalse(engaged(' registered ',False))
        self.assertEqual(money(1234.5),'$1,235')
        self.assertEqual(money(None),'$0')
    def test_navigation(self):
        state,term=transition(initial_state(),'filter',term=' Alex ')
        self.assertEqual((state['filter'],state['page']),('Alex',0))
        state,_=transition(state,'select','003000000000000001')
        state,_=transition(state,'back'); self.assertIsNone(state['selected'])
        state,term=transition(state,'clear'); self.assertEqual((term,state['filter']),('',''))
        with self.assertRaises(DataError): transition(state,'select','<script>')
    def test_details(self):
        repo=Repository('demo'); p=people(repo.get())[0]
        state={**initial_state(),'selected':p['id']}
        self.assertIn('TIMELINE',encoded(render_view('person',state,repo)))
        a=accounts(repo.get())[0]; state['selected']=a['aid']
        self.assertIn('CAMPAIGN COVERAGE',encoded(render_view('account',state,repo)))
        state['contact']=a['rows'][0]['cid']
        self.assertIn('Back to account',encoded(render_view('account',state,repo)))
        state['contact']='003999999999999999'
        with self.assertRaises(DataError): render_view('account',state,repo)
    def test_bigquery_query(self):
        job=Mock(); job.result.return_value=[{'id':'a'},{'id':'b'}]
        client=Mock(); client.query.return_value=job
        adapter=BigQuery(LIVE,client)
        self.assertEqual(len(adapter.query('SELECT id FROM `test-project.dashboard.members`')),2)
        client.query.assert_called_once()
    def test_live_config(self):
        with self.assertRaises(DataError): BigQuery({**LIVE,'BQ_PROJECT':'bad project'},Mock())
    def test_cache(self):
        loader=Mock(side_effect=[demo_data(),DataError('failed')]); repo=Repository('live',loader=loader)
        first=repo.get(); self.assertIs(repo.get(),first); self.assertEqual(loader.call_count,1)
        repo.expires=0
        with self.assertRaises(DataError): repo.get()
    def test_layout(self):
        client=create_app({}).server.test_client(); response=client.get('/_dash-layout')
        self.assertEqual(response.status_code,200)
        for label in ('Campaign Performance','Person Engagement','Account Engagement'): self.assertIn(label,response.get_data(as_text=True))
        self.assertNotIn('Heatmap',response.get_data(as_text=True))
        self.assertEqual(views.MAIN,dict(maxWidth=1600,margin='0 auto',padding='32px 48px 60px'))
        cards=views.campaign_page(event_stats(demo_data()))[0]
        self.assertEqual(cards.style['gap'],28)
        self.assertEqual(cards.children[0].children[-1].style,dict(display='flex',gap=20))
    def test_campaign_callback(self):
        client=create_app({}).server.test_client()
        r=client.post('/_dash-update-component',json=dict(output='campaign-content.children',outputs=dict(id='campaign-content',property='children'),inputs=[dict(id='active-tab',property='data',value='campaign'),dict(id='campaign-state',property='data',value=initial_state())],state=[],changedPropIds=['active-tab.data']))
        self.assertEqual(r.status_code,200); self.assertIn('Net ACV',r.get_data(as_text=True)); self.assertNotIn('Total members',r.get_data(as_text=True))
    def test_pattern_callback(self):
        client=create_app({}).server.test_client(); button=dict(scope='person',action='select',key=people(demo_data())[0]['id'])
        r=client.post('/_dash-update-component',json=dict(output='..person-state.data...person-input.value..',outputs=[dict(id='person-state',property='data'),dict(id='person-input',property='value')],inputs=[[dict(id=button,property='n_clicks',value=1)],dict(id='person-input',property='n_submit',value=0)],state=[dict(id='person-state',property='data',value=initial_state()),dict(id='person-input',property='value',value='')],changedPropIds=[json.dumps(button,sort_keys=True,separators=(',',':'))+'.n_clicks']))
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['response']['person-state']['data']['selected'],button['key'])
    def test_cross_site(self):
        client=create_app({}).server.test_client()
        self.assertEqual(client.post('/_dash-update-component',headers={'Origin':'https://evil.example'}).status_code,403)
    def test_auth(self):
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            json.dump({'reviewer':generate_password_hash('test-only',method='pbkdf2:sha256')},f); f.flush()
            client=create_app({**LIVE,'APP_USERS_FILE':f.name},Repository('demo')).server.test_client()
            self.assertEqual(client.get('/_dash-layout').status_code,403)
            self.assertEqual(client.get('/_dash-layout',base_url='https://localhost').status_code,401)
            self.assertEqual(client.post('/_dash-update-component',base_url='https://localhost').status_code,401)
            auth='Basic '+base64.b64encode(b'reviewer:test-only').decode()
            r=client.get('/_dash-layout',base_url='https://localhost',headers={'Authorization':auth})
            self.assertEqual(r.status_code,200); self.assertEqual(r.headers['Cache-Control'],'no-store')
if __name__=='__main__': unittest.main()
