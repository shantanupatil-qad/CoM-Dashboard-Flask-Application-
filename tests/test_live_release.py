import base64
import json
import unittest
from unittest.mock import Mock
from werkzeug.security import generate_password_hash
from app import create_app
from bigquery import DataError
from test_app import LIVE
class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.env={**LIVE,'APP_USERS_JSON':json.dumps({'viewer':generate_password_hash('test-password',method='pbkdf2:sha256')})}
        self.auth={'Authorization':'Basic '+base64.b64encode(b'viewer:test-password').decode()}
    def test_env_auth_and_readiness(self):
        repo=Mock();repo.get.return_value={}
        client=create_app(self.env,repo).server.test_client()
        self.assertEqual(client.get('/readyz',base_url='https://localhost').status_code,401)
        repo.get.assert_not_called()
        response=client.get('/readyz',base_url='https://localhost',headers=self.auth)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['mode'],'live')
        self.assertEqual(response.headers['Cache-Control'],'no-store')
    def test_failed_source_not_ready(self):
        repo=Mock();repo.get.side_effect=DataError('BigQuery query failed')
        client=create_app(self.env,repo).server.test_client()
        self.assertEqual(client.get('/readyz',base_url='https://localhost',headers=self.auth).status_code,503)
    def test_demo_never_claims_live_ready(self):
        self.assertEqual(create_app({}).server.test_client().get('/readyz').status_code,503)
    def test_malformed_users_fail_startup(self):
        with self.assertRaises(RuntimeError):create_app({**self.env,'APP_USERS_JSON':'{}'})
    def test_local_launcher_collects_live_settings(self):
        from run_live_local import collect_settings
        from werkzeug.security import check_password_hash
        ask=Mock(return_value='local-viewer')
        hidden=Mock(side_effect=['long-local-password','long-local-password'])
        env=collect_settings(LIVE,ask,hidden)
        self.assertEqual(env['DATA_MODE'],'live')
        self.assertTrue(check_password_hash(json.loads(env['APP_USERS_JSON'])['local-viewer'],'long-local-password'))
        self.assertNotIn('APP_USERS_FILE',env)
    def test_local_launcher_collects_bigquery_settings(self):
        from run_live_local import collect_settings
        env=collect_settings({**LIVE,'BQ_PROJECT':'','BQ_DATASET':''},Mock(side_effect=['project','dataset','viewer']),Mock(side_effect=['long-local-password','long-local-password']))
        self.assertEqual((env['BQ_PROJECT'],env['BQ_DATASET']),('project','dataset'))
