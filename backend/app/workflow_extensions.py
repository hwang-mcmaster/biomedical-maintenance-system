"""Coordinator review, recurring service and validated assignment changes."""
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, model_validator
from psycopg.types.json import Jsonb
from .database import get_connection
from . import repository
from .schemas import Equipment
from .assessment import assess_equipment
from .calculations import reference_date, BUSINESS_TIMEZONE
from .workflow_schemas import TaskInput
from .scheduling_schemas import InputModel, Label
from .scheduling import local_instant, qualification_key
from .workflow import lock, required, create_task_in_transaction

router = APIRouter(prefix='/api/workflow', tags=['Engineering review'])
Note = Annotated[str, Field(min_length=3, max_length=2000, pattern=r'\S.*\S')]


class ReviewInput(InputModel):
    decision: Literal['accepted', 'rejected', 'deferred']
    rationale: Note


class PolicyInput(InputModel):
    title: Label
    interval_days: Annotated[int, Field(strict=True, ge=1, le=3650)]
    last_service_date: date
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)]
    required_qualification: Label
    priority: Literal['Low', 'Medium', 'High']
    source: Note
    active: bool = True

    @model_validator(mode='after')
    def past_service(self):
        if self.last_service_date > reference_date():
            raise ValueError('Last service date cannot be in the future.')
        return self


class AssignmentEdit(InputModel):
    technician_id: UUID
    date: date
    start: Annotated[str, Field(pattern=r'^\d{2}:\d{2}$')]
    expected_technician_id: UUID
    expected_start: datetime
    reason: Note
    acknowledge_late: bool = False

    @model_validator(mode='after')
    def aware_version(self):
        if self.expected_start.tzinfo is None:
            raise ValueError('Expected assignment start requires a timezone.')
        return self


class ReconcileInput(InputModel):
    repair_event: bool
    reason: Note


def coordinator(request):
    if request.state.user['role'] not in ('admin', 'coordinator'):
        raise HTTPException(403, 'Coordinator access required.')


@router.post('/equipment/{equipment_id}/reviews', status_code=201)
def review(equipment_id: UUID, body: ReviewInput, request: Request):
    coordinator(request)
    with get_connection() as c:
        row = required(c.execute(f'SELECT {repository.COLUMNS},updated_at FROM equipment WHERE equipment_id=%s', (equipment_id,)).fetchone(), 'Equipment not found.')
    version = row.pop('updated_at')
    snapshot = assess_equipment(Equipment.model_validate(row))
    with get_connection() as c:
        lock(c)
        current = required(c.execute('SELECT updated_at FROM equipment WHERE equipment_id=%s FOR UPDATE', (equipment_id,)).fetchone(), 'Equipment not found.')
        if current['updated_at'] != version:
            raise HTTPException(409, 'Equipment changed during review. Reassess and retry.')
        return c.execute('INSERT INTO workflow_reviews(equipment_id,equipment_version,snapshot,decision,rationale,actor_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *',
                         (equipment_id, version, Jsonb(snapshot.model_dump(mode='json')), body.decision, body.rationale, request.state.user['id'])).fetchone()


@router.put('/equipment/{equipment_id}/service-policy')
def save_policy(equipment_id: UUID, body: PolicyInput, request: Request):
    coordinator(request)
    with get_connection() as c:
        lock(c)
        equipment = required(c.execute('SELECT in_service_date FROM equipment WHERE equipment_id=%s FOR UPDATE', (equipment_id,)).fetchone(), 'Equipment not found.')
        if body.last_service_date < equipment['in_service_date']:
            raise HTTPException(422, 'Last service date cannot precede in-service date.')
        return c.execute('''INSERT INTO workflow_service_policies(equipment_id,title,interval_days,last_service_date,duration_minutes,required_qualification,priority,source,active,actor_id)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(equipment_id) DO UPDATE SET
          title=excluded.title,interval_days=excluded.interval_days,last_service_date=excluded.last_service_date,
          duration_minutes=excluded.duration_minutes,required_qualification=excluded.required_qualification,priority=excluded.priority,
          source=excluded.source,active=excluded.active,actor_id=excluded.actor_id,updated_at=now() RETURNING *''',
          (equipment_id, body.title, body.interval_days, body.last_service_date, body.duration_minutes,
           qualification_key(body.required_qualification), body.priority, body.source, body.active, request.state.user['id'])).fetchone()


@router.post('/equipment/{equipment_id}/service-policy/generate', status_code=201)
def generate_recurring(equipment_id: UUID, request: Request):
    coordinator(request)
    # Serializes policy reads and task creation; create_task uses the same connection.
    with get_connection() as c:
        lock(c)
        return recurring_task(c, equipment_id, request)


