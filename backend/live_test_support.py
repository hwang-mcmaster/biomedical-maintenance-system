"""Isolated real-login fixtures. Never changes an existing user's credentials."""
import secrets
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.auth import digest, hasher
from app.database import get_connection

ORIGIN = 'http://localhost:5173'


def authenticated_fixture(case, role='admin'):
    identifier = uuid4()
    email = f'validation-{identifier.hex}@example.test'
    plain = secrets.token_urlsafe(12)
    with get_connection() as c:
        c.execute('INSERT INTO auth_users(id,email,name,password_hash,role) VALUES (%s,%s,%s,%s,%s)',
                  (identifier, email, 'Isolated validation fixture', hasher.hash(plain), role))
    def cleanup():
        with get_connection() as c:
            c.execute('DELETE FROM auth_audit WHERE user_id=%s', (identifier,))
            c.execute('DELETE FROM auth_sessions WHERE user_id=%s', (identifier,))
            c.execute('DELETE FROM auth_tokens WHERE user_id=%s', (identifier,))
            c.execute('DELETE FROM auth_attempts WHERE bucket=%s', (digest('account:'+email),))
            c.execute('DELETE FROM auth_users WHERE id=%s', (identifier,))
    case.addCleanup(cleanup)
    client = TestClient(app, headers={'Origin': ORIGIN})
    response = client.post('/api/auth/login', json={'email': email, 'password': plain})
    case.assertEqual(response.status_code, 200, response.text)
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    case.addCleanup(client.close)
    return client
