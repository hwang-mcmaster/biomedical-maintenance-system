import csv
import io
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import httpx
import psycopg
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Equipment, EquipmentCreate
from app.calculations import exact_age, annual_average, reference_date

ID = '49e7403c-a464-44be-bc4c-c1741b53ec11'
PAYLOAD = dict(asset_tag='TEST-1', serial_number='0000123', manufacturer='Getinge SERVOi',
               in_service_date='2003-03-03', repair_events=19, total_historical_cost='9678.12')
PREDICTION = dict(asset_tag='TEST-1', predicted_annual_cost=600, cost_error_range=149.08,
                  repair_rate_per_year=1.5, risk_score=0.8, risk_level='high',
                  cumulative_cost_to_date=1000, projected_cost_next_years=3000,
                  projection_years=5, assumed_replacement_cost=None,
                  maintenance_to_replacement_ratio=None, warnings=['Example model warning'])


class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.record = PAYLOAD | {'id': ID}

    def test_validation(self):
        for change in ({'asset_tag': '  '}, {'serial_number': 123}, {'manufacturer': None},
                       {'id': ID}, {'repair_events': -1}, {'repair_events': 1.5},
                       {'repair_events': '5'}, {'total_historical_cost': -1},
                       {'total_historical_cost': 'NaN'}, {'total_historical_cost': 'Infinity'},
                       {'total_historical_cost': '1.234'}, {'in_service_date': '2999-01-01'},
                       {'in_service_date': reference_date().isoformat()},
                       {'manufacturer': 'x' * 101}, {'age_years': 5}, {'avg_annual_cost': 10},
                       {'calculated_as_of': '2020-01-01'}, {'name': 'Legacy field'}):
            for method, path in [('post', '/api/equipment'), ('put', f'/api/equipment/{ID}')]:
                with self.subTest(change=change, method=method):
                    self.assertEqual(getattr(self.client, method)(path, json=PAYLOAD | change).status_code, 422)
        for field in ['asset_tag', 'serial_number', 'manufacturer', 'in_service_date']:
            incomplete = {key: value for key, value in PAYLOAD.items() if key != field}
            self.assertEqual(self.client.post('/api/equipment', json=incomplete).status_code, 422)
        self.assertEqual(self.client.get('/api/equipment/not-a-uuid').status_code, 422)

    def test_default_counts_and_cost(self):
        payload = {key: value for key, value in PAYLOAD.items() if key not in ['repair_events', 'total_historical_cost']}
        device = EquipmentCreate.model_validate(payload)
        self.assertEqual(device.repair_events, 0)
        self.assertEqual(device.total_historical_cost, Decimal('0.00'))
        self.assertEqual(len(EquipmentCreate.model_fields), 6)

    def test_calculations_and_zero_age(self):
        # One day rounds to 0.00 years, but division uses the unrounded age.
        device = Equipment.model_validate(self.record | {
            'in_service_date': '2020-01-01', 'calculated_as_of': date(2020, 1, 2),
            'total_historical_cost': '100.00',
        })
        self.assertEqual(device.age_years, Decimal('0.00'))
        self.assertEqual(device.avg_annual_cost, Decimal('36525.00'))
        zero = device.model_copy(update={'calculated_as_of': date(2020, 1, 1)})
        self.assertIsNone(zero.avg_annual_cost)
        self.assertEqual(zero.age_years, Decimal('0.00'))
        changed = device.model_copy(update={'calculated_as_of': date(2021, 1, 1)})
        self.assertNotEqual(changed.age_years, device.age_years)
        self.assertNotEqual(changed.avg_annual_cost, device.avg_annual_cost)

    @patch('app.repository.save_equipment')
    @patch('app.repository.get_equipment')
    @patch('app.repository.list_equipment')
    @patch('app.repository.delete_equipment')
    def test_crud_contract(self, delete, listing, get, save):
        listing.return_value = [self.record]
        get.return_value = save.return_value = self.record
        delete.return_value = {'equipment_id': ID}
        response = self.client.post('/api/equipment', json=PAYLOAD | {'asset_tag': ' TEST-1 '})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(save.call_args.args[0].asset_tag, 'TEST-1')
        body = response.json()
        self.assertEqual(body['serial_number'], '0000123')
        self.assertEqual(body['calculated_as_of'], reference_date().isoformat())
        self.assertEqual(set(body), set(PAYLOAD) | {'id', 'calculated_as_of', 'age_years', 'avg_annual_cost'})
        age = exact_age(date(2003, 3, 3), reference_date())
        self.assertEqual(Decimal(body['avg_annual_cost']), annual_average(Decimal('9678.12'), age))
        self.assertEqual(self.client.get('/api/equipment').json()[0]['id'], ID)
        self.assertEqual(self.client.get(f'/api/equipment/{ID}').status_code, 200)
        self.assertEqual(self.client.put(f'/api/equipment/{ID}', json=PAYLOAD).status_code, 200)
        self.assertEqual(self.client.delete(f'/api/equipment/{ID}').status_code, 204)

    @patch('app.repository.list_equipment')
    @patch('app.main.reference_date', return_value=date(2020, 1, 2))
    def test_dated_training_export(self, today, listing):
        listing.return_value = [self.record | {'in_service_date': '2020-01-01', 'total_historical_cost': '100.00'}]
        response = self.client.get('/api/equipment/export')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['x-calculated-as-of'], '2020-01-02')
        self.assertIn('2020-01-02', response.headers['content-disposition'])
        row = list(csv.DictReader(io.StringIO(response.text)))[0]
        self.assertEqual(len(row), 8)
        self.assertEqual(row['serial_number'], '0000123')
        self.assertEqual(row['age_years'], '0.00')
        self.assertEqual(row['avg_annual_cost'], '36525.00')

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
    def test_assessment_uses_unrounded_age(self, client, get):
        get.return_value = self.record | {'in_service_date': '2020-01-01'}
        client.return_value.__enter__.return_value.post.return_value.json.return_value = PREDICTION
        result = self.client.get(f'/api/equipment/{ID}/assessment')
        self.assertEqual(result.status_code, 200, result.text)
        body = result.json()
        self.assertEqual(body['equipment_id'], ID)
        self.assertEqual(body['risk_score'], 0.8)
        self.assertEqual(result.headers['cache-control'], 'no-store')
        self.assertIn('Prioritize', body['recommendation'])
        sent = client.return_value.__enter__.return_value.post.call_args.kwargs['json']
        self.assertEqual(sent['age_years'], float(exact_age(date(2020, 1, 1), reference_date())))
        self.assertNotIn('avg_annual_cost', sent)
        self.assertEqual(self.client.post(f'/api/equipment/{ID}/assessment').status_code, 200)

    @patch('app.repository.get_equipment')
    @patch('app.assessment.httpx.Client')
    def test_assessment_failure(self, client, get):
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
    def test_zero_elapsed_age_assessment(self, client, get):
        get.return_value = self.record | {'in_service_date': reference_date()}
        self.assertEqual(self.client.get(f'/api/equipment/{ID}/assessment').status_code, 422)
        client.assert_not_called()

    def test_cors_and_health(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)
        response = self.client.options(f'/api/equipment/{ID}', headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'PUT',
            'Access-Control-Request-Headers': 'content-type',
        })
        self.assertEqual(response.status_code, 200)
