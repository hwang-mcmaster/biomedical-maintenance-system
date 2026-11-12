"""No RDS writes. Security boundary tests use mocked account persistence."""
import unittest
from unittest.mock import patch,MagicMock
from uuid import uuid4
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.auth import authorize,password,verify,digest

USER={'id':str(uuid4()),'name':'Fixture','email':'fixture@example.test','role':'technician','is_active':True,'csrf_token':'csrf-fixture'}
class AuthTests(unittest.TestCase):
 def test_signed_out_denied(self):
  with patch('app.auth.authenticate',side_effect=HTTPException(401,'Sign in')):
   client=TestClient(app)
   for path in ['/api/equipment','/api/equipment/export','/api/workflow/tasks','/api/maintenance-schedules','/docs','/openapi.json']:
    self.assertEqual(client.get(path).status_code,401,path)
   self.assertEqual(client.get('/api/health').status_code,200)
 def test_unconfigured_fails_closed(self):
  with patch('app.auth.authenticate',side_effect=RuntimeError('missing table')):
   self.assertEqual(TestClient(app).get('/api/equipment').status_code,503)
 def test_permissions(self):
  for method,path in [('POST','/api/equipment'),('POST','/api/workflow/schedules/preview'),('GET','/api/equipment/export'),('GET','/api/auth/users'),('GET','/api/ready')]:
   with self.assertRaises(HTTPException): authorize(USER,method,path)
  authorize(USER,'GET','/api/equipment')
  authorize(USER|{'role':'coordinator'},'POST','/api/workflow/schedules/preview')
  with self.assertRaises(HTTPException): authorize(USER|{'role':'coordinator'},'POST','/api/auth/users')
 def test_csrf_and_origin(self):
  with patch('app.auth.authenticate',return_value=USER|{'role':'coordinator'}):
   client=TestClient(app)
   self.assertEqual(client.post('/api/workflow/tasks',json={}).status_code,403)
   self.assertEqual(client.post('/api/workflow/tasks',json={},headers={'Origin':'https://evil.test','X-CSRF-Token':'csrf-fixture'}).status_code,403)
   with patch('app.auth.audit'):
    self.assertEqual(client.post('/api/workflow/tasks',json={},headers={'Origin':'http://localhost:5173','X-CSRF-Token':'csrf-fixture'}).status_code,422)
 def test_login_origin(self):
  self.assertEqual(TestClient(app).post('/api/auth/login',json={'email':'a@b.c','password':'x'}).status_code,403)
 def test_password_hash(self):
  value='fixture-long-passphrase-0198';encoded=password(value)
  self.assertNotIn(value,encoded);self.assertTrue(verify(encoded,value));self.assertFalse(verify(encoded,'wrong'))
  self.assertEqual(len(digest(value)),64)
  with self.assertRaises(HTTPException): password('short')
 def test_technician_ownership(self):
  from app.workflow import change_status
  from app.workflow_schemas import StatusInput
  request=MagicMock();request.state.user=USER
  c=MagicMock();c.execute.return_value.fetchone.side_effect=[{'status':'scheduled'},None]
  with patch('app.workflow.get_connection') as connect:
   connect.return_value.__enter__.return_value=c
   # lock() consumes execute but not fetchone.
   with self.assertRaises(HTTPException) as error:
    change_status(uuid4(),StatusInput(status='in_progress',notes='start work'),request)
   self.assertEqual(error.exception.status_code,403)
 def test_logout_revokes(self):
  with patch('app.auth.authenticate',return_value=USER),patch('app.auth.get_connection') as connect:
   client=TestClient(app);client.cookies.set('maintenance_session','fixture-token')
   r=client.post('/api/auth/logout',headers={'Origin':'http://localhost:5173','X-CSRF-Token':'csrf-fixture'})
   self.assertEqual(r.status_code,200)
   sql=connect.return_value.__enter__.return_value.execute.call_args.args[0]
   self.assertIn('DELETE FROM auth_sessions',sql)

 def test_login_issues_secure_opaque_cookie(self):
  user=USER|{'password_hash':password('fixture-long-password-2026')}
  with patch('app.auth.get_connection') as connect:
   c=connect.return_value.__enter__.return_value
   c.execute.return_value.fetchone.side_effect=[{'failures':0},{'failures':0},user]
   r=TestClient(app).post('/api/auth/login',json={'email':user['email'],'password':'fixture-long-password-2026'},headers={'Origin':'http://localhost:5173'})
   self.assertEqual(r.status_code,200,r.text)
   self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('Secure',r.headers['set-cookie'])
   self.assertIn('SameSite=lax',r.headers['set-cookie'])
   self.assertIn('csrf_token',r.json());self.assertNotIn('password_hash',r.json()['user'])
 def test_failed_login_persists_attempts(self):
  with patch('app.auth.get_connection') as connect:
   c=connect.return_value.__enter__.return_value
   c.execute.return_value.fetchone.side_effect=[{'failures':0},{'failures':0},None]
   r=TestClient(app).post('/api/auth/login',json={'email':'absent@example.test','password':'incorrect'},headers={'Origin':'http://localhost:5173'})
   self.assertEqual(r.status_code,401);c.commit.assert_called_once()
 def test_throttle(self):
  with patch('app.auth.get_connection') as connect:
   connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value={'failures':10}
   r=TestClient(app).post('/api/auth/login',json={'email':'a@example.test','password':'incorrect'},headers={'Origin':'http://localhost:5173'})
   self.assertEqual(r.status_code,429)
 def test_last_admin_preserved(self):
  with patch('app.auth.authenticate',return_value=USER|{'role':'admin'}),patch('app.auth.get_connection') as connect:
   c=connect.return_value.__enter__.return_value
   c.execute.return_value.fetchone.side_effect=[USER|{'role':'admin'},{'n':1}]
   r=TestClient(app).put('/api/auth/users/'+USER['id'],json={'role':'coordinator','is_active':True},headers={'Origin':'http://localhost:5173','X-CSRF-Token':'csrf-fixture'})
   self.assertEqual(r.status_code,409,r.text)
 def test_expired_activation_rejected(self):
  with patch('app.auth.get_connection') as connect:
   connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=None
   r=TestClient(app).post('/api/auth/activate',json={'token':'x'*32,'password':'fixture-long-password'},headers={'Origin':'http://localhost:5173'})
   self.assertEqual(r.status_code,400)
