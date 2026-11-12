"""Saved maintenance workflow. All mutations serialize on one transaction lock.
The small prototype favors correctness over concurrent write throughput.
"""
from datetime import datetime, timedelta, timezone
from time import perf_counter
from uuid import UUID
from fastapi import APIRouter, HTTPException, Response, Request
from psycopg.types.json import Jsonb
from .database import get_connection
from . import repository
from .schemas import Equipment
from .assessment import assess_equipment
from .calculations import reference_date, BUSINESS_TIMEZONE
from .scheduling import generate_schedule, local_instant, qualification_key
from .scheduling_schemas import ScheduleRequest
from .workflow_schemas import TechnicianInput, TaskInput, PlanInput, StatusInput

router=APIRouter(prefix='/api/workflow', tags=['Saved maintenance workflow'])
LOCK=74102026
LEVEL_PRIORITY={'high':'High','medium':'Medium','low':'Low'}
TARGET_DAYS={'High':7,'Medium':30,'Low':90}


def lock(c):
    c.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK,))


def required(row, message):
    if row is None: raise HTTPException(404,message)
    return row


def priority_policy(assessment, override=None, reason=None):
    level=assessment.risk_level if assessment else None
    suggested=LEVEL_PRIORITY.get(level)
    if assessment and suggested is None: raise HTTPException(422,'Assessment returned an unsupported repair-intensity level.')
    priority=override or suggested
    if priority is None: raise HTTPException(422,'Enter a manual priority and reason when assessment is unavailable.')
    explanation=(f'Repair intensity {level}, training-fleet percentile {assessment.risk_score:.1%}: suggested {suggested}. '
                 'This is a prototype workload policy, not failure probability or a clinical service deadline. ') if assessment else 'Explicit manual priority. '
    if override: explanation+=f'User selected {override}: {reason}'
    return priority, explanation


def qualification(c, value):
    value=qualification_key(value)
    c.execute('INSERT INTO workflow_qualifications(name) VALUES (%s) ON CONFLICT DO NOTHING',(value,))
    return value


def technicians(c):
    result=c.execute('SELECT * FROM workflow_technicians ORDER BY created_at,id').fetchall()
    for tech in result:
        tech['qualifications']=[r['qualification'] for r in c.execute('SELECT qualification FROM workflow_technician_qualifications WHERE technician_id=%s ORDER BY qualification',(tech['id'],))]
        tech['availability']=[{'date':r['starts_at'].astimezone(BUSINESS_TIMEZONE).date(),
          'start':r['starts_at'].astimezone(BUSINESS_TIMEZONE).strftime('%H:%M'),
          'end':r['ends_at'].astimezone(BUSINESS_TIMEZONE).strftime('%H:%M')}
          for r in c.execute('SELECT * FROM workflow_availability WHERE technician_id=%s ORDER BY starts_at',(tech['id'],))]
    return result


@router.get('/technicians')
def list_technicians():
    with get_connection() as c: return technicians(c)


def save_technician(body, technician_id=None):
    with get_connection() as c:
        lock(c)
        if technician_id:
            required(c.execute('SELECT id FROM workflow_technicians WHERE id=%s FOR UPDATE',(technician_id,)).fetchone(),'Technician not found.')
            c.execute('UPDATE workflow_technicians SET name=%s WHERE id=%s',(body.name,technician_id))
        else:
            technician_id=c.execute('INSERT INTO workflow_technicians(name) VALUES (%s) RETURNING id',(body.name,)).fetchone()['id']
        qualifications={qualification(c,v) for v in body.qualifications}
        windows=[(local_instant(w.date,w.start),local_instant(w.date,w.end)) for w in body.availability]
        commitments=c.execute("SELECT a.*,t.required_qualification FROM workflow_assignments a JOIN workflow_tasks t ON t.id=a.task_id WHERE a.technician_id=%s AND a.status IN ('scheduled','in_progress')",(technician_id,)).fetchall()
        for a in commitments:
            if a['required_qualification'] not in qualifications or not any(start<=a['starts_at'] and a['ends_at']<=end for start,end in windows):
                raise HTTPException(409,'This edit would invalidate a confirmed assignment. Cancel it before changing qualifications or availability.')
        c.execute('DELETE FROM workflow_technician_qualifications WHERE technician_id=%s',(technician_id,))
        c.execute('DELETE FROM workflow_availability WHERE technician_id=%s',(technician_id,))
        for value in sorted(qualifications): c.execute('INSERT INTO workflow_technician_qualifications VALUES (%s,%s)',(technician_id,value))
        for start,end in windows: c.execute('INSERT INTO workflow_availability(technician_id,starts_at,ends_at) VALUES (%s,%s,%s)',(technician_id,start,end))
        return next(t for t in technicians(c) if t['id']==technician_id)


