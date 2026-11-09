"""Lifecycle checks use mocks and never connect to the project database."""
import os
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from ai.app import main


class SchedulerLifecycleTests(unittest.TestCase):
    def check_disabled(self, settings):
        with patch.dict(os.environ, settings, clear=True), \
             patch.object(main, 'sweep_overdue_schedules') as sweep, \
             patch.object(main, 'AsyncIOScheduler') as scheduler, \
             patch.object(main, 'load_model', return_value=(Mock(), {})):
            with TestClient(main.app) as client:
                self.assertEqual(client.get('/api/ai/health').status_code, 200)
                self.assertFalse(main.scheduler_enabled())
            sweep.assert_not_called()
            scheduler.assert_not_called()

    def test_missing_setting_disables_all_background_work(self):
        self.check_disabled({})

    def test_false_disables_all_background_work(self):
        self.check_disabled({'SCHEDULER_ENABLED': ' false '})

    def test_enabled_registers_hourly_job_and_stops_on_shutdown(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': ' TRUE '}), \
             patch.object(main, 'sweep_overdue_schedules') as sweep, \
             patch.object(main, 'AsyncIOScheduler') as factory:
            scheduler = factory.return_value
            with TestClient(main.app):
                sweep.assert_called_once_with()
                factory.assert_called_once_with()
                scheduler.add_job.assert_called_once_with(
                    main.run_maintenance_schedule_optimizer, 'interval', minutes=60)
                scheduler.start.assert_called_once_with()
                scheduler.shutdown.assert_not_called()
            scheduler.shutdown.assert_called_once_with()

    def test_enabled_shutdown_also_runs_after_application_error(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'true'}), \
             patch.object(main, 'sweep_overdue_schedules'), \
             patch.object(main, 'AsyncIOScheduler') as factory:
            with self.assertRaisesRegex(RuntimeError, 'test error'):
                with TestClient(main.app):
                    raise RuntimeError('test error')
            factory.return_value.shutdown.assert_called_once_with()

    def test_invalid_setting_fails_before_database_access(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'maybe'}), \
             patch.object(main, 'sweep_overdue_schedules') as sweep, \
             patch.object(main, 'AsyncIOScheduler') as factory:
            with self.assertRaisesRegex(ValueError, 'SCHEDULER_ENABLED'):
                with TestClient(main.app):
                    pass
            sweep.assert_not_called()
            factory.assert_not_called()

    def test_disabled_predictions_and_manual_optimizer_still_available(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'false'}), \
             patch.object(main, 'AsyncIOScheduler') as factory, \
             patch.object(main, 'sweep_overdue_schedules') as sweep, \
             patch.object(main, 'get_equipment_due_for_maintenance', return_value=[]), \
             patch.object(main, 'save_optimized_maintenance_schedule') as save, \
             patch.object(main, 'predict_one', side_effect=main.predict_one), \
             patch.object(main, 'load_model') as load:
            model = Mock()
            model.predict.return_value = [300]
            load.return_value = model, {
                'features': ['manufacturer', 'repair_rate'],
                'manufacturers': ['Getinge SERVOi'],
                'fleet_repair_rates': [0.8, 1.2, 2.2],
                'repair_rate_cutoffs': {'low_below': 1, 'high_from': 2},
                'selected_mae': 149.08,
            }
            with TestClient(main.app) as client:
                sweep.assert_not_called()
                response = client.post('/api/ai/predict', json={
                    'device_type': 'Ventilator', 'manufacturer': 'Getinge SERVOi',
                    'age_years': 10, 'repair_events': 5,
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['predicted_annual_cost'], 300)
                response = client.post('/api/ai/optimize-schedule')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['schedule'], [])
                sweep.assert_called_once_with()
            factory.assert_not_called()
            save.assert_not_called()


if __name__ == '__main__':
    unittest.main()
