"""Versioned engineering review rules; these are not learned failure predictions."""
from .calculations import exact_age

CATEGORIES = ('Normal Monitoring', 'Recommended Inspection', 'Recommended Maintenance',
              'Recommended Replacement Review')
POLICY_VERSION = 'engineering-review-v1'


def recommendation_policy(device, prediction):
    reasons = []
    if device.expected_useful_life and exact_age(device.in_service_date, device.calculated_as_of) >= device.expected_useful_life:
        reasons.append('Recorded reference useful life has been reached.')
    ratio = prediction.maintenance_to_replacement_ratio
    if ratio is not None and ratio >= 1:
        reasons.append('Recorded historical maintenance cost equals or exceeds replacement cost.')
    if reasons:
        category = CATEGORIES[3]
    else:
        category = {'low': CATEGORIES[0], 'medium': CATEGORIES[1], 'high': CATEGORIES[2]}[prediction.risk_level]
        reasons.append(f'Relative repair intensity is {prediction.risk_level}.')
    return category, reasons + ['Prototype review rule; verify manufacturer guidance and condition. Replacement requires qualified human approval.']


def criticality_priority(priority, criticality):
    # A critical device receives at least High; Important receives at least Medium.
    order = {'Low': 0, 'Medium': 1, 'High': 2}
    floor = {'Routine': 0, 'Important': 1, 'Critical': 2, None: 0}[criticality]
    return ('Low', 'Medium', 'High')[max(order[priority], floor)]