@router.post('/technicians',status_code=201)
def create_technician(body: TechnicianInput): return save_technician(body)


@router.put('/technicians/{technician_id}')
def update_technician(technician_id: UUID, body: TechnicianInput): return save_technician(body,technician_id)


def task_rows(c, equipment_id=None):
    where=' WHERE t.equipment_id=%s' if equipment_id else ''
    return c.execute('SELECT t.*,e.asset_tag,a.snapshot AS assessment FROM workflow_tasks t JOIN equipment e ON e.equipment_id=t.equipment_id LEFT JOIN workflow_assessments a ON a.id=t.assessment_id'+where+' ORDER BY t.created_at,t.id',(equipment_id,) if equipment_id else ()).fetchall()


@router.get('/tasks')
def list_tasks():
    with get_connection() as c: return task_rows(c)


def existing_task(c, body):
    row=c.execute('SELECT id,equipment_id,request_payload FROM workflow_tasks WHERE request_id=%s',(body.request_id,)).fetchone()
    if row:
        if row['request_payload']!=body.model_dump(mode='json',exclude={'request_id'}):
            raise HTTPException(409,'This request ID was already used with different task inputs. Refresh before creating a new task.')
        return next(t for t in task_rows(c,row['equipment_id']) if t['id']==row['id'])
    return None


@router.post('/tasks',status_code=201)
def create_task(body: TaskInput, request: Request):
    # Model calls happen outside the write lock. Version comparison prevents stale saves.
    with get_connection() as c:
        saved=existing_task(c,body)
        if saved: return saved
        row=required(c.execute(f'SELECT {repository.COLUMNS},updated_at FROM equipment WHERE equipment_id=%s',(body.equipment_id,)).fetchone(),'Equipment not found.')
    assessment=assess_equipment(Equipment.model_validate({k:v for k,v in row.items() if k!="updated_at"})) if body.use_assessment else None
    priority,reason=priority_policy(assessment,body.priority_override,body.override_reason)
    due=body.due_date or reference_date()+timedelta(days=TARGET_DAYS[priority])
    with get_connection() as c:
        lock(c)
        saved=existing_task(c,body)
        if saved: return saved
        current=required(c.execute('SELECT updated_at FROM equipment WHERE equipment_id=%s FOR UPDATE',(body.equipment_id,)).fetchone(),'Equipment not found.')
        if current['updated_at']!=row['updated_at']: raise HTTPException(409,'Equipment changed during assessment. Review it and retry.')
        assessment_id=None
        if assessment:
            assessment_id=c.execute('INSERT INTO workflow_assessments(equipment_id,equipment_version,snapshot) VALUES (%s,%s,%s) RETURNING id',
              (body.equipment_id,row['updated_at'],Jsonb(assessment.model_dump(mode='json')))).fetchone()['id']
        q=qualification(c,body.required_qualification)
        task=c.execute('INSERT INTO workflow_tasks(equipment_id,assessment_id,equipment_version,title,duration_minutes,required_qualification,priority,priority_reason,due_date,request_id,request_payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
          (body.equipment_id,assessment_id,row['updated_at'],body.title,body.duration_minutes,q,priority,reason,due,body.request_id,Jsonb(body.model_dump(mode='json',exclude={'request_id'})))).fetchone()
        c.execute("INSERT INTO workflow_events(task_id,to_status,note,actor_id) VALUES (%s,'pending',%s,%s)",(task['id'],reason,request.state.user['id']))
        return next(t for t in task_rows(c,body.equipment_id) if t['id']==task['id'])


def assignments(c, equipment_id=None):
    where=' WHERE a.equipment_id=%s' if equipment_id else ''
    return c.execute('SELECT a.*,t.title,t.priority,t.priority_reason,t.due_date,e.asset_tag,tech.name AS technician_name FROM workflow_assignments a JOIN workflow_tasks t ON t.id=a.task_id JOIN equipment e ON e.equipment_id=a.equipment_id JOIN workflow_technicians tech ON tech.id=a.technician_id'+where+' ORDER BY a.starts_at,a.id',(equipment_id,) if equipment_id else ()).fetchall()


