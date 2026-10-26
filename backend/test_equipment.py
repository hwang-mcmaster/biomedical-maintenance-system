import unittest
from datetime import date
from unittest.mock import patch
from uuid import UUID

import httpx
import psycopg
from fastapi.testclient import TestClient

from app.main import app

ID = '49e7403c-a464-44be-bc4c-c1741b53ec11'
PAYLOAD = dict(asset_tag='TEST-1', serial_number='0000123', manufacturer='Getinge SERVOi',
               in_service_date='2003-03-03', age_years='23.380', repair_events=19,
               total_historical_cost='9678.12', avg_annual_cost='413.95')
PREDICTION = dict(asset_tag='TEST-1', predicted_annual_cost=600, cost_error_range=149.08,
                  repair_rate_per_year=1.5, risk_score=0.8, risk_level='high',
                  cumulative_cost_to_date=1000, projected_cost_next_years=3000,
                  projection_years=5, assumed_replacement_cost=20000,
                  maintenance_to_replacement_ratio=0.05, warnings=['Example model warning'])


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.record = PAYLOAD | {'id': ID}

    def test_validation(self):
        for change in ({'asset_tag': '  '}, {'serial_number': 123}, {'manufacturer': None},
                       {'id': ID}, {'repair_events': -1}, {'repair_events': 1.5},
                       {'repair_events': '5'}, {'total_historical_cost': -1},
                       {'avg_annual_cost': -1}, {'age_years': -1}, {'age_years': 'NaN'},
                       {'age_years': 'Infinity'}, {'age_years': '1.2345'},
                       {'avg_annual_cost': '1.234'}, {'total_historical_cost': 'Infinity'},
                       {'in_service_date': '2999-01-01'}, {'manufacturer': 'x' * 101},
                       {'name': 'Removed legacy field'}, {'status': 'Operational'},
                       {'assumed_replacement_cost': 20000}):
            for method, path in [('post', '/api/equipment'), ('put', f'/api/equipment/{ID}')]:
                with self.subTest(change=change, method=method):
                    self.assertEqual(getattr(self.client, method)(path, json=PAYLOAD | change).status_code, 422)
        self.assertEqual(self.client.post('/api/equipment', json={}).status_code, 422)
        for field in PAYLOAD:
            incomplete = {key: value for key, value in PAYLOAD.items() if key != field}
            self.assertEqual(self.client.post('/api/equipment', json=incomplete).status_code, 422, field)
        self.assertEqual(self.client.get('/api/equipment/not-a-uuid').status_code, 422)

    @patch('app.repository.save_equipment')
    @patch('app.repository.get_equipment')
    @patch('app.repository.list_equipment')
    @patch('app.repository.delete_equipment')
    def test_crud_contract(self, delete, listing, get, save):
        listing.return_value = [self.record]
        get.return_value = save.return_value = self.record
        delete.return_value = {'equipment_id': ID}
        response = self.client.post('/api/equipment', json=PAYLOAD | {'asset_tag': ' TEST-1 '})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['id'], ID)
        self.assertEqual(save.call_args.args[0].asset_tag, 'TEST-1')
        self.assertEqual(response.json()['serial_number'], '0000123')
        self.assertEqual(response.json()['age_years'], '23.380')
        self.assertEqual(response.json()['avg_annual_cost'], '413.95')
        self.assertEqual(set(response.json()), set(PAYLOAD) | {'id'})
        self.assertEqual(self.client.get('/api/equipment').json()[0]['id'], ID)
        self.assertEqual(self.client.get(f'/api/equipment/{ID}').status_code, 200)
        self.assertEqual(self.client.put(f'/api/equipment/{ID}', json=PAYLOAD).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/equipment/{ID}').status_code, 204)

    def test_missing_records(self):
        for method, name in [('get', 'get_equipment'), ('put', 'save_equipment'), ('delete', 'delete_equipment')]:
            with patch(f'app.repository.{name}', return_value=None):
                kwargs = {'json': PAYLOAD} if method == 'put' else {}
                self.assertEqual(getattr(self.client, method)(f'/api/equipment/{ID}', **kwargs).status_code, 404)
        with patch('app.repository.get_equipment', return_value=None):
            self.assertEqual(self.client.get(f'/api/equipment/{ID}/assessment').status_code, 404)

    def test_database_failures_are_safe(self):
        for error, expected in [(psycopg.OperationalError('secret-password'), 503),
                                (RuntimeError('secret-password'), 503),
                                (psycopg.errors.UniqueViolation('private-value'), 409),
                                (psycopg.errors.ForeignKeyViolation('private-value'), 409)]:
            with patch('app.repository.save_equipment', side_effect=error):
                response = self.client.post('/api/equipment', json=PAYLOAD)
                self.assertEqual(response.status_code, expected)
                self.assertNotIn('secret-password', response.text)
                self.assertNotIn('private-value', response.text)

    @patch('app.repository.get_equipment')
    @patch('app.assessment.httpx.Client')
    def test_assessment_uses_saved_data_and_ai(self, client, get):
        get.return_value = self.record
        response = client.return_value.__enter__.return_value.post.return_value
        response.json.return_value = PREDICTION
        result = self.client.get(f'/api/equipment/{ID}/assessment')
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body['equipment_id'], ID)
        self.assertEqual(body['risk_score'], 0.8)
        self.assertEqual(body['risk_level'], 'high')
        self.assertEqual(body['risk_score'], body['prediction']['risk_score'])
        self.assertEqual(result.headers['cache-control'], 'no-store')
        legacy = self.client.post(f'/api/equipment/{ID}/assessment')
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.json()['risk_score'], body['risk_score'])
        self.assertEqual(body['prediction']['risk_level'], 'high')
        self.assertIn('Prioritize', body['recommendation'])
        self.assertIn('synthetic', body['limitation'])
        sent = client.return_value.__enter__.return_value.post.call_args.kwargs['json']
        self.assertEqual(sent['repair_events'], 19)
        self.assertEqual(sent['manufacturer'], PAYLOAD['manufacturer'])
        self.assertEqual(sent['age_years'], 23.38)
        self.assertNotIn('avg_annual_cost', sent)
        self.assertNotIn('assumed_replacement_cost', sent)

    @patch('app.repository.get_equipment')
    @patch('app.assessment.httpx.Client')
    def test_assessment_unavailable_or_invalid_response(self, client, get):
        get.return_value = self.record
        post = client.return_value.__enter__.return_value.post
        post.side_effect = httpx.ConnectError('internal-host')
        response = self.client.get(f'/api/equipment/{ID}/assessment')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('internal-host', response.text)
        post.side_effect = None
        post.return_value.json.return_value = {'unexpected': True}
        self.assertEqual(self.client.get(f'/api/equipment/{ID}/assessment').status_code, 503)

    @patch('app.repository.get_equipment')
    @patch('app.assessment.httpx.Client')
    def test_zero_age_assessment(self, client, get):
        for change in ({'age_years': '0'},):
            get.return_value = self.record | change
            self.assertEqual(self.client.get(f'/api/equipment/{ID}/assessment').status_code, 422)
        client.assert_not_called()

    def test_cors_and_health(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        response = self.client.options(f'/api/equipment/{ID}', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'PUT',
            'Access-Control-Request-Headers': 'content-type',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('PUT', response.headers['access-control-allow-methods'])


if __name__ == '__main__':
    unittest.main()
