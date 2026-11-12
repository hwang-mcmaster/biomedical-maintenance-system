"""Database-backed accounts and opaque sessions. Fail closed when setup is missing."""
import logging
import hashlib
import os
import secrets
from datetime import datetime,timedelta,timezone
from uuid import UUID
from fastapi import APIRouter,HTTPException,Request,Response
from pydantic import BaseModel,ConfigDict,Field
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from .database import get_connection

router=APIRouter(prefix='/api/auth',tags=['Accounts'])
hasher=PasswordHasher();DUMMY=hasher.hash(secrets.token_urlsafe(32))
COOKIE='maintenance_session'
ROLES=('admin','coordinator','technician')

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def origins(): return set(os.getenv('APP_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','))
def check_origin(request):
    if request.headers.get('origin') not in origins(): raise HTTPException(403,'Request origin is not allowed.')
def password(value):
    if len(value)<15 or len(value)>128: raise HTTPException(422,'Use a password of 15–128 characters.')
    if value.casefold() in {'passwordpassword','123456789012345','changemepassword'}: raise HTTPException(422,'Choose a less common password.')
    return hasher.hash(value)
def public(user): return {k:user[k] for k in ('id','email','name','role','is_active')}
def authenticate(token):
    if not token: raise HTTPException(401,'Sign in to continue.')
    with get_connection() as c:
        row=c.execute("SELECT u.*,s.csrf_token FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id WHERE s.token_hash=%s AND u.is_active AND u.password_hash IS NOT NULL AND s.expires_at>now() AND s.last_seen>now()-interval '30 minutes'",(digest(token),)).fetchone()
        if not row: raise HTTPException(401,'Your session expired. Sign in again.')
        c.execute('UPDATE auth_sessions SET last_seen=now() WHERE token_hash=%s',(digest(token),))
        return row

def authorize(user,method,path):
    if path.startswith('/api/auth/users') or path=='/api/auth/audit' or path in ('/docs','/redoc','/openapi.json','/api/ready') or path.startswith('/api/scheduling/'):
        if user['role']!='admin': raise HTTPException(403,'Administrator access required.')
    if user['role']=='technician':
        if path=='/api/equipment/export': raise HTTPException(403,'Export requires a coordinator.')
        if method not in ('GET','HEAD') and not path.startswith('/api/auth/') and not (path.startswith('/api/workflow/tasks/') and path.endswith('/status')):
            raise HTTPException(403,'This action requires a maintenance coordinator.')

def audit(user_id,action):
    with get_connection() as c: c.execute('INSERT INTO auth_audit(user_id,action) VALUES (%s,%s)',(user_id,action))

async def access_control(request,call_next):
    path=request.url.path
    if request.method=='OPTIONS' or path=='/api/health': return await call_next(request)
    try:
        if path not in ('/api/auth/login','/api/auth/activate'):
            user=await run_in_threadpool(authenticate,request.cookies.get(COOKIE));request.state.user=user
            authorize(user,request.method,path)
            if request.method not in ('GET','HEAD'):
                check_origin(request)
                if not secrets.compare_digest(request.headers.get('x-csrf-token',''),user['csrf_token']): raise HTTPException(403,'Security token missing. Reload and retry.')
        else: check_origin(request)
    except HTTPException as e: return JSONResponse({'detail':e.detail},status_code=e.status_code)
    except Exception:
        return JSONResponse({'detail':'Account storage is unavailable. Ask the administrator to complete the authentication database setup.'},status_code=503)
    if request.method not in ('GET','HEAD') and not path.startswith('/api/auth/'):
        try: await run_in_threadpool(audit,request.state.user['id'],f'Attempt {request.method} {path}')
        except Exception: return JSONResponse({'detail':'Audit storage unavailable. No action was performed.'},status_code=503)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    if request.method not in ('GET','HEAD') and not path.startswith('/api/auth/'):
        try: await run_in_threadpool(audit,request.state.user['id'],f'Result {response.status_code}: {request.method} {path}')
        except Exception: logging.getLogger(__name__).error('Could not record action result; pre-action audit remains available.')
    return response

class Input(BaseModel): model_config=ConfigDict(extra='forbid')
class Login(Input):
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=1,max_length=128)
class Activate(Input):
    token: str=Field(min_length=20,max_length=200)
    password: str=Field(min_length=15,max_length=128)
class Change(Input):
    current_password: str=Field(max_length=128)
    new_password: str=Field(min_length=15,max_length=128)
class UserInput(Input):
    email: str=Field(min_length=3,max_length=254)
    name: str=Field(min_length=1,max_length=100)
    role: str
    technician_id: UUID|None=None
class UserEdit(Input):
    role: str
    is_active: bool
    technician_id: UUID|None=None

def verify(encoded,plain):
    try: return hasher.verify(encoded or DUMMY,plain)
    except (VerificationError,InvalidHashError): return False

@router.post('/login')
def login(body:Login,request:Request,response:Response):
    email=body.email.strip().casefold();ip=request.client.host if request.client else 'unknown'
    # Separate account and source buckets prevent trivial IP/account rotation.
    buckets=[digest('account:'+email),digest('source:'+ip)]
    with get_connection() as c:
        c.execute('SELECT pg_advisory_xact_lock(74102027)')
        for bucket in buckets:
            c.execute('INSERT INTO auth_attempts(bucket) VALUES (%s) ON CONFLICT DO NOTHING',(bucket,))
            c.execute("UPDATE auth_attempts SET failures=0,window_start=now() WHERE bucket=%s AND window_start<now()-interval '15 minutes'",(bucket,))
            attempts=c.execute('SELECT failures FROM auth_attempts WHERE bucket=%s',(bucket,)).fetchone()['failures']
            if attempts>=10: raise HTTPException(429,'Too many sign-in attempts. Try again later.')
        user=c.execute('SELECT * FROM auth_users WHERE email=%s',(email,)).fetchone()
        valid=verify(user['password_hash'] if user else None,body.password)
        if not user or not valid or not user['is_active'] or not user['password_hash']:
            for bucket in buckets: c.execute('UPDATE auth_attempts SET failures=failures+1 WHERE bucket=%s',(bucket,))
            c.execute("INSERT INTO auth_audit(action) VALUES ('Failed sign-in')")
            c.commit() # Persist throttling before returning an authentication error.
            raise HTTPException(401,'Invalid email or password.')
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        c.execute("INSERT INTO auth_sessions(token_hash,user_id,csrf_token,expires_at) VALUES (%s,%s,%s,now()+interval '8 hours')",(digest(token),user['id'],csrf))
        c.execute('UPDATE auth_attempts SET failures=0 WHERE bucket=%s',(buckets[0],))
        c.execute("INSERT INTO auth_audit(user_id,action) VALUES (%s,'Signed in')",(user['id'],))
    response.set_cookie(COOKIE,token,httponly=True,secure=os.getenv('AUTH_COOKIE_SECURE','true').lower()!='false',samesite='lax',max_age=28800,path='/')
    response.headers['Cache-Control']='no-store'
    return {'user':public(user),'csrf_token':csrf}

@router.get('/me')
def me(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    return {'user':public(request.state.user),'csrf_token':request.state.user['csrf_token']}

@router.post('/logout')
def logout(request:Request,response:Response):
    with get_connection() as c:
        c.execute("INSERT INTO auth_audit(user_id,action) VALUES (%s,'Signed out')",(request.state.user['id'],))
        c.execute('DELETE FROM auth_sessions WHERE token_hash=%s',(digest(request.cookies[COOKIE]),))
    response.delete_cookie(COOKIE,path='/');return {'message':'Signed out.'}

@router.post('/change-password')
def change(body:Change,request:Request,response:Response):
    if not verify(request.state.user['password_hash'],body.current_password): raise HTTPException(400,'Current password is incorrect.')
    encoded=password(body.new_password)
    with get_connection() as c:
        c.execute('UPDATE auth_users SET password_hash=%s WHERE id=%s',(encoded,request.state.user['id']))
        c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(request.state.user['id'],))
        c.execute("INSERT INTO auth_audit(user_id,action) VALUES (%s,'Changed password and revoked sessions')",(request.state.user['id'],))
    response.delete_cookie(COOKIE,path='/');return {'message':'Password changed. Sign in again.'}

@router.post('/activate')
def activate(body:Activate):
    with get_connection() as c:
        row=c.execute('DELETE FROM auth_tokens WHERE token_hash=%s AND expires_at>now() RETURNING user_id',(digest(body.token),)).fetchone()
        if not row: raise HTTPException(400,'This activation/reset link is invalid or expired.')
        encoded=password(body.password)
        c.execute('UPDATE auth_users SET password_hash=%s WHERE id=%s AND is_active',(encoded,row['user_id']))
        c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(row['user_id'],))
        c.execute("INSERT INTO auth_audit(user_id,action) VALUES (%s,'Set password using one-time token')",(row['user_id'],))
    return {'message':'Password set. Sign in to continue.'}