@router.get('/assignments')
def list_assignments():
    with get_connection() as c: return assignments(c)


@router.get('/equipment/{equipment_id}')
def equipment_context(equipment_id: UUID):
    with get_connection() as c:
        required(c.execute('SELECT equipment_id FROM equipment WHERE equipment_id=%s',(equipment_id,)).fetchone(),'Equipment not found.')
        tasks=task_rows(c,equipment_id)
        return {'tasks':tasks,'assignments':assignments(c,equipment_id),
          'latest_saved_assessment':c.execute('SELECT snapshot,created_at,equipment_version FROM workflow_assessments WHERE equipment_id=%s ORDER BY created_at DESC LIMIT 1',(equipment_id,)).fetchone(),
          'history':c.execute('SELECT h.*,t.title FROM workflow_history h JOIN workflow_tasks t ON t.id=h.task_id WHERE h.equipment_id=%s ORDER BY h.completed_at DESC',(equipment_id,)).fetchall(),
          'events':c.execute('SELECT v.* FROM workflow_events v JOIN workflow_tasks t ON t.id=v.task_id WHERE t.equipment_id=%s ORDER BY v.created_at',(equipment_id,)).fetchall()}


def build_plan(c, body):
    started=perf_counter()
    rows=c.execute('SELECT t.*,e.updated_at AS current_version FROM workflow_tasks t JOIN equipment e ON e.equipment_id=t.equipment_id WHERE t.id=ANY(%s) FOR UPDATE OF t FOR SHARE OF e',(body.task_ids,)).fetchall()
    if len(rows)!=len(body.task_ids): raise HTTPException(404,'One or more tasks no longer exist.')
    if any(r['status']!='pending' for r in rows): raise HTTPException(409,'Only pending tasks can be scheduled. Refresh the task list.')
    if any(r['equipment_version']!=r['current_version'] for r in rows): raise HTTPException(409,'Equipment changed after task creation. Cancel the outdated task and create a reviewed replacement.')
    techs=technicians(c)
    if not techs: raise HTTPException(422,'Add a technician with qualifications and availability first.')
    if len(techs)>30: raise HTTPException(422,'This prototype supports at most 30 technicians per planning run.')
    equipment={str(r['id']):r for r in c.execute(f'SELECT {repository.COLUMNS} FROM equipment')}
    now=datetime.now(timezone.utc)
    minimum=(now+timedelta(minutes=1)).astimezone(BUSINESS_TIMEZONE).replace(second=0,microsecond=0)
    inputs=[]
    for tech in techs:
        windows=[]
        for w in tech['availability']:
            if w['date']!=body.schedule_date: continue
            start=datetime.strptime(w['start'],'%H:%M').time();end=datetime.strptime(w['end'],'%H:%M').time()
            if body.schedule_date==reference_date(): start=max(start,minimum.time().replace(tzinfo=None))
            if start<end: windows.append({'start':start,'end':end})
        inputs.append({'id':str(tech['id']),'name':tech['name'],'qualifications':tech['qualifications'],'availability':windows})
    request=ScheduleRequest(schedule_date=body.schedule_date,tasks=[{
      'id':str(r['id']),'equipment_id':r['equipment_id'],'title':r['title'],'priority':r['priority'],
      'duration_minutes':r['duration_minutes'],'required_qualification':r['required_qualification']} for r in rows],technicians=inputs)
    bookings=[(str(a['technician_id']),a['equipment_id'],a['starts_at'],a['ends_at']) for a in c.execute("SELECT * FROM workflow_assignments WHERE status IN ('scheduled','in_progress')")]
    # Legacy automatic schedules reserve equipment too, but carry no technician.
    if c.execute("SELECT to_regclass('maintenance_schedules') AS name").fetchone()['name']:
        bookings.extend((None,r['equipment_id'],r['scheduled_start_time'],r['scheduled_end_time']) for r in c.execute("SELECT * FROM maintenance_schedules WHERE status IN ('scheduled','pending','in_progress') AND scheduled_start_time IS NOT NULL AND scheduled_end_time IS NOT NULL"))
    result=generate_schedule(request,equipment,bookings).model_dump(mode='json')
    reasons={str(r['id']):r for r in rows}
    for a in result['assignments']:
        task=reasons[a['task_id']];a['priority_reason']=task['priority_reason'];a['due_date']=task['due_date'].isoformat()
        a['within_target']=datetime.fromisoformat(a['end']).astimezone(BUSINESS_TIMEZONE).date()<=task['due_date']
    available_minutes=sum((local_instant(body.schedule_date,w.end)-local_instant(body.schedule_date,w.start)).total_seconds()/60 for t in request.technicians for w in t.availability)
    selected_minutes=sum(a['duration_minutes'] for a in result['assignments'])
    high=[a for a in result['assignments'] if a['priority']=='High']
    conflicts=sum(1 for i,a in enumerate(result['assignments']) for b in result['assignments'][i+1:] if (a['technician_id']==b['technician_id'] or a['equipment_id']==b['equipment_id']) and datetime.fromisoformat(a['start'])<datetime.fromisoformat(b['end']) and datetime.fromisoformat(b['start'])<datetime.fromisoformat(a['end']))
    if conflicts: raise HTTPException(500,'Schedule validation failed. No bookings were saved.')
    result['metrics']={'computation_ms':round((perf_counter()-started)*1000,2),'tasks_requested':len(rows),
      'scheduled_count':len(result['assignments']),'unscheduled_count':len(result['unscheduled']),'conflicts':conflicts,
      'high_priority_requested':sum(r['priority']=='High' for r in rows),'high_priority_scheduled_within_target':sum(a['within_target'] for a in high),
      'selected_task_utilization_percent':round(100*selected_minutes/available_minutes,2) if available_minutes else 0,
      'technicians':[{'technician_id':t['id'],'name':t['name'],'assigned_minutes':sum(a['duration_minutes'] for a in result['assignments'] if a['technician_id']==t['id']), 'available_minutes':sum((local_instant(body.schedule_date,w.end)-local_instant(body.schedule_date,w.start)).total_seconds()/60 for w in request.technicians[i].availability)} for i,t in enumerate(inputs)]}
    result['notices']=['Saved draft. Confirm it to reserve resources. Priority comes from reviewed assessment or an explicit manual override.',
      'High/Medium/Low maps from repair intensity. Default review targets are 7/30/90 days, not manufacturer service intervals or clinical deadlines.',
      'Priority-first placement is feasible, not globally optimal. Utilization measures this run only, not actual work completed. Times use America/Toronto.']
    return result


