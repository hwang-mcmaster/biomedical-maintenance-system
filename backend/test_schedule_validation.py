import copy
import unittest
from datetime import date
from pydantic import ValidationError
from app.scheduling import generate_schedule
from app.scheduling_schemas import ScheduleRequest
from app.schedule_validation import inspect_schedule, schedule_metrics
from app.workflow_schemas import TaskInput
from test_scheduling import base, task, technician, E1, E2


class ValidationTests(unittest.TestCase):
    def inputs(self):
        payload=base()
        payload['tasks']=[task('low',priority='Low'),task('high',equipment=E2,priority='High')]
        for t in payload['tasks']: t['due_date']='2030-11-05'
        payload['technicians']=[technician(windows=[dict(start='09:00',end='10:00')])]
        return ScheduleRequest.model_validate(payload)

    def test_risk_and_baseline_same_constraints(self):
        request=self.inputs();equipment={E1:{'asset_tag':'A'},E2:{'asset_tag':'B'}}
        risk=generate_schedule(request,equipment).model_dump(mode='json')
        fixed=generate_schedule(request,equipment,strategy='fixed_interval').model_dump(mode='json')
        self.assertEqual(risk['assignments'][0]['task_id'],'high')
        # Equal due dates use IDs, so rename to prove the baseline ignores risk.
        request.tasks[0].id='aaa-low'
        fixed=generate_schedule(request,equipment,strategy='fixed_interval').model_dump(mode='json')
        self.assertEqual(fixed['assignments'][0]['task_id'],'aaa-low')
        self.assertTrue(inspect_schedule(request,fixed)['passed'])

    def test_corrupt_outputs_fail_independent_checks(self):
        request=self.inputs();equipment={E1:{'asset_tag':'A'},E2:{'asset_tag':'B'}}
        result=generate_schedule(request,equipment).model_dump(mode='json')
        cases=[]
        bad=copy.deepcopy(result);bad['assignments'][0]['end']='2030-11-05T10:30:00-05:00';cases.append(bad)
        bad=copy.deepcopy(result);bad['assignments'][0]['equipment_id']=E1;cases.append(bad)
        bad=copy.deepcopy(result);bad['assignments'][0]['technician_id']='missing';cases.append(bad)
        bad=copy.deepcopy(result);bad['unscheduled']=[];cases.append(bad)
        for bad in cases: self.assertFalse(inspect_schedule(request,bad)['passed'])
        booking=[('tech-1',E2,'2030-11-05T09:30:00-05:00','2030-11-05T10:30:00-05:00')]
        self.assertFalse(inspect_schedule(request,result,booking)['passed'])
        request.technicians[0].qualifications=['other']
        self.assertFalse(inspect_schedule(request,result)['passed'])

    def test_due_date_breaks_priority_tie_and_late_intervals_are_measured(self):
        payload=base();payload['tasks']=[task('aaa'),task('zzz',equipment=E2)]
        payload['tasks'][0]['due_date']='2030-11-06'
        payload['tasks'][1].update(due_date='2030-11-04',service_due_date='2030-11-04')
        payload['technicians']=[technician(windows=[dict(start='09:00',end='10:00')])]
        request=ScheduleRequest.model_validate(payload)
        result=generate_schedule(request,{E1:{'asset_tag':'A'},E2:{'asset_tag':'B'}}).model_dump(mode='json')
        self.assertEqual(result['assignments'][0]['task_id'],'zzz')
        metrics=schedule_metrics(request,result)
        self.assertEqual(metrics['service_interval_scheduled_late'],1)
        self.assertEqual(metrics['selected_task_utilization_percent'],100)

    def test_service_interval_validation(self):
        valid=dict(equipment_id=E1,title='Review',duration_minutes=60,required_qualification='ventilator',
                   use_assessment=False,priority_override='High',override_reason='Approved review')
        for change in [dict(last_service_date='2020-01-01'),dict(service_interval_days=30),
                       dict(last_service_date='2999-01-01',service_interval_days=30),
                       dict(last_service_date='2020-01-01',service_interval_days=0),
                       dict(last_service_date='2020-01-01',service_interval_days=30,due_date='2030-01-01')]:
            with self.assertRaises(ValidationError): TaskInput(**(valid|change))
        body=TaskInput(**(valid|dict(last_service_date=date(2020,1,1),service_interval_days=30)))
        self.assertEqual(body.service_interval_days,30)