def recurring_task(c, equipment_id, request):
    policy = required(c.execute('SELECT * FROM workflow_service_policies WHERE equipment_id=%s FOR UPDATE', (equipment_id,)).fetchone(), 'Record a service policy first.')
    if not policy['active']:
        raise HTTPException(409, 'Service policy is paused.')
    due = policy['last_service_date'] + timedelta(days=policy['interval_days'])
    key = uuid5(NAMESPACE_URL, f'service:{equipment_id}:{due}')
    # A cancelled cycle can be recreated without returning a terminal task.
    while True:
        previous=c.execute('SELECT id,status FROM workflow_tasks WHERE request_id=%s',(key,)).fetchone()
        if not previous or previous['status']!='cancelled': break
        key=uuid5(NAMESPACE_URL,f'service-retry:{previous["id"]}')
    body = TaskInput(request_id=key, equipment_id=equipment_id, title=policy['title'],
                     duration_minutes=policy['duration_minutes'], required_qualification=policy['required_qualification'],
                     use_assessment=False, priority_override=policy['priority'], override_reason=f"Approved recurring policy: {policy['source'][:1900]}",
                     last_service_date=policy['last_service_date'], service_interval_days=policy['interval_days'])
    # Use workflow's transaction-aware helper rather than nested independent commits.
    task=create_task_in_transaction(body, request, connection=c)
    c.execute('UPDATE workflow_tasks SET recurring_due=%s WHERE id=%s',(due,task['id']))
    return task



@router.post('/assignments/{assignment_id}/reschedule')
def reschedule(assignment_id: UUID, body: AssignmentEdit, request: Request):
    coordinator(request)
    from datetime import time
    try:
        start = local_instant(body.date, time.fromisoformat(body.start))
    except ValueError:
        raise HTTPException(422, 'Enter a valid start time.') from None
    if start <= datetime.now(timezone.utc):
        raise HTTPException(422, 'Assignment must start in the future.')
    with get_connection() as c:
        lock(c)
        assignment = required(c.execute('SELECT a.*,t.duration_minutes,t.due_date,t.request_payload,t.equipment_version,e.updated_at AS current_version FROM workflow_assignments a JOIN workflow_tasks t ON t.id=a.task_id JOIN equipment e ON e.equipment_id=a.equipment_id WHERE a.id=%s FOR UPDATE OF a,t FOR SHARE OF e', (assignment_id,)).fetchone(), 'Assignment not found.')
        if assignment['status'] != 'scheduled' or assignment['starts_at'] != body.expected_start or assignment['technician_id'] != body.expected_technician_id:
            raise HTTPException(409, 'Assignment changed or work has started. Refresh before editing.')
        if assignment['equipment_version'] != assignment['current_version']:
            raise HTTPException(409, 'Equipment changed; cancel this task and create a fresh reviewed task.')
        end = start + timedelta(minutes=assignment['duration_minutes'])
        payload = assignment.get('request_payload') or {}
        service_due = date.fromisoformat(payload['last_service_date']) + timedelta(days=payload['service_interval_days']) if payload.get('last_service_date') else assignment['due_date']
        if end.astimezone(BUSINESS_TIMEZONE).date() > min(service_due, assignment['due_date']) and not body.acknowledge_late:
            raise HTTPException(422, 'This change exceeds the service/review target. Explicitly acknowledge lateness.')
        # Database trigger independently enforces qualification, availability and all booking conflicts.
        c.execute('UPDATE workflow_assignments SET technician_id=%s,starts_at=%s,ends_at=%s WHERE id=%s', (body.technician_id, start, end, assignment_id))
        c.execute("INSERT INTO workflow_events(task_id,from_status,to_status,note,actor_id) VALUES (%s,'scheduled','scheduled',%s,%s)",
                  (assignment['task_id'], f"Rescheduled from {assignment['starts_at']} ({assignment['technician_id']}) to {start} ({body.technician_id}): {body.reason}; late acknowledged: {body.acknowledge_late}", request.state.user['id']))
        return {'id': assignment_id, 'start': start, 'end': end, 'status': 'scheduled'}


@router.post('/history/{history_id}/reconcile')
def reconcile(history_id: UUID, body: ReconcileInput, request: Request):
    coordinator(request)
    with get_connection() as c:
        lock(c)
        history = required(c.execute('SELECT * FROM workflow_history WHERE id=%s FOR UPDATE', (history_id,)).fetchone(), 'History record not found.')
        if history['aggregates_applied']:
            return {'id': history_id, 'already_applied': True}
        c.execute('UPDATE equipment SET total_historical_cost=total_historical_cost+%s,repair_events=repair_events+%s,updated_at=now() WHERE equipment_id=%s',
                  (history['actual_cost'], int(body.repair_event), history['equipment_id']))
        c.execute('UPDATE workflow_history SET aggregates_applied=true WHERE id=%s', (history_id,))
        c.execute("INSERT INTO workflow_events(task_id,from_status,to_status,note,actor_id) VALUES (%s,'completed','completed',%s,%s)",
                  (history['task_id'], f'Applied cost to lifecycle totals; repair event={body.repair_event}: {body.reason}', request.state.user['id']))
        return {'id': history_id, 'already_applied': False}
