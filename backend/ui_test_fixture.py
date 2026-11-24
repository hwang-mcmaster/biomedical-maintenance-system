"""CLI fixture helper for the opt-in React integration test; never an API route.

    Receives a generated run UUID and action on stdin. The caller captures the
    temporary password privately. Existing accounts and equipment are untouched.
"""
import json
import secrets
import sys
from uuid import UUID
from app.auth import digest, hasher
from app.database import get_connection


def main():
    body=json.load(sys.stdin)
    identifier=UUID(body['run_id'])
    tag='UI-VALIDATE-'+identifier.hex
    email=f'validation-ui-{identifier.hex}@example.test'
    with get_connection() as c:
        if body['action']=='create':
            plain=secrets.token_urlsafe(12)
            c.execute('INSERT INTO auth_users(id,email,name,role,password_hash) VALUES (%s,%s,%s,%s,%s)',
              (identifier,email,tag,'coordinator',hasher.hash(plain)))
            print(json.dumps({'email':email,'password':plain,'tag':tag,'qualification':'ui-'+identifier.hex}))
        elif body['action']=='cleanup':
            c.execute('SELECT pg_advisory_xact_lock(74102026)')
            equipment=[r['equipment_id'] for r in c.execute('SELECT equipment_id FROM equipment WHERE asset_tag=%s',(tag,))]
            tasks=[str(r['id']) for r in c.execute('SELECT id FROM workflow_tasks WHERE equipment_id=ANY(%s)',(equipment,))]
            c.execute('DELETE FROM workflow_events WHERE task_id IN (SELECT id FROM workflow_tasks WHERE equipment_id=ANY(%s))',(equipment,))
            c.execute('DELETE FROM workflow_history WHERE equipment_id=ANY(%s)',(equipment,))
            c.execute('DELETE FROM workflow_assignments WHERE equipment_id=ANY(%s)',(equipment,))
            c.execute('DELETE FROM workflow_schedules WHERE task_ids ?| %s',(tasks,))
            c.execute('DELETE FROM workflow_tasks WHERE equipment_id=ANY(%s)',(equipment,))
            c.execute('DELETE FROM workflow_assessments WHERE equipment_id=ANY(%s)',(equipment,))
            c.execute('DELETE FROM equipment WHERE equipment_id=ANY(%s)',(equipment,))
            c.execute('DELETE FROM workflow_technicians WHERE name=%s',(tag,))
            c.execute('DELETE FROM workflow_qualifications WHERE name=%s',('ui-'+identifier.hex,))
            c.execute('DELETE FROM auth_audit WHERE user_id=%s',(identifier,))
            c.execute('DELETE FROM auth_sessions WHERE user_id=%s',(identifier,))
            c.execute('DELETE FROM auth_tokens WHERE user_id=%s',(identifier,))
            c.execute('DELETE FROM auth_attempts WHERE bucket=%s',(digest('account:'+email),))
            c.execute('DELETE FROM auth_users WHERE id=%s AND email=%s',(identifier,email))
            print(json.dumps({'cleaned':True,'run_id':str(identifier)}))
        else: raise ValueError('Unknown fixture action.')


if __name__=='__main__': main()