def link_technician(c,user_id,role,technician_id):
    c.execute('UPDATE workflow_technicians SET user_id=NULL WHERE user_id=%s',(user_id,))
    if role=='technician':
        if not technician_id: raise HTTPException(422,'Select a technician record for this role.')
        row=c.execute('SELECT user_id FROM workflow_technicians WHERE id=%s FOR UPDATE',(technician_id,)).fetchone()
        if not row: raise HTTPException(404,'Technician not found.')
        if row['user_id']: raise HTTPException(409,'Technician already has an account.')
        c.execute('UPDATE workflow_technicians SET user_id=%s WHERE id=%s',(user_id,technician_id))

def issue_token(c,user_id):
    token=secrets.token_urlsafe(32)
    c.execute('DELETE FROM auth_tokens WHERE user_id=%s',(user_id,))
    c.execute("INSERT INTO auth_tokens VALUES (%s,%s,now()+interval '1 hour')",(digest(token),user_id))
    return {'activation_token':token,'expires_in_minutes':60}

@router.get('/users')
def users():
    with get_connection() as c: return c.execute('SELECT u.id,u.email,u.name,u.role,u.is_active,t.id AS technician_id FROM auth_users u LEFT JOIN workflow_technicians t ON t.user_id=u.id ORDER BY u.name').fetchall()

