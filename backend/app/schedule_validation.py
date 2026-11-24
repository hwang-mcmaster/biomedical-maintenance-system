"""Independent schedule checks and measurements; no database or model changes."""
from datetime import datetime, timezone
from .calculations import BUSINESS_TIMEZONE
from .scheduling import local_instant, qualification_key


def instant(value):
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        raise ValueError('Assignment timestamps must include a timezone.')
    return parsed.astimezone(timezone.utc)


def inspect_schedule(request, result, resource_bookings=()):
    """Check the output against original inputs, independently of placement logic.

    Deadlines are measured, rather than silently dropping overdue maintenance.
    A late assignment is reported explicitly and requires a user's review.
    """
    tasks = {t.id: t for t in request.tasks}
    techs = {t.id: t for t in request.technicians}
    issues, seen, intervals = [], set(), []
    bookings = list(resource_bookings) + [
        (b.technician_id, b.equipment_id, local_instant(request.schedule_date, b.start),
         local_instant(request.schedule_date, b.end)) for b in request.existing_bookings]
    for row in result['assignments']:
        task, tech = tasks.get(row['task_id']), techs.get(row['technician_id'])
        if row['task_id'] in seen or task is None or tech is None:
            issues.append('Unknown or duplicate task/technician.')
            continue
        seen.add(task.id)
        start, end = instant(row['start']), instant(row['end'])
        if (str(row['equipment_id']) != str(task.equipment_id)
                or row['priority'] != task.priority
                or row['duration_minutes'] != task.duration_minutes
                or qualification_key(row['required_qualification']) != qualification_key(task.required_qualification)):
            issues.append('Assignment does not match the original task.')
        if end <= start or (end-start).total_seconds() != task.duration_minutes * 60:
            issues.append('Task duration is incorrect.')
        if qualification_key(task.required_qualification) not in {qualification_key(q) for q in tech.qualifications}:
            issues.append('Technician lacks the required qualification.')
        if not any(local_instant(request.schedule_date, w.start) <= start < end <=
                   local_instant(request.schedule_date, w.end) for w in tech.availability):
            issues.append('Assignment is outside technician availability.')
        intervals.append((tech.id, str(task.equipment_id), start, end))
    conflicts = 0
    for i, (tech, equipment, start, end) in enumerate(intervals):
        others = intervals[i+1:] + [(t, str(e), instant(s), instant(f)) for t, e, s, f in bookings]
        for other_tech, other_equipment, other_start, other_end in others:
            if (tech == other_tech or equipment == other_equipment) and start < other_end and other_start < end:
                conflicts += 1
    if conflicts:
        issues.append('Technician or equipment booking overlaps.')
    for row in result['unscheduled']:
        if row['task_id'] in seen or row['task_id'] not in tasks:
            issues.append('Unknown or duplicate unassigned task.')
        seen.add(row['task_id'])
    if seen != set(tasks):
        issues.append('Some requested tasks are missing from the result.')
    return {'passed': not issues, 'conflicts': conflicts, 'issues': sorted(set(issues)),
            'checks': ['task coverage', 'task identity', 'duration', 'qualifications', 'availability',
                       'technician conflicts', 'equipment conflicts', 'existing bookings']}


def schedule_metrics(request, result, resource_bookings=()):
    check = inspect_schedule(request, result, resource_bookings)
    rows = result['assignments']
    by_id = {t.id: t for t in request.tasks}
    def on_time(row, field):
        deadline = getattr(by_id[row['task_id']], field)
        return deadline is not None and instant(row['end']).astimezone(BUSINESS_TIMEZONE).date() <= deadline
    tech_metrics = []
    for tech in request.technicians:
        available = sum((local_instant(request.schedule_date, w.end)-local_instant(request.schedule_date, w.start)).total_seconds()/60 for w in tech.availability)
        assigned = sum(r['duration_minutes'] for r in rows if r['technician_id'] == tech.id)
        tech_metrics.append({'technician_id': tech.id, 'name': tech.name, 'available_minutes': available,
                             'assigned_minutes': assigned, 'utilization_percent': round(100*assigned/available, 2) if available else 0})
    available = sum(t['available_minutes'] for t in tech_metrics)
    assigned = sum(r['duration_minutes'] for r in rows)
    return {'tasks_requested': len(request.tasks), 'scheduled_count': len(rows),
            'unscheduled_count': len(result['unscheduled']), 'conflicts': check['conflicts'],
            'validation': check, 'high_priority_requested': sum(t.priority == 'High' for t in request.tasks),
            'high_priority_scheduled_within_target': sum(r['priority'] == 'High' and on_time(r, 'due_date') for r in rows),
            'after_target_count': sum(by_id[r['task_id']].due_date is not None and not on_time(r, 'due_date') for r in rows),
            'service_interval_tasks': sum(t.service_due_date is not None for t in request.tasks),
            'service_interval_scheduled_on_time': sum(on_time(r, 'service_due_date') for r in rows),
            'service_interval_scheduled_late': sum(by_id[r['task_id']].service_due_date is not None and not on_time(r, 'service_due_date') for r in rows),
            'planned_work_minutes': assigned, 'planned_equipment_downtime_minutes': assigned,
            'selected_task_utilization_percent': round(100*assigned/available, 2) if available else 0,
            'technicians': tech_metrics}
