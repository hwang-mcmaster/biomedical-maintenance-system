# Authorized access and service workspace

Frontend/backend implementation is complete enough for account and role testing.
The app intentionally fails closed until the account tables exist. There are no
default credentials or public registration.

## Database tasks for the database owner

The account schema is `database/migrations/005_authentication.sql`. It is applied
by `python -m app.migrate` after migrations 002–004 and before 006, and it is
re-runnable. Apply it to the intended DEV database first. For a manual review,
`psql -1 -f` runs it in one transaction. The file implements items 1–7 below.

1. Create auth_users with unique normalized email, password hash, allowed role,
   active status and creation timestamp. Roles: admin/coordinator/technician.
2. Create auth_sessions, linked to users, with hashed opaque tokens, CSRF tokens,
   creation/last-seen timestamps and absolute expiration. Index user_id.
3. Create auth_tokens for hashed one-use activation/reset tokens and expiry.
4. Create auth_attempts for shared account/IP throttling buckets. Failed attempts
   must persist even when a sign-in returns 401.
5. Create auth_audit for timestamped user/account/security activity.
6. Add unique nullable workflow_technicians.user_id referencing auth_users. Link
   technician accounts explicitly; account roles do not certify qualifications.
7. Add nullable workflow_events.actor_id referencing auth_users. Keep historical
   rows NULL instead of inventing an actor. New task/status/confirmation events
   record the authenticated actor in the same transaction.
8. Back up the target database, review grants for the application user and apply
   the supplied transaction once. Verify constraints and existing record counts.
9. Schedule cleanup of expired sessions/tokens and old throttling buckets. Define
   an audit retention policy appropriate to the deployment. Keep audit rows out
   of ordinary user edit/delete interfaces.
10. Run account bootstrap and authenticated integration checks against dev before
    applying the reviewed schema to the shared environment. Do not delete existing
    equipment/history as part of access setup.

## Bootstrap and local startup after database setup

Install backend requirements, then run from backend:

    venv/Scripts/python.exe -m app.create_admin

This prompts for administrator email/name/password without storing credentials in
source. New passwords currently use the requested temporary 5–20 character limit.
Existing longer passwords remain accepted at sign-in; changing/resetting them uses
the new limit. Email is a unique login identifier and need not be a deliverable
inbox while activation/reset links are distributed manually. It refuses to bootstrap over an existing active administrator.

For local HTTP set AUTH_COOKIE_SECURE=false in backend/.env. In deployment use
HTTPS and AUTH_COOKIE_SECURE=true. Configure APP_ORIGINS as the exact comma-separated
browser origins. Sessions expire after 30 minutes idle or eight hours absolute.
Account disabling, role changes and password resets revoke existing sessions.

The Vite frontend proxies /api to 127.0.0.1:8000. Open localhost:5173 consistently
rather than alternating hostnames. The default browser API base is same-origin. Clear any old VITE_API_URL value in frontend/.env to use the proxy.
A production reverse proxy must serve React and /api at the same HTTPS origin and
fall back to index.html. Page navigation uses bookmarkable hash URLs.

Start the backend/AI/frontend using the existing three terminals. Keep
SCHEDULER_ENABLED=false for local runs. No AI model code was changed in this task.

## Pages and roles

Sidebar: Overview, Equipment, Maintenance tasks, Scheduling, Technicians, My work,
Administration and Advanced tools. Account/password actions are in the header.
Equipment details separate overview, assessment and maintenance. Inventory supports
search/status filtering, sorting and 15-row pages. Advanced tools retain the legacy
calendar and unsaved manual preview for administrators.

Administrators manage users, reset links, role changes, diagnostics and audit.
Coordinators manage equipment, tasks, technicians and scheduling. Technicians may
read records, see My work and start/complete only their own assigned tasks. They
cannot cancel tasks, generate schedules, export the fleet or administer users.

Create a technician record before creating its linked technician account. The
admin receives a one-time activation link, valid for one hour. Deliver it securely
to the intended recipient. No email delivery is implemented. Reset links use the
same one-use flow and revoke sessions. Changing a password signs out all sessions.

## Security boundary

The backend checks sessions/roles on every operational endpoint, including CSV,
legacy routes and API documentation. Only minimal health, sign-in and token-based
password setup are public. Mutations check exact Origin and a session-bound CSRF
header. Session cookies are HttpOnly/SameSite=Lax and Secure by default. Passwords
use Argon2id. Token digests, not raw session/reset tokens, live in the database.
There is no authentication-disable environment variable.

Pre-action audit failures block operational writes. Result audit failures log an
error because a committed action must not be reported as rolled back. Workflow
actor events remain atomic with their task changes. Login throttling uses shared
15-minute account/IP buckets. No user passwords or tokens are written to audit.

Deployment tasks outside frontend/backend code changes:
- Keep the AI service private (127.0.0.1 locally, private network/firewall in
  deployment). Its separate existing endpoints are NOT protected by backend
  cookies. Do not expose port 8001 publicly. A future AI service-key verifier
  requires an AI-code change and matching backend client configuration.
- Restrict direct RDS access, use a least-privilege app database user and retain TLS.
- Configure HTTPS, secure cookies, proxy origins and audit retention/monitoring.
- External SSO/MFA and email-delivered recovery are future integrations, not
  capabilities claimed by this implementation.

## Checks and current limits

    backend/venv/Scripts/python.exe -m unittest discover -s backend -p test_auth.py
    npm.cmd --prefix frontend test
    npm.cmd --prefix frontend run lint

The account unit tests mock persistence and verify login gates, roles, CSRF,
logout, hashing and assignment ownership. Business unit tests use a scoped identity
mock, never a production bypass. Current opt-in PostgreSQL/workflow tests and
the React live npm entry point use real temporary accounts, session cookies and
CSRF. See VALIDATION.md for commands and saved results. Invitation/reset,
last-admin races and wider account lifecycle scenarios still need additional
live coverage. Older standalone unauthenticated scripts are historical only.
The workspace still uses existing small-fleet list APIs for data loading; table
pagination is client-side. Server-side paging is a later scalability improvement.

## Frontend-only development preview

Start only Vite, then open http://localhost:5173/?preview=1#/overview . This
uses sample data without requesting the backend. Mutation requests are rejected
locally. The prominent preview banner distinguishes this from an authenticated
session. The switch only exists when import.meta.env.DEV is true; production
builds ignore the preview query and still require real authentication.
