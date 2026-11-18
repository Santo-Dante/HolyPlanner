import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from holy_planner.backend import Api
from holy_planner.web_app import PlannerServer


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.server=PlannerServer(('127.0.0.1',0),Api(Path(self.temp.name)/'planner.db'),'test-pair-code')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.cookie=''

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self,path,payload=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        request_headers={'Content-Type':'application/json','X-Holy-Planner':'1','Cookie':self.cookie}
        request_headers.update(headers or {})
        conn.request('POST' if payload is not None else 'GET',path,json.dumps(payload) if payload is not None else None,request_headers)
        response=conn.getresponse()
        body=response.read()
        result=(response.status,body,dict(response.getheaders()))
        conn.close()
        return result

    def login(self):
        status,body,headers=self.request('/api/login',{'code':'test-pair-code'})
        self.assertEqual(status,200)
        self.cookie=headers['Set-Cookie'].split(';')[0]

    def test_api_requires_pairing_and_persists_shared_data(self):
        self.assertEqual(self.request('/api/call',{'method':'snapshot'})[0],401)
        self.assertEqual(self.request('/api/login',{'code':'bad'})[0],401)
        self.login()
        status,body,_=self.request('/api/call',{'method':'save','args':['tasks',{'title':'Pelo celular'}]})
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)['ok'])
        self.assertEqual(self.server.api.snapshot()['tasks'][0]['title'],'Pelo celular')

    def test_private_methods_csrf_and_files_are_blocked(self):
        self.login()
        self.assertEqual(self.request('/api/call',{'method':'_database'})[0],403)
        self.assertEqual(self.request('/api/call',{'method':'snapshot'}, {'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/call',{'method':'snapshot'}, {'X-Holy-Planner':''})[0],403)
        for path in ('/../credentials.json','/credentials.json','/../backend.py','/%2e%2e/credentials.json'):
            self.assertEqual(self.request(path)[0],404)

    def test_workouts_shared_between_browser_and_desktop(self):
        from datetime import date
        self.login()
        payload=dict(title='Cardio pelo celular',day=date.today().isoformat(),cardio=[dict(name='Bicicleta',minutes=25)])
        result=json.loads(self.request('/api/call',{'method':'save_workout','args':[payload]})[1])
        self.assertTrue(result['ok'])
        self.assertEqual(self.server.api.workouts_snapshot()['summary']['cardio_minutes'],25)
        snap=json.loads(self.request('/api/call',{'method':'workouts_snapshot'})[1])
        self.assertEqual(snap['sessions'][0]['title'],payload['title'])
        self.assertTrue(json.loads(self.request('/api/call',{'method':'delete_workout','args':[result['id']]})[1])['ok'])
        self.assertEqual(self.server.api.workouts_snapshot()['sessions'],[])
        for asset in ('/workouts.js','/workouts.css'):
            self.assertEqual(self.request(asset)[0],200)

    def test_invalid_calls_and_rate_limit(self):
        self.login()
        self.assertEqual(self.request('/api/call',{'method':[]})[0],400)
        self.assertEqual(self.request('/api/call',{'method':'snapshot','args':{}})[0],400)
        for _ in range(10):self.request('/api/login',{'code':'bad'})
        self.assertEqual(self.request('/api/login',{'code':'bad'})[0],429)

    def test_shell_manifest_and_download(self):
        self.assertEqual(self.request('/')[0],200)
        self.assertIn(b'data-runtime="web"',self.request('/')[1])
        self.assertEqual(self.request('/sw.js')[2]['Content-Type'],'text/javascript')
        manifest=json.loads(self.request('/manifest.webmanifest')[1])
        self.assertEqual(manifest['display'],'standalone')
        for icon in manifest['icons']:self.assertEqual(self.request(icon['src'])[0],200)
        self.login()
        result=json.loads(self.request('/api/call',{'method':'backup'})[1])
        import base64
        self.assertTrue(base64.b64decode(result['download']['data']).startswith(b'SQLite format 3'))