@router.post('/schedules/preview',status_code=201)
def preview(body: PlanInput):
    with get_connection() as c:
        lock(c)
        result=build_plan(c,body)
        row=c.execute('INSERT INTO workflow_schedules(schedule_date,task_ids,result) VALUES (%s,%s,%s) RETURNING id,status',
          (body.schedule_date,Jsonb([str(i) for i in body.task_ids]),Jsonb(result))).fetchone()
        return {**row,**result,'draft_saved':True,'booked':False}


@router.get('/schedules')
def schedules():
    with get_connection() as c: return c.execute('SELECT * FROM workflow_schedules ORDER BY created_at DESC LIMIT 100').fetchall()


@router.post('/schedules/{schedule_id}/confirm')
def confirm(schedule_id: UUID, request: Request):
    with get_connection() as c:
        lock(c)
        row=required(c.execute('SELECT * FROM workflow_schedules WHERE id=%s FOR UPDATE',(schedule_id,)).fetchone(),'Schedule not found.')
        if row['status']=='confirmed': return {'id':schedule_id,'status':'confirmed','message':'Already confirmed. No duplicate assignments created.'}
        if row['schedule_date']<reference_date(): raise HTTPException(409,'This draft is from a previous date. Generate a new preview.')
        body=PlanInput(schedule_date=row['schedule_date'],task_ids=row['task_ids'])
        result=build_plan(c,body)
        if not result['assignments']: raise HTTPException(422,'There are no assignments to confirm.')
        if result['assignments']!=row['result']['assignments']: raise HTTPException(409,'Tasks, availability or bookings changed. Generate a new preview before confirming.')
        if any(datetime.fromisoformat(a['start'])<=datetime.now(timezone.utc) for a in result['assignments']): raise HTTPException(409,'Preview contains a past start time. Generate a new preview.')
        for a in result['assignments']:
            c.execute('INSERT INTO workflow_assignments(schedule_id,task_id,equipment_id,technician_id,starts_at,ends_at) VALUES (%s,%s,%s,%s,%s,%s)',
              (schedule_id,a['task_id'],a['equipment_id'],a['technician_id'],a['start'],a['end']))
            c.execute("UPDATE workflow_tasks SET status='scheduled',updated_at=now() WHERE id=%s",(a['task_id'],))
            c.execute("INSERT INTO workflow_events(task_id,from_status,to_status,note,actor_id) VALUES (%s,'pending','scheduled',%s,%s)",(a['task_id'],f'Confirmed schedule {schedule_id}',request.state.user['id']))
        c.execute("UPDATE workflow_schedules SET status='confirmed',confirmed_at=now() WHERE id=%s",(schedule_id,))
        return {'id':schedule_id,'status':'confirmed','assigned_count':len(result['assignments'])}


