import unittest
from unittest.mock import MagicMock, patch
import psycopg
from fastapi.testclient import TestClient
from app.main import app

class EquipmentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = dict(name='Pump', type='Infusion', location='ICU', status='Operational')

    def test_validation(self):
        for change in ({'name': '  '}, {'status': 'Maintenance Due'}, {'location': None}, {'id': 2}):
            with self.subTest(change=change):
                self.assertEqual(self.client.post('/api/equipment', json=self.payload | change).status_code, 422)
        self.assertEqual(self.client.post('/api/equipment', json={}).status_code, 422)

    @patch('app.main.get_connection')
    def test_create_and_list_contract(self, connect):
        connection = connect.return_value.__enter__.return_value
        record = self.payload | {'id': 42}
        connection.execute.return_value.fetchone.return_value = record
        result = self.client.post('/api/equipment', json=self.payload | {'name': ' Pump '})
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json(), record)
        self.assertEqual(connection.execute.call_args.args[1][0], 'Pump')
        connection.execute.return_value.fetchall.return_value = [record]
        self.assertEqual(self.client.get('/api/equipment').json(), [record])

    @patch('app.main.get_connection', side_effect=psycopg.OperationalError('secret-password'))
    def test_unavailable_does_not_leak_secrets(self, connect):
        for response in (self.client.get('/api/equipment'), self.client.post('/api/equipment', json=self.payload)):
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret-password', response.text)

if __name__ == '__main__':
    unittest.main()