@router.post('/users',status_code=201)
def create_user(body:UserInput,request:Request,response:Response):
    if body.role not in ROLES or not body.name.strip() or '@' not in body.email: raise HTTPException(422,'Enter a name, email and valid role.')
    with get_connection() as c:
        c.execute('SELECT pg_advisory_xact_lock(74102027)')
        row=c.execute('INSERT INTO auth_users(email,name,role) VALUES (%s,%s,%s) RETURNING id',(body.email.strip().casefold(),body.name.strip(),body.role)).fetchone()
        link_technician(c,row['id'],body.role,body.technician_id)
        result=issue_token(c,row['id'])
        c.execute('INSERT INTO auth_audit(user_id,action) VALUES (%s,%s)',(request.state.user['id'],f"Created account {row['id']}"))
    response.headers['Cache-Control']='no-store';return {'id':row['id'],**result}

@router.put('/users/{user_id}')
def edit_user(user_id:UUID,body:UserEdit,request:Request):
    if body.role not in ROLES: raise HTTPException(422,'Invalid role.')
    with get_connection() as c:
        c.execute('SELECT pg_advisory_xact_lock(74102027)')
        current=c.execute('SELECT * FROM auth_users WHERE id=%s FOR UPDATE',(user_id,)).fetchone()
        if not current: raise HTTPException(404,'User not found.')
        if current['role']=='admin' and current['is_active'] and (body.role!='admin' or not body.is_active):
            if c.execute("SELECT count(*) AS n FROM auth_users WHERE role='admin' AND is_active").fetchone()['n']<=1: raise HTTPException(409,'Keep at least one active administrator.')
        link_technician(c,user_id,body.role,body.technician_id)
        c.execute('UPDATE auth_users SET role=%s,is_active=%s WHERE id=%s',(body.role,body.is_active,user_id))
        c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user_id,))
        c.execute('INSERT INTO auth_audit(user_id,action) VALUES (%s,%s)',(request.state.user['id'],f'Changed account {user_id} role/status and revoked sessions'))
    return {'message':'Account updated. Existing sessions revoked.'}

@router.post('/users/{user_id}/reset')
def reset(user_id:UUID,request:Request,response:Response):
    with get_connection() as c:
        row=c.execute('SELECT id FROM auth_users WHERE id=%s AND is_active FOR UPDATE',(user_id,)).fetchone()
        if not row: raise HTTPException(404,'Active user not found.')
        c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(user_id,))
        result=issue_token(c,user_id)
        c.execute('INSERT INTO auth_audit(user_id,action) VALUES (%s,%s)',(request.state.user['id'],f'Issued reset for {user_id}'))
    response.headers['Cache-Control']='no-store';return result

@router.get('/audit')
def audit_events():
    with get_connection() as c: return c.execute('SELECT a.*,u.name FROM auth_audit a LEFT JOIN auth_users u ON u.id=a.user_id ORDER BY a.created_at DESC LIMIT 200').fetchall()
