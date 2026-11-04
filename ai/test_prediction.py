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
        result = predict_one(AssetIn(manufacturer='Getinge SERVOi', age_years=10, repair_events=5))
        self.assertEqual(result.predicted_annual_cost, 299.50)
        self.assertEqual(result.projected_cost_next_years, 1497.50)
        self.assertEqual(result.training_repair_rate_min, 0.81266)
        self.assertEqual(result.training_repair_rate_max, 2.272727)
        self.assertEqual(result.risk_score, 0)
        self.assertEqual(result.risk_level, 'low')


if __name__ == '__main__':
    unittest.main()
