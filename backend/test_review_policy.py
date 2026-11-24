import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
from pydantic import ValidationError
from fastapi import HTTPException
from app.schemas import EquipmentCreate
from app.decision_policy import recommendation_policy, criticality_priority, CATEGORIES
from app.workflow_extensions import PolicyInput, AssignmentEdit, ReconcileInput, reconcile, coordinator, reschedule


class ReviewPolicyTests(unittest.TestCase):
    def test_all_four_categories_and_replacement_precedence(self):
        device=SimpleNamespace(expected_useful_life=None,in_service_date=date(2020,1,1),calculated_as_of=date(2026,1,1))
        prediction=SimpleNamespace(maintenance_to_replacement_ratio=None,risk_level='low')
        for level,category in zip(('low','medium','high'),CATEGORIES):
            prediction.risk_level=level
            self.assertEqual(recommendation_policy(device,prediction)[0],category)
        prediction.risk_level='low'; prediction.maintenance_to_replacement_ratio=1
        self.assertEqual(recommendation_policy(device,prediction)[0],CATEGORIES[3])
        prediction.maintenance_to_replacement_ratio=None;device.expected_useful_life=5
        self.assertEqual(recommendation_policy(device,prediction)[0],CATEGORIES[3])

    def test_criticality_floor_never_reduces_priority(self):
        for priority in ('Low','Medium','High'):
            self.assertEqual(criticality_priority(priority,'Critical'),'High')
        self.assertEqual(criticality_priority('Low','Important'),'Medium')
        self.assertEqual(criticality_priority('High','Routine'),'High')
        self.assertEqual(criticality_priority('Low',None),'Low')

    def test_strict_policy_and_assignment_inputs(self):
        base=dict(title='Service',interval_days=30,last_service_date='2020-01-01',duration_minutes=60,required_qualification='ventilator',priority='Medium',source='Approved manual')
        for change in ({'interval_days':0},{'last_service_date':'2999-01-01'},{'duration_minutes':0},{'source':'  '}):
            with self.assertRaises(ValidationError): PolicyInput(**(base|change))
        with self.assertRaises(ValidationError):
            AssignmentEdit(technician_id=uuid4(),expected_technician_id=uuid4(),date='2030-01-01',start='09:00',expected_start='2030-01-01T09:00:00',reason='Reviewed change')

    def test_reconciliation_is_idempotent_and_role_guarded(self):
        request=SimpleNamespace(state=SimpleNamespace(user={'id':uuid4(),'role':'coordinator'}))
        c=MagicMock();c.execute.return_value.fetchone.return_value={'aggregates_applied':True}
        with patch('app.workflow_extensions.get_connection') as connection:
            connection.return_value.__enter__.return_value=c
            result=reconcile(uuid4(),ReconcileInput(repair_event=True,reason='Not previously included'),request)
        self.assertTrue(result['already_applied'])
        self.assertFalse(any('UPDATE equipment' in call.args[0] for call in c.execute.call_args_list))
        request.state.user['role']='technician'
        with self.assertRaises(HTTPException): coordinator(request)

    def test_openapi_includes_review_and_reschedule_without_connection_parameter(self):
        from app.main import app
        schema=app.openapi()
        self.assertIn('/api/workflow/assignments/{assignment_id}/reschedule',schema['paths'])
        params=schema['paths']['/api/workflow/tasks']['post'].get('parameters',[])
        self.assertFalse(any(p['name']=='connection' for p in params))

    def test_reschedule_rejects_stale_and_late_changes_before_writing(self):
        start=datetime(2030,1,1,14,tzinfo=timezone.utc)
        body=AssignmentEdit(technician_id=uuid4(),expected_technician_id=uuid4(),date='2030-01-02',start='09:00',expected_start=start,reason='Reviewed change')
        row=dict(technician_id=body.expected_technician_id,status='scheduled',starts_at=start,equipment_version=start,current_version=start,
                 duration_minutes=60,request_payload={},due_date=date(2030,1,1))
        request=SimpleNamespace(state=SimpleNamespace(user={'id':uuid4(),'role':'coordinator'}))
        for change,code in (({'status':'in_progress'},409),({},422),({'current_version':datetime(2030,1,2,tzinfo=timezone.utc)},409)):
            c=MagicMock();c.execute.return_value.fetchone.return_value=row|change
            with patch('app.workflow_extensions.get_connection') as connection:
                connection.return_value.__enter__.return_value=c
                with self.assertRaises(HTTPException) as error: reschedule(uuid4(),body,request)
                self.assertEqual(error.exception.status_code,code)
            self.assertFalse(any('UPDATE workflow_assignments' in call.args[0] for call in c.execute.call_args_list))

    def test_recurring_generation_uses_cycle_key_and_shared_transaction(self):
        from app.workflow_extensions import recurring_task
        equipment_id=uuid4();c=MagicMock();request=MagicMock()
        policy=dict(active=True,last_service_date=date(2020,1,1),interval_days=30,
            title='Service',duration_minutes=60,required_qualification='ventilator',priority='Medium',source='Approved interval')
        c.execute.return_value.fetchone.side_effect=[policy,None,policy,None]
        with patch('app.workflow_extensions.create_task_in_transaction',return_value={'id':uuid4()}) as create:
            recurring_task(c,equipment_id,request);recurring_task(c,equipment_id,request)
            first,second=create.call_args_list
            self.assertEqual(first.args[0].request_id,second.args[0].request_id)
            self.assertIs(first.kwargs['connection'],c)

    def test_policy_completion_creates_next_cycle_in_same_transaction(self):
        from app.workflow import change_status
        from app.workflow_schemas import StatusInput
        task_id,equipment_id=uuid4(),uuid4()
        task=dict(id=task_id,equipment_id=equipment_id,status='in_progress',recurring_due=date(2020,1,31))
        policy=dict(active=True,last_service_date=date(2020,1,1),interval_days=30)
        c=MagicMock()
        def execute(sql,*args):
            result=MagicMock()
            if sql.startswith('SELECT * FROM workflow_tasks'): result.fetchone.return_value=task
            elif sql.startswith('SELECT * FROM workflow_assignments'): result.fetchone.return_value={'starts_at':datetime(2020,1,1,tzinfo=timezone.utc)}
            elif sql.startswith('SELECT * FROM workflow_service_policies'): result.fetchone.return_value=policy
            return result
        c.execute.side_effect=execute
        request=SimpleNamespace(state=SimpleNamespace(user={'id':uuid4(),'role':'coordinator'}))
        with patch('app.workflow.get_connection') as connection, patch('app.workflow_extensions.recurring_task') as recurring:
            connection.return_value.__enter__.return_value=c
            change_status(task_id,StatusInput(status='completed',notes='Service finished',actual_cost='30.00'),request)
            recurring.assert_called_once_with(c,equipment_id,request)
        self.assertTrue(any('INSERT INTO workflow_history' in call.args[0] for call in c.execute.call_args_list))