@router.post('/tasks/{task_id}/status')
def change_status(task_id: UUID, body: StatusInput, request: Request):
    with get_connection() as c:
        lock(c)
        task=required(c.execute('SELECT * FROM workflow_tasks WHERE id=%s FOR UPDATE',(task_id,)).fetchone(),'Task not found.')
        user=request.state.user
        if user['role']=='technician':
            owner=c.execute('SELECT 1 FROM workflow_assignments a JOIN workflow_technicians tech ON tech.id=a.technician_id WHERE a.task_id=%s AND tech.user_id=%s',(task_id,user['id'])).fetchone()
            if not owner or body.status=='cancelled': raise HTTPException(403,'Technicians may only start or complete their own assigned work.')
        allowed={'pending':{'cancelled'},'scheduled':{'in_progress','cancelled'},'in_progress':{'completed','cancelled'},'completed':set(),'cancelled':set()}
        if body.status not in allowed[task['status']]: raise HTTPException(409,f"Cannot move {task['status']} to {body.status}.")
        assignment=c.execute('SELECT * FROM workflow_assignments WHERE task_id=%s',(task_id,)).fetchone()
        if body.status=='in_progress' and assignment['starts_at']>datetime.now(timezone.utc): raise HTTPException(409,'Cannot start work before its confirmed start time.')
        c.execute('UPDATE workflow_tasks SET status=%s,updated_at=now() WHERE id=%s',(body.status,task_id))
        c.execute('UPDATE workflow_assignments SET status=%s WHERE task_id=%s',(body.status,task_id))
        c.execute('INSERT INTO workflow_events(task_id,from_status,to_status,note,actor_id) VALUES (%s,%s,%s,%s,%s)',(task_id,task['status'],body.status,body.notes,user['id']))
        if body.status=='completed':
            c.execute('INSERT INTO workflow_history(task_id,equipment_id,notes,actual_cost) VALUES (%s,%s,%s,%s)',(task_id,task['equipment_id'],body.notes,body.actual_cost))
        # Completion records are separate service events. Aggregate training fields are not silently changed.
        return {'id':task_id,'status':body.status}


@router.get('/metrics')
def validation_metrics():
    with get_connection() as c:
        totals=c.execute("SELECT count(*) AS tasks, count(*) FILTER(WHERE status='pending') AS pending, count(*) FILTER(WHERE status='completed') AS completed FROM workflow_tasks").fetchone()
        completion=c.execute("SELECT count(*) AS completed, count(*) FILTER(WHERE (h.completed_at AT TIME ZONE 'America/Toronto')::date<=t.due_date) AS completed_within_target FROM workflow_history h JOIN workflow_tasks t ON t.id=h.task_id WHERE t.priority='High'").fetchone()
        return {'tasks':totals,'high_priority_completion':completion,
          'scope':'Recorded task completions only. Scheduling utilization and timing are per-run estimates, not clinical or downtime outcomes.'}


@router.get('/my-work')
def my_work(request: Request):
    with get_connection() as c:
        return c.execute('SELECT a.*,t.title,t.priority,t.priority_reason,e.asset_tag FROM workflow_assignments a JOIN workflow_tasks t ON t.id=a.task_id JOIN equipment e ON e.equipment_id=a.equipment_id JOIN workflow_technicians tech ON tech.id=a.technician_id WHERE tech.user_id=%s ORDER BY a.starts_at',(request.state.user['id'],)).fetchall()
