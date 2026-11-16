"""Local seasonal recurrence matching Flight Web's Sunday-first calendar."""
import re
from datetime import timedelta


def validate_weeks(value):
    if not isinstance(value, str) or (value and (
        not re.fullmatch('[1-6]{1,6}', value) or len(set(value)) != len(value)
    )):
        raise ValueError('Weeks of month must be unique digits 1–6, or blank')
    return ''.join(sorted(value))


def operates(flight, day):
    weeks = flight.get('weeksText', '')
    week = 1 + (day.replace(day=1).isoweekday() % 7 + day.day - 1) // 7
    return day.isoweekday() in flight['operatingDays'] and (not weeks or str(week) in weeks)


def overlap(first, second, start, end):
    if not set(first['operatingDays']) & set(second['operatingDays']):
        return False
    cycle = 146097 if first.get('weeksText') or second.get('weeksText') else 7
    return any(operates(first, day) and operates(second, day)
               for day in (start + timedelta(days=i)
                           for i in range(min(cycle, (end-start).days+1))))
