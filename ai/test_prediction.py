import unittest
from unittest.mock import Mock, patch
from app.main import AssetIn, predict_one


class PredictionContractTests(unittest.TestCase):
    @patch('app.main.load_model')
    def test_range_metadata_and_cent_consistent_projection(self, load):
        model = Mock()
        model.predict.return_value = [299.501234]
        load.return_value = model, {
            'features': ['manufacturer', 'repair_rate'], 'manufacturers': ['Getinge SERVOi'],
            'fleet_repair_rates': [0.81266, 1.2, 2.272727],
            'repair_rate_cutoffs': {'low_below': 1.0, 'high_from': 2.0}, 'selected_mae': 149.08,
        }
        result = predict_one(AssetIn(device_type='Ventilator', manufacturer='Getinge SERVOi', age_years=10, repair_events=5))
        self.assertEqual(result.predicted_annual_cost, 299.50)
        self.assertEqual(result.projected_cost_next_years, 1497.50)
        self.assertEqual(result.training_repair_rate_min, 0.81266)
        self.assertEqual(result.training_repair_rate_max, 2.272727)
        self.assertEqual(result.risk_score, 0)
        self.assertEqual(result.risk_level, 'low')




class ExpandedAIContractTests(unittest.TestCase):
    def fixture(self, load):
        model=Mock()
        model.predict.return_value=[300]
        load.return_value=model, {'features':['manufacturer','repair_rate'],
            'manufacturers':['Getinge SERVOi','Draeger V500'],
            'fleet_repair_rates':[0.8,1.2,2.2],
            'repair_rate_cutoffs':{'low_below':1,'high_from':2},'selected_mae':149.08}
        return model

    @patch('app.main.load_model')
    def test_separate_manufacturer_model_and_lifecycle_context(self, load):
        model=self.fixture(load)
        result=predict_one(AssetIn(device_type='Ventilator', manufacturer='Getinge', model_name='SERVOi',
            age_years=10, repair_events=15, cumulative_cost_to_date=15000,
            assumed_replacement_cost=20000, expected_useful_life=12))
        self.assertEqual(result.model_input_category,'Getinge SERVOi')
        self.assertEqual(model.predict.call_args.args[0]['manufacturer'][0],'Getinge SERVOi')
        self.assertEqual(result.maintenance_to_replacement_ratio,0.75)
        self.assertEqual(result.reference_remaining_life_years,2)
        self.assertFalse(result.warnings)

    @patch('app.main.load_model')
    def test_zero_cost_and_elapsed_reference_life(self, load):
        self.fixture(load)
        result=predict_one(AssetIn(device_type='Ventilator', manufacturer='Draeger', model_number='V500',
            age_years=20, repair_events=20, cumulative_cost_to_date=1000,
            assumed_replacement_cost=0, expected_useful_life=15))
        self.assertIsNone(result.maintenance_to_replacement_ratio)
        self.assertEqual(result.assumed_replacement_cost,0)
        self.assertEqual(result.reference_remaining_life_years,0)
        self.assertTrue(any('zero' in item for item in result.warnings))
        self.assertTrue(any('reference threshold' in item for item in result.warnings))

    def test_device_scope_and_finite_inputs(self):
        from pydantic import ValidationError
        base=dict(device_type='Ventilator',manufacturer='Getinge',age_years=10,repair_events=1)
        for change in [{'device_type':'Other'},{'age_years':float('nan')},{'assumed_replacement_cost':-1},{'expected_useful_life':0}]:
            with self.assertRaises(ValidationError): AssetIn(**(base | change))


if __name__ == '__main__':
    unittest.main()
