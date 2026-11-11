"""Deterministic feasibility prototype. No AI calls or database writes."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Response
from . import repository
from .calculations import BUSINESS_TIMEZONE
from .scheduling_schemas import Assignment, SchedulePreview, ScheduleRequest, UnscheduledTask

router = APIRouter(prefix='/api/scheduling', tags=['Scheduling prototype'])
PRIORITY_ORDER = {'High': 0, 'Medium': 1, 'Low': 2}


def local_instant(day, clock):
    naive = datetime.combine(day, clock)
    candidates = []
    for fold in (0, 1):
        local = naive.replace(tzinfo=BUSINESS_TIMEZONE, fold=fold)
        utc = local.astimezone(timezone.utc)
        if utc.astimezone(BUSINESS_TIMEZONE).replace(tzinfo=None) == naive and utc not in candidates:
            candidates.append(utc)
    if len(candidates) != 1:
        raise HTTPException(422, 'A time is ambiguous or nonexistent during a daylight-saving change. Choose an unambiguous Toronto time.')
    return candidates[0]


def first_slot(start, end, duration, blocked):
    cursor = start
    for busy_start, busy_end in sorted(blocked):
        if busy_end <= cursor or busy_start >= end:
            continue
        if cursor + duration <= busy_start:
            return cursor
        cursor = max(cursor, busy_end)
        if cursor + duration > end:
            return None
    return cursor if cursor + duration <= end else None


def qualification_key(value):
    return ' '.join(value.casefold().split())


def generate_schedule(request, equipment, resource_bookings=()):
    referenced = {task.equipment_id for task in request.tasks} | {booking.equipment_id for booking in request.existing_bookings}
    missing = sorted(str(key) for key in referenced if str(key) not in equipment)
    if missing:
        raise HTTPException(404, f'Equipment not found: {", ".join(missing)}. Refresh inventory and update the inputs.')
    windows = {tech.id: [(local_instant(request.schedule_date, w.start), local_instant(request.schedule_date, w.end))
                         for w in tech.availability] for tech in request.technicians}
    technician_busy = {tech.id: [] for tech in request.technicians}
    equipment_busy = {key: [] for key in referenced}
    for booking in sorted(request.existing_bookings, key=lambda item: (item.start, item.id)):
        start, end = local_instant(request.schedule_date, booking.start), local_instant(request.schedule_date, booking.end)
        busy = technician_busy[booking.technician_id] + equipment_busy[booking.equipment_id]
        if any(start < other_end and other_start < end for other_start, other_end in busy):
            raise HTTPException(422, 'Existing bookings already overlap for a technician or equipment item. Correct them before generating a preview.')
        technician_busy[booking.technician_id].append((start, end))
        equipment_busy[booking.equipment_id].append((start, end))

    # Saved workflow bookings carry full timezone-aware intervals, including overnight work.
    for technician_id, equipment_id, start, end in resource_bookings:
        if technician_id in technician_busy:
            technician_busy[technician_id].append((start, end))
        if equipment_id in equipment_busy:
            equipment_busy[equipment_id].append((start, end))

    assignments, unscheduled = [], []
    for task in sorted(request.tasks, key=lambda item: (PRIORITY_ORDER[item.priority], item.id)):
        duration = timedelta(minutes=task.duration_minutes)
        qualified = [tech for tech in request.technicians if qualification_key(task.required_qualification)
                     in {qualification_key(value) for value in tech.qualifications}]
        candidates, long_enough = [], False
        for tech in qualified:
            for start, end in windows[tech.id]:
                if end - start >= duration:
                    long_enough = True
                slot = first_slot(start, end, duration, technician_busy[tech.id] + equipment_busy[task.equipment_id])
                if slot is not None:
                    candidates.append((slot, tech.id))
        asset_tag = equipment[str(task.equipment_id)]['asset_tag']
        if not candidates:
            if not qualified:
                code, reason = 'NO_QUALIFIED_TECHNICIAN', 'No supplied technician has the required qualification.'
            elif not long_enough:
                code, reason = 'INSUFFICIENT_AVAILABILITY', 'No qualified technician has one continuous availability window long enough for this task.'
            else:
                code, reason = 'RESOURCE_CONFLICT', 'No slot remains after bookings and higher-priority placements. Adjust availability or task order and regenerate.'
            unscheduled.append(UnscheduledTask(task_id=task.id, title=task.title, equipment_id=task.equipment_id,
                asset_tag=asset_tag, priority=task.priority, reason_code=code, reason=reason))
            continue
        start, technician_id = min(candidates)
        end = start + duration
        technician_busy[technician_id].append((start, end))
        equipment_busy[task.equipment_id].append((start, end))
        technician = next(tech for tech in request.technicians if tech.id == technician_id)
        assignments.append(Assignment(task_id=task.id, title=task.title, equipment_id=task.equipment_id,
            asset_tag=asset_tag, technician_id=technician_id, technician_name=technician.name,
            priority=task.priority, required_qualification=task.required_qualification,
            duration_minutes=task.duration_minutes, start=start.astimezone(BUSINESS_TIMEZONE), end=end.astimezone(BUSINESS_TIMEZONE)))
    assignments.sort(key=lambda item: (item.start.astimezone(timezone.utc), item.technician_id, item.task_id))
    return SchedulePreview(schedule_date=request.schedule_date, generated_at=datetime.now(timezone.utc),
        assignments=assignments, unscheduled=unscheduled, notices=[
            'Preview only. Tasks, technicians, qualifications, availability and bookings are supplied inputs; this plan is not saved or booked.',
            'Priority-first placement produces a feasible draft, not a globally optimized schedule. Some unassigned tasks may fit under a different ordering.',
            'Equipment identity comes from PostgreSQL. Task priority is entered explicitly and is not a clinical risk score.',
        ])


@router.post('/preview', response_model=SchedulePreview)
def preview_schedule(request: ScheduleRequest, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    equipment = {str(row['id']): row for row in repository.list_equipment()}
    return generate_schedule(request, equipment)
