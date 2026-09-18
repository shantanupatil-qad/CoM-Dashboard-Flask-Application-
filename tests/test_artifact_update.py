import unittest
from unittest.mock import Mock
from campaigns import build_config,CURRENT,widget_count,etm_owners
from app import render_view,initial_state
from bigquery import Repository,BigQuery
from model import event_stats
from views import widget_memberships,cell_icon
from test_app import LIVE,encoded

class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.sessions=[dict(Id='701000000000000001',Name='#CoM TH Session-AI'),dict(Id='701000000000000002',Name='#CoM TH Session-Planning'),dict(Id='701000000000000003',Name='#CoM BR Session-ERP')]
        self.cfg=build_config(self.sessions)
        self.token=CURRENT.set(self.cfg)
    def tearDown(self): CURRENT.reset(self.token)
    def test_discovery_and_group_count(self):
        self.assertEqual(len(self.cfg['widgets']),11)
        self.assertEqual(len(self.cfg['campaigns']),12)
        self.assertEqual(self.cfg['by_id'][self.sessions[0]['Id']]['label'],'AI')
        members=[dict(campaignId=s['Id'],status='Registered',hasResponded=False,createdDate='2026-09-01') for s in self.sessions[:2]]
        self.assertEqual(widget_count(members),1)
        self.assertEqual(cell_icon(widget_memberships(members)['theater']).children,'2/2')
    def test_session_pipeline_and_exclusion(self):
        data=dict(campaigns=[],sourcedOpps=[dict(campaignId=self.sessions[0]['Id'],acv=20,isWon=True,saHit=False)],influence=[dict(ic=self.sessions[1]['Id'],oi='006000000000000001',pc=self.sessions[0]['Id'],acv=20,won=True,sa=False)])
        stats=event_stats(data)['namer']
        self.assertEqual(stats['sourced']['count'],1)
        self.assertEqual(stats['influenced']['count'],0)
    def test_territory_rules(self):
        assoc=[dict(ObjectId='A',Territory2Id='T',Territory2=dict(Territory2Type=dict(MasterLabel='Named Accounts'),Territory2Model=dict(State='Active')))]
        owners=[dict(Territory2Id='T',RoleInTerritory2='Channel Manager',User=dict(Name='Owner'))]*2
        self.assertEqual(etm_owners('A','Licensed EU',assoc,owners),[dict(bu='ERP',names='Owner')])
        self.assertEqual(etm_owners('A','Other',assoc,owners),[])
        assoc[0]['Territory2']['Territory2Model']['State']='Planning'
        self.assertEqual(etm_owners('A','Remote EU',assoc,owners),[])
    def test_render_features_and_context_reset(self):
        repo=Repository('demo')
        person=encoded(render_view('person',initial_state(),repo))
        self.assertNotIn('HEATMAP',person)
        self.assertIn('Operations Director',person)
        self.assertNotIn('lightning.force.com',person)
        self.assertIn('Theater Session',person)
        account=encoded(render_view('account',initial_state(),repo))
        self.assertIn('ETM Owners',account)
        self.assertIn('Demo Owner',account)
        self.assertIs(CURRENT.get(),self.cfg)
    def test_adapter_discovers_before_member_query(self):
        sf=BigQuery(LIVE,Mock())
        sf.query=Mock(side_effect=[self.sessions,[],[],[]])
        data=sf.load()
        self.assertEqual(len(data['sessions']),3)
        queries=[call.args[0] for call in sf.query.call_args_list]
        self.assertIn('parent_id',queries[0])
        self.assertIn(self.sessions[0]['Id'],queries[-1])
        self.assertIn('members',queries[-1])
        self.assertNotIn('HierarchyNumber',' '.join(queries))
