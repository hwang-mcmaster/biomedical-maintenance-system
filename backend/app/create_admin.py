"""Run from backend: python -m app.create_admin. Apply AUTH_DATABASE_TASKS.sql first."""
from getpass import getpass
from .auth import password
from .database import get_connection

def main():
    email=input('Administrator email: ').strip().casefold();name=input('Name: ').strip()
    if '@' not in email or not name: raise SystemExit('A valid email and name are required.')
    value=getpass('Password (15+ characters): ')
    if value!=getpass('Confirm password: '): raise SystemExit('Passwords differ.')
    encoded=password(value)
    with get_connection() as c:
        c.execute('SELECT pg_advisory_xact_lock(74102027)')
        if c.execute("SELECT 1 FROM auth_users WHERE role='admin' AND is_active").fetchone(): raise SystemExit('An administrator already exists. Use account administration.')
        c.execute("INSERT INTO auth_users(email,name,password_hash,role) VALUES (%s,%s,%s,'admin')",(email,name,encoded))
    print('Administrator created. No password was written to source files.')
if __name__=='__main__': main()
