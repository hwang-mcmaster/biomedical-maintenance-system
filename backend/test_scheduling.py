import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from auth_test_support import TestClient, setup_identity
from app.main import app

E1 = '49e7403c-a464-44be-bc4c-c1741b53ec11'
E2 = '49e7403c-a464-44be-bc4c-c1741b53ec12'
DAY = '2030-11-05'


def task(identifier='task-1', equipment=E1, duration=60, priority='Medium', skill='Ventilator'):
    return dict(id=identifier, equipment_id=equipment, title='Inspection', priority=priority,
                required_qualification=skill, duration_minutes=duration)


def technician(identifier='tech-1', skill='Ventilator', windows=None):
    return dict(id=identifier, name=identifier, qualifications=[skill],
                availability=windows if windows is not None else [dict(start='09:00', end='13:00')])


def base():
    return dict(schedule_date=DAY, tasks=[task()], technicians=[technician()], existing_bookings=[])


def instant(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@patch('app.scheduling.repository.list_equipment')
class SchedulingTests(unittest.TestCase):
    def setUp(self):
        setup_identity(self)
        self.client = TestClient(app)

    def run_preview(self, lookup, payload):
        lookup.return_value = [{'id':E1, 'asset_tag':'SAVED-1'}, {'id':E2, 'asset_tag':'SAVED-2'}]
        return self.client.post('/api/scheduling/preview', json=payload)

    def assert_conflict_free(self, body):
        assigned = body['assignments']
        self.assertEqual(len({row['task_id'] for row in assigned}), len(assigned))
        for index, row in enumerate(assigned):
            self.assertEqual((instant(row['end']) - instant(row['start'])).total_seconds(), row['duration_minutes'] * 60)
            for other in assigned[index+1:]:
                if row['technician_id'] == other['technician_id'] or row['equipment_id'] == other['equipment_id']:
                    self.assertFalse(instant(row['start']) < instant(other['end']) and instant(other['start']) < instant(row['end']))

    def test_real_equipment_reference_and_no_persistence(self, lookup):
        result = self.run_preview(lookup, base())
        self.assertEqual(result.status_code,200,result.text)
        body = result.json()
        self.assertEqual(body['assignments'][0]['asset_tag'],'SAVED-1')
        self.assertFalse(body['persisted'])
        self.assertEqual(body['timezone'],'America/Toronto')
        self.assertEqual(result.headers['cache-control'],'no-store')
        lookup.assert_called_once()
        self.assert_conflict_free(body)

    def test_priority_wins_scarce_slot(self, lookup):
        payload = base()
        payload['tasks']=[task('low',priority='Low'),task('high',priority='High')]
        payload['technicians']=[technician(windows=[dict(start='09:00',end='10:00')])]
        body=self.run_preview(lookup,payload).json()
        self.assertEqual([a['task_id'] for a in body['assignments']],['high'])
        self.assertEqual(body['unscheduled'][0]['reason_code'],'RESOURCE_CONFLICT')

    def test_equipment_and_technician_never_double_booked(self, lookup):
        payload=base()
        payload['technicians']=[technician('A'),technician('B')]
        payload['tasks']=[task('one'),task('two'),task('three',equipment=E2)]
        body=self.run_preview(lookup,payload).json()
        self.assertEqual(len(body['assignments']),3)
        self.assert_conflict_free(body)
        same_equipment=[a for a in body['assignments'] if a['equipment_id']==E1]
        self.assertNotEqual(same_equipment[0]['start'],same_equipment[1]['start'])
        self.assertEqual(body['assignments'][0]['start'],body['assignments'][1]['start'])

    def test_bookings_and_breaks_respected(self, lookup):
        payload=base()
        payload['tasks']=[task(duration=90)]
        payload['technicians']=[technician(windows=[dict(start='09:00',end='12:00'),dict(start='13:00',end='17:00')])]
        payload['existing_bookings']=[dict(id='fixed',technician_id='tech-1',equipment_id=E1,start='09:00',end='11:00')]
        body=self.run_preview(lookup,payload).json()
        self.assertIn('T13:00:00',body['assignments'][0]['start'])
        self.assertIn('T14:30:00',body['assignments'][0]['end'])

    def test_case_insensitive_qualifications(self, lookup):
        payload=base()
        payload['technicians']=[technician(skill='  ventilator  ')]
        self.assertEqual(len(self.run_preview(lookup,payload).json()['assignments']),1)

    def test_unassigned_reasons(self, lookup):
        for change, code in [
            ({'technicians':[technician(skill='Other')]},'NO_QUALIFIED_TECHNICIAN'),
            ({'technicians':[technician(windows=[])]},'INSUFFICIENT_AVAILABILITY'),
            ({'technicians':[technician(windows=[dict(start='09:00',end='09:30'),dict(start='10:00',end='10:30')])]},'INSUFFICIENT_AVAILABILITY'),
        ]:
            with self.subTest(code=code):
                body=self.run_preview(lookup,base() | change).json()
                self.assertFalse(body['assignments'])
                self.assertEqual(body['unscheduled'][0]['reason_code'],code)

    def test_adjacent_tasks_fit_exactly(self, lookup):
        payload=base()
        payload['tasks']=[task('a',duration=30),task('b',duration=30)]
        payload['technicians']=[technician(windows=[dict(start='09:00',end='10:00')])]
        body=self.run_preview(lookup,payload).json()
        self.assertEqual(len(body['assignments']),2)
        self.assertEqual(body['assignments'][0]['end'],body['assignments'][1]['start'])
        self.assert_conflict_free(body)

    def test_request_validation(self, lookup):
        cases=[]
        for value in [0,-1,1.5,'60',1441]:
            p=base();p['tasks'][0]['duration_minutes']=value;cases.append(p)
        p=base();p['tasks']*=2;cases.append(p)
        p=base();p['technicians']*=2;cases.append(p)
        p=base();p['tasks'][0]['priority']='Critical';cases.append(p)
        p=base();p['technicians'][0]['availability']=[dict(start='09:00',end='12:00'),dict(start='11:00',end='13:00')];cases.append(p)
        p=base();p['technicians'][0]['availability']=[dict(start='17:00',end='09:00')];cases.append(p)
        p=base();p['technicians'][0]['availability']=[dict(start='09:00Z',end='12:00Z')];cases.append(p)
        p=base();p['existing_bookings']=[dict(id='b',equipment_id=E1,technician_id='missing',start='09:00',end='10:00')];cases.append(p)
        p=base();p['schedule_date']='2000-01-01';cases.append(p)
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.run_preview(lookup,payload).status_code,422)

    def test_missing_equipment_is_not_scheduled(self, lookup):
        payload=base();payload['tasks'][0]['equipment_id']='49e7403c-a464-44be-bc4c-c1741b53ec99'
        result=self.run_preview(lookup,payload)
        self.assertEqual(result.status_code,404)

    def test_conflicting_existing_bookings_rejected(self, lookup):
        for shared in ['technician','equipment']:
            payload=base();payload['technicians']=[technician('A'),technician('B')]
            payload['existing_bookings']=[
                dict(id='a',technician_id='A',equipment_id=E1,start='09:00',end='10:00'),
                dict(id='b',technician_id='A' if shared=='technician' else 'B',equipment_id=E2 if shared=='technician' else E1,start='09:30',end='10:30'),
            ]
            self.assertEqual(self.run_preview(lookup,payload).status_code,422)

    def test_deterministic_ties(self, lookup):
        payload=base();payload['technicians']=[technician('B'),technician('A')]
        first=self.run_preview(lookup,payload).json()['assignments']
        payload['technicians'].reverse()
        second=self.run_preview(lookup,payload).json()['assignments']
        self.assertEqual(first,second)
        self.assertEqual(first[0]['technician_id'],'A')

    def test_dst_ambiguous_and_nonexistent_inputs_rejected(self, lookup):
        for day in ['2030-03-10','2030-11-03']:
            payload=base();payload['schedule_date']=day
            payload['technicians'][0]['availability']=[dict(start='02:30' if '03-10' in day else '01:30',end='04:00')]
            self.assertEqual(self.run_preview(lookup,payload).status_code,422)

    def test_dst_duration_is_elapsed_time(self, lookup):
        payload=base();payload['schedule_date']='2030-11-03'
        payload['tasks'][0]['duration_minutes']=240
        payload['technicians'][0]['availability']=[dict(start='00:00',end='04:00')]
        response=self.run_preview(lookup,payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assert_conflict_free(response.json())
        self.assertIn('T03:00:00-05:00',response.json()['assignments'][0]['end'])


if __name__ == '__main__':
    unittest.main()
