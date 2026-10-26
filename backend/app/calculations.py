"""Shared calculations. Round only output values, never intermediate age."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo('America/Toronto')


def reference_date():
    return datetime.now(BUSINESS_TIMEZONE).date()


def exact_age(in_service_date, as_of):
    days = max(0, (as_of - in_service_date).days)
    return Decimal(days) / Decimal('365.25')


def two_places(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def annual_average(total_cost, age):
    return None if age <= 0 else two_places(total_cost / age)
