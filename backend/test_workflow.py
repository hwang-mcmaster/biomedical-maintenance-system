"""Unit and opt-in RDS workflow tests. Cleanup touches only generated fixture IDs."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_connection
from app.calculations import reference_date
from app.workflow import priority_policy
from app.workflow_schemas import TechnicianInput, TaskInput
from pydantic import ValidationError
from test_equipment import PAYLOAD

class PolicyTests(unittest.TestCase):
    def test_mapping_and_explanation(self):
        for level,expected in [('high','High'),('medium','Medium'),('low','Low')]:
            priority,reason=priority_policy(SimpleNamespace(risk_level=level,risk_score=.8))
            self.assertEqual(priority,expected)
            self.assertIn('not failure probability',reason)
        priority,reason=priority_policy(SimpleNamespace(risk_level='low',risk_score=.1),'High','Repeated engineering concerns')
        self.assertEqual(priority,'High');self.assertIn('Repeated engineering concerns',reason)

    def test_manual_mode_and_invalid_inputs(self):
        base=dict(equipment_id=uuid4(),title='Review',duration_minutes=60,required_qualification='Ventilator')
        for change in [dict(use_assessment=False),dict(priority_override='High'),dict(duration_minutes=0),dict(title='  '),dict(required_qualification='  ')]:
            with self.assertRaises(ValidationError): TaskInput(**(base|change))
        TaskInput(**(base|dict(use_assessment=False,priority_override='Medium',override_reason='Reviewed manually')))
        day=reference_date()+timedelta(days=1)
        with self.assertRaises(ValidationError): TechnicianInput(name='A',qualifications=['Ventilator'],availability=[
          dict(date=day,start='09:00',end='12:00'),dict(date=day,start='11:00',end='13:00')])

@unittest.skipUnless(os.getenv('RUN_WORKFLOW_TESTS')=='1','Set RUN_WORKFLOW_TESTS=1 for isolated RDS workflow fixtures.')
class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app);self.token=uuid4().hex;self.equipment=[];self.techs=[];self.runs=[]
        self.day=(reference_date()+timedelta(days=2)).isoformat()
        with get_connection() as c:
            self.original=c.execute('SELECT count(*) AS n FROM equipment').fetchone()['n']
        self.eq=self.create_equipment()

    def tearDown(self):
        with get_connection() as c:
            c.execute('SELECT pg_advisory_xact_lock(74102026)')
            for equipment_id in self.equipment:
                c.execute('DELETE FROM workflow_events WHERE task_id IN (SELECT id FROM workflow_tasks WHERE equipment_id=%s)',(equipment_id,))
                c.execute('DELETE FROM workflow_history WHERE equipment_id=%s',(equipment_id,))
                c.execute('DELETE FROM workflow_assignments WHERE equipment_id=%s',(equipment_id,))
                c.execute('DELETE FROM workflow_tasks WHERE equipment_id=%s',(equipment_id,))
                c.execute('DELETE FROM workflow_assessments WHERE equipment_id=%s',(equipment_id,))
                c.execute('DELETE FROM equipment WHERE equipment_id=%s',(equipment_id,))
            for run in self.runs: c.execute('DELETE FROM workflow_schedules WHERE id=%s',(run,))
            for tech in self.techs: c.execute('DELETE FROM workflow_technicians WHERE id=%s',(tech,))
            c.execute('DELETE FROM workflow_qualifications q WHERE NOT EXISTS(SELECT 1 FROM workflow_tasks t WHERE t.required_qualification=q.name) AND NOT EXISTS(SELECT 1 FROM workflow_technician_qualifications tq WHERE tq.qualification=q.name) AND name=%s',(self.token,))
            self.assertEqual(c.execute('SELECT count(*) AS n FROM equipment').fetchone()['n'],self.original)

    def post(self,path,body,status=201):
        r=self.client.post('/api/workflow/'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()

    def create_equipment(self):
        token=uuid4().hex
        r=self.client.post('/api/equipment',json=PAYLOAD|{'asset_tag':'CODEX-W10-'+token,'serial_number':'000'+token})
        self.assertEqual(r.status_code,201,r.text);self.equipment.append(r.json()['id']);return r.json()['id']

    def technician(self):
        body={'name':'CODEX-W10-'+self.token,'qualifications':[self.token], 'availability':[{'date':self.day,'start':'09:00','end':'17:00'}]}
        result=self.post('technicians',body);self.techs.append(result['id']);return result

    def task(self,eq=None,**changes):
        return self.post('tasks',{'equipment_id':eq or self.eq,'title':'Fixture review','duration_minutes':60,
          'required_qualification':self.token,'use_assessment':False,'priority_override':'High','override_reason':'Explicit synthetic test priority',**changes})

    def preview(self,ids):
        r=self.post('schedules/preview',{'schedule_date':self.day,'task_ids':ids});self.runs.append(r['id']);return r

    def test_full_manual_and_assessment_flow(self):
        self.technician()
        task=self.task()
        preview=self.preview([task['id']]);self.assertEqual(preview['metrics']['scheduled_count'],1)
        self.assertIn('Explicit',preview['assignments'][0]['priority_reason'])
        self.post(f"schedules/{preview['id']}/confirm",{},200)
        self.post(f"schedules/{preview['id']}/confirm",{},200)
        context=self.client.get('/api/workflow/equipment/'+self.eq).json()
        self.assertEqual(len(context['assignments']),1);self.assertEqual(context['tasks'][0]['status'],'scheduled')
        self.post(f"tasks/{task['id']}/status",{'status':'completed','notes':'invalid transition'},409)
        self.post(f"tasks/{task['id']}/status",{'status':'in_progress','notes':'Too early'},409)
        # Advance only the test API clock to exercise a real completion record.
        start=datetime.fromisoformat(preview['assignments'][0]['start'])+timedelta(minutes=61)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None): return start.astimezone(tz or timezone.utc)
        with patch('app.workflow.datetime',Clock):
            self.post(f"tasks/{task['id']}/status",{'status':'in_progress','notes':'Fixture started'},200)
            self.post(f"tasks/{task['id']}/status",{'status':'completed','notes':'Fixture inspection complete','actual_cost':'25.50'},200)
        context=self.client.get('/api/workflow/equipment/'+self.eq).json()
        self.assertEqual(len(context['history']),1);self.assertEqual(float(context['history'][0]['actual_cost']),25.50)
        self.post(f"tasks/{task['id']}/status",{'status':'completed','notes':'Duplicate completion'},409)

    def test_ai_snapshot_drives_priority(self):
        from app.schemas import Assessment
        payload={'equipment_id':self.eq,'risk_score':.95,'risk_level':'high','assessed_at':datetime.now(timezone.utc).isoformat(),
          'method':'Synthetic fixture','recommendation':'Prioritize review','limitation':'Synthetic test',
          'prediction':{'asset_tag':'test','predicted_annual_cost':500,'cost_error_range':149,'repair_rate_per_year':2,
          'risk_score':.95,'risk_level':'high','cumulative_cost_to_date':None,'projected_cost_next_years':2500,
          'projection_years':5,'assumed_replacement_cost':None,'maintenance_to_replacement_ratio':None,'warnings':[],'model_version':'fixture-v1'}}
        with patch('app.workflow.assess_equipment',return_value=Assessment.model_validate(payload)):
            task=self.task(use_assessment=True,priority_override=None,override_reason=None)
        self.assertEqual(task['priority'],'High');self.assertEqual(task['assessment']['prediction']['model_version'],'fixture-v1')
        self.technician();plan=self.preview([task['id']]);self.assertIn('95.0%',plan['assignments'][0]['priority_reason'])
        self.post(f"schedules/{plan['id']}/confirm",{},200)

    def test_conflicting_previews_and_concurrent_confirmation(self):
        self.technician();a=self.task();b=self.task(eq=self.create_equipment())
        plans=[self.preview([t['id']]) for t in [a,b]];barrier=Barrier(2)
        def confirm(p):
            barrier.wait()
            return TestClient(app).post('/api/workflow/schedules/'+p['id']+'/confirm',json={}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool: codes=list(pool.map(confirm,plans))
        self.assertEqual(sorted(codes),[200,409])

    def test_missing_qualification_and_validation(self):
        tech=self.technician();task=self.task(required_qualification='unavailable-'+self.token)
        plan=self.preview([task['id']]);self.assertEqual(plan['unscheduled'][0]['reason_code'],'NO_QUALIFIED_TECHNICIAN')
        self.post(f"schedules/{plan['id']}/confirm",{},422)
        self.post('tasks',{'equipment_id':self.eq},422)
        self.post('technicians',{'name':' ','qualifications':[]},422)
        self.post('tasks',{'equipment_id':str(uuid4()),'title':'Missing','duration_minutes':60,'required_qualification':self.token,'use_assessment':False,'priority_override':'High','override_reason':'test'},404)
        self.post(f"tasks/{task['id']}/status",{'status':'unknown','notes':'test'},422)
        # The unique qualification made only for this task is fixture-owned.
        with get_connection() as c:
            c.execute('DELETE FROM workflow_events WHERE task_id=%s',(task['id'],));c.execute('DELETE FROM workflow_tasks WHERE id=%s',(task['id'],))
            c.execute('DELETE FROM workflow_qualifications WHERE name=%s',('unavailable-'+self.token,))

    def test_changed_availability_invalidates_preview(self):
        tech=self.technician();task=self.task();plan=self.preview([task['id']])
        r=self.client.put('/api/workflow/technicians/'+tech['id'],json={'name':tech['name'],'qualifications':[self.token],
          'availability':[{'date':self.day,'start':'13:00','end':'17:00'}]})
        self.assertEqual(r.status_code,200,r.text)
        self.post(f"schedules/{plan['id']}/confirm",{},409)

    def test_database_guard_rejects_legacy_overlap(self):
        import psycopg
        with get_connection() as c:
            if not c.execute("SELECT to_regclass('maintenance_schedules') AS name").fetchone()['name']:
                self.skipTest('Legacy schedule table is absent.')
        self.technician();task=self.task();plan=self.preview([task['id']]);self.post(f"schedules/{plan['id']}/confirm",{},200)
        a=plan['assignments'][0]
        with self.assertRaises(psycopg.errors.ExclusionViolation):
            with get_connection() as c:
                c.execute("INSERT INTO maintenance_schedules(equipment_id,asset_tag,scheduled_start_time,scheduled_end_time,status,priority_score) VALUES (%s,%s,%s,%s,'scheduled',1)",
                  (self.eq,'CODEX-W10-LEGACY-'+self.token,a['start'],a['end']))

    def test_task_retry_is_idempotent(self):
        key=str(uuid4())
        first=self.task(request_id=key)
        second=self.task(request_id=key)
        self.assertEqual(first['id'],second['id'])
        body={'request_id':key,'equipment_id':self.eq,'title':'Changed','duration_minutes':60,
          'required_qualification':self.token,'use_assessment':False,'priority_override':'High','override_reason':'Explicit synthetic test priority'}
        self.post('tasks',body,409)

    def test_stale_equipment_and_technician_edit(self):
        tech=self.technician();task=self.task();plan=self.preview([task['id']]);self.post(f"schedules/{plan['id']}/confirm",{},200)
        r=self.client.put('/api/workflow/technicians/'+tech['id'],json={'name':'Updated','qualifications':[self.token],'availability':[]})
        self.assertEqual(r.status_code,409,r.text)
        fresh=self.task();p=self.preview([fresh['id']])
        with get_connection() as c: c.execute('UPDATE equipment SET updated_at=now() WHERE equipment_id=%s',(self.eq,))
        self.post(f"schedules/{p['id']}/confirm",{},409)

    @unittest.skipUnless(os.getenv('RUN_AI_TESTS')=='1','Start the AI service and set RUN_AI_TESTS=1 for real model integration.')
    def test_real_model_to_saved_assignment(self):
        self.technician();task=self.task(use_assessment=True,priority_override=None,override_reason=None)
        self.assertIsNotNone(task['assessment_id']);self.assertNotEqual(task['assessment']['prediction']['model_version'],'unreported')
        plan=self.preview([task['id']]);self.post(f"schedules/{plan['id']}/confirm",{},200)
        self.assertEqual(len(self.client.get('/api/workflow/equipment/'+self.eq).json()['assignments']),1)
