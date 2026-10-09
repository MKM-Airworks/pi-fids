import json
import unittest
from test_lan import LanTests
from pifids.security import Security, write_private
from pifids.lan import manager_handler

class UsersAuditTests(LanTests):
    def cookie(self,name='test',password='synthetic-test-password'):
        with self.request(self.manager,'/api/login',{'username':name,'password':password}) as response:
            return {'Cookie':response.headers['Set-Cookie'].split(';')[0]}

    def test_role_enforcement_and_revoke(self):
        admin=self.cookie()
        with self.request(self.manager,'/api/users',{'airport':'ROR','action':'create','username':'op','password':'synthetic-operator-password','role':'operator'},admin):pass
        operator=self.cookie('op','synthetic-operator-password')
        for endpoint in ('/api/users','/api/audit?airport=ROR','/api/audit-settings?airport=ROR','/api/clock?airport=ROR'):
            self.denied(403,self.manager,endpoint,headers=operator)
        for endpoint in ('/api/terminals','/api/terminals/delete','/api/profiles','/api/assets','/api/airport-names','/api/clock','/api/display','/api/users','/api/upstream/mode','/api/audit-settings'):
            self.denied(403,self.manager,endpoint,{'airport':'ROR'},operator)
        from pifids import registry
        registry.save_terminal(self.store,{'airport':'ROR','displayId':'counter-02','name':'Synthetic counter','usage':'signage'})
        registry.save_profile(self.store,{'airport':'ROR','name':'Synthetic image','mode':'counter','airline':'Synthetic airline','logo':'','image':''})
        with self.request(self.manager,'/api/signage',{'airport':'ROR','displayId':'counter-02','profileName':'Synthetic image'},operator):pass
        self.assertEqual(self.store.display('ROR','counter-02')['mode'],'counter')
        with self.request(self.manager,'/api/flights',{'airport':'ROR','flightNumber':'OP123','destination':'Guam','time':'12:00'},operator):pass
        with self.request(self.manager,'/api/publish',{'airport':'ROR'},operator):pass
        with self.request(self.manager,'/api/audit?airport=ROR',headers=admin) as r:logs=json.load(r)
        self.assertEqual([x['action'] for x in logs[:2]],['flight.publish','flight.create'])
        self.assertEqual(logs[1]['actor'],'op');self.assertEqual(logs[1]['source'],'Pi-FIDS')
        self.assertNotIn('synthetic-operator-password',json.dumps(logs));self.assertNotIn('passwordHash',json.dumps(logs))
        with self.request(self.manager,'/api/users',{'airport':'ROR','action':'update','username':'op','role':'operator','active':False},admin):pass
        self.denied(401,self.manager,'/api/state?airport=ROR',headers=operator)
        self.assertEqual(Security(self.config_path).listing()[0]['active'],False)
        self.denied(400,self.manager,'/api/users',{'airport':'ROR','action':'delete','username':'test'},admin)
        self.assertTrue(self.security.session(admin))

    def test_atomic_audit_conflict_and_pagination(self):
        admin=self.cookie()
        with self.request(self.manager,'/api/flights',{'airport':'ROR','flightNumber':'EDIT','destination':'Guam','time':'12:00','actor':'spoof'},admin):pass
        state=self.store.read('ROR');flight=state['draft'][0]
        with self.request(self.manager,'/api/flights/update',{**flight,'destination':'Tokyo','expectedDraftRevision':state['draftRevision']},admin):pass
        self.denied(409,self.manager,'/api/flights/delete',{'airport':'ROR','id':flight['id'],'expectedDraftRevision':state['draftRevision']},admin)
        self.assertEqual(len(self.store.audit_records('ROR')),2)
        latest=self.store.audit_records('ROR')[0];self.assertEqual(latest['actor'],'test');self.assertEqual(latest['before']['destination'],'Guam');self.assertEqual(latest['after']['destination'],'Tokyo')
        with self.request(self.manager,'/api/flights/delete',{'airport':'ROR','id':flight['id'],'expectedDraftRevision':state['draftRevision']+1},admin):pass
        self.assertIsNone(self.store.audit_records('ROR')[0]['after'])
        with self.request(self.manager,'/api/audit?airport=ROR&beforeId='+str(latest['id']),headers=admin) as r:self.assertEqual(len(json.load(r)),1)
        self.denied(403,self.manager,'/api/audit?airport=SHI',headers=admin)
        self.denied(400,self.manager,'/api/audit?airport=ROR&beforeId=oops',headers=admin)

    def test_initial_admin_once_and_password_reset(self):
        self.security.users_path.unlink()
        config=self.config.copy();config['username']='unused-lan-only';write_private(self.config_path,config)
        security=Security(self.config_path);manager=self.start(manager_handler(self.store,security))
        with self.request(manager,'/api/session') as r:self.assertTrue(json.load(r)['setupRequired'])
        self.denied(403,manager,'/api/setup-admin',{'username':'admin','password':'synthetic-admin-password'},{'Origin':'http://untrusted.example'})
        with self.request(manager,'/api/setup-admin',{'username':'admin','password':'synthetic-admin-password'}) as r:cookie={'Cookie':r.headers['Set-Cookie'].split(';')[0]}
        self.denied(400,manager,'/api/setup-admin',{'username':'other','password':'synthetic-admin-password'})
        self.assertEqual(security.terminal(self.credentials()),('ROR','gate-01'))
        with self.request(manager,'/api/users',{'airport':'ROR','action':'reset','username':'admin','password':'synthetic-new-password'},cookie):pass
        self.denied(401,manager,'/api/state?airport=ROR',headers=cookie)
        self.assertIsNotNone(Security(self.config_path).login('admin','synthetic-new-password','new-peer'))

if __name__=='__main__':unittest.main()
