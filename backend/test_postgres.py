"""Opt-in PostgreSQL integration tests. Only generated test records are removed."""
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from app.main import app
from test_equipment import PAYLOAD


@unittest.skipUnless(os.getenv('RUN_POSTGRES_TESTS') == '1', 'Set RUN_POSTGRES_TESTS=1 to test the configured PostgreSQL database.')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.ids = []
        token = uuid4().hex
        self.payload = PAYLOAD | {'asset_tag': f'CODEX-TEST-{token}', 'serial_number': f'CODEX-TEST-{token}'}

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
        self.assertIn(equipment_id, [row['id'] for row in self.client.get('/api/equipment').json()])
        self.assertEqual(self.client.post('/api/equipment', json=self.payload).status_code, 409)
        response = self.client.put(path, json=self.payload | {'location': 'Test lab', 'status': 'Under Maintenance'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(path).json()['status'], 'Under Maintenance')
        self.assertEqual(self.client.get(path).json()['location'], 'Test lab')
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    @unittest.skipUnless(os.getenv('RUN_AI_TESTS') == '1', 'Set RUN_AI_TESTS=1 with the AI service running.')
    def test_saved_equipment_through_real_ai_service(self):
        equipment_id = self.create()
        response = self.client.post(f'/api/equipment/{equipment_id}/assessment')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['prediction']['asset_tag'], self.payload['asset_tag'])
        self.assertGreaterEqual(response.json()['prediction']['predicted_annual_cost'], 0)
        self.assertIn('synthetic', response.json()['limitation'])
