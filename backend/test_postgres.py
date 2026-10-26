"""Opt-in PostgreSQL integration tests. Only generated test records are removed."""
import os
import unittest
from uuid import uuid4
from decimal import Decimal
import psycopg
from app.database import get_connection

from fastapi.testclient import TestClient
from app.main import app
from test_equipment import PAYLOAD


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1 to test the configured PostgreSQL database.')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.ids = []
        token = uuid4().hex
        self.payload = PAYLOAD | {'asset_tag': f'CODEX-TEST-{token}', 'serial_number': f'000{token}'}

    def tearDown(self):
        for equipment_id in self.ids:
            response = self.client.delete(f'/api/equipment/{equipment_id}')
            self.assertIn(response.status_code, [204, 404], response.text)

    def create(self):
        response = self.client.post('/api/equipment', json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        equipment_id = response.json()['id']
        self.ids.append(equipment_id)
        return equipment_id

    def test_persistence_update_uniqueness_and_delete(self):
        self.assertEqual(self.client.get('/api/ready').status_code, 200)
        equipment_id = self.create()
        path = f'/api/equipment/{equipment_id}'
        # Each request uses a separate real connection: confirms committed persistence.
        self.assertEqual(self.client.get(path).json()['asset_tag'], self.payload['asset_tag'])
        self.assertEqual(self.client.get(path).json()['serial_number'], self.payload['serial_number'])
        self.assertIn(equipment_id, [row['id'] for row in self.client.get('/api/equipment').json()])
        self.assertEqual(self.client.post('/api/equipment', json=self.payload).status_code, 409)
        response = self.client.put(path, json=self.payload | {'in_service_date': '2020-01-01', 'repair_events': 12, 'total_historical_cost': '5678.90'})
        self.assertEqual(response.status_code, 200, response.text)
        retrieved = self.client.get(path).json()
        self.assertEqual(retrieved['in_service_date'], '2020-01-01')
        self.assertEqual(Decimal(retrieved['total_historical_cost']), Decimal('5678.90'))
        self.assertEqual(retrieved['repair_events'], 12)
        from app.calculations import exact_age, annual_average, reference_date
        from datetime import date
        age = exact_age(date(2020, 1, 1), reference_date())
        self.assertEqual(Decimal(retrieved['avg_annual_cost']), annual_average(Decimal('5678.90'), age))
        with get_connection() as connection:
            for column, invalid in [('repair_events', '-1'), ('total_historical_cost', '-1'), ('in_service_date', reference_date().isoformat())]:
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with connection.transaction():
                        connection.execute(psycopg.sql.SQL('UPDATE equipment SET {}=%s WHERE equipment_id=%s').format(psycopg.sql.Identifier(column)), (invalid, equipment_id))
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    @unittest.skipUnless(os.getenv('RUN_AI_TESTS') == '1', 'Set RUN_AI_TESTS=1 with the AI service running.')
    def test_saved_equipment_through_real_ai_service(self):
        equipment_id = self.create()
        response = self.client.get(f'/api/equipment/{equipment_id}/assessment')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['equipment_id'], equipment_id)
        self.assertEqual(response.json()['risk_score'], response.json()['prediction']['risk_score'])
        self.assertTrue(0 <= response.json()['risk_score'] <= 1)
        self.assertTrue(response.json()['recommendation'])
        self.assertEqual(response.json()['prediction']['asset_tag'], self.payload['asset_tag'])
        self.assertGreaterEqual(response.json()['prediction']['predicted_annual_cost'], 0)
        self.assertIn('synthetic', response.json()['limitation'])

    def test_defaults_and_legacy_snapshots_ignored(self):
        payload = {key: value for key, value in self.payload.items() if key not in ['repair_events', 'total_historical_cost']}
        response = self.client.post('/api/equipment', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        equipment_id = response.json()['id']
        self.ids.append(equipment_id)
        self.assertEqual(response.json()['repair_events'], 0)
        self.assertEqual(Decimal(response.json()['avg_annual_cost']), 0)
        # The migrated RDS retains old snapshots; writing those must not affect reads.
        with get_connection() as connection:
            columns = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='equipment'").fetchall()
            if {'age_years', 'avg_annual_cost'} <= {row['column_name'] for row in columns}:
                connection.execute('UPDATE equipment SET age_years=99, avg_annual_cost=999 WHERE equipment_id=%s', (equipment_id,))
        retrieved = self.client.get(f'/api/equipment/{equipment_id}').json()
        self.assertNotEqual(Decimal(retrieved['age_years']), 99)
        self.assertEqual(Decimal(retrieved['avg_annual_cost']), 0)
