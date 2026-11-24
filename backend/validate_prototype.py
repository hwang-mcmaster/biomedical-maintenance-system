"""Repeatable large synthetic scenarios; writes evidence only under backend/validation.

Run: venv/Scripts/python.exe validate_prototype.py
No database, AI model or real operational records are changed.
"""
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from uuid import UUID
from app.calculations import reference_date
from app.scheduling import generate_schedule
from app.scheduling_schemas import ScheduleRequest
from app.schedule_validation import schedule_metrics


def fixture(count, offset=0):
    day=reference_date()+timedelta(days=2)
    equipment={str(UUID(int=i+1)):{'asset_tag':f'SYNTHETIC-{i:04}'} for i in range(offset,offset+count)}
    tasks=[]
    for i,key in enumerate(equipment,offset):
        due=day+timedelta(days=(i%4)-1)
        tasks.append({'id':f'task-{i:04}','equipment_id':key,'title':f'Synthetic inspection {i}',
          'priority':'High' if i%5==0 else 'Medium' if i%2 else 'Low',
          'required_qualification':'ventilator' if i%3 else 'infusion pump',
          'duration_minutes':[30,45,60,90][i%4],'due_date':due,'service_due_date':due})
    techs=[{'id':f'tech-{i}','name':f'Synthetic technician {i}',
      'qualifications':['ventilator','infusion pump'] if i==0 else ['ventilator' if i%2 else 'infusion pump'],
      'availability':[{'start':'09:00','end':'12:00'},{'start':'13:00','end':'17:00'}]} for i in range(5)]
    bookings=[{'id':'existing','technician_id':'tech-0','equipment_id':next(iter(equipment)),
               'start':'09:00','end':'10:00'}]
    return ScheduleRequest(schedule_date=day,tasks=tasks,technicians=techs,existing_bookings=bookings),equipment


def measure(request,equipment,strategy,repeats=20):
    timings=[]
    for _ in range(repeats):
        started=perf_counter()
        result=generate_schedule(request,equipment,strategy=strategy).model_dump(mode='json')
        timings.append((perf_counter()-started)*1000)
    metrics=schedule_metrics(request,result)
    if not metrics['validation']['passed']: raise AssertionError(metrics['validation'])
    return {'metrics':metrics,'runs':repeats,'mean_engine_ms':round(sum(timings)/len(timings),3),
            'max_engine_ms':round(max(timings),3),'output':result}


def run():
    scenarios=[]
    for fleet_size in (50,100,200):
        batches=[]
        for offset in range(0,fleet_size,100):
            request,equipment=fixture(min(100,fleet_size-offset),offset)
            batches.append({'offset':offset,'inputs':request.model_dump(mode='json'),
              'risk':measure(request,equipment,'risk'),'fixed_interval':measure(request,equipment,'fixed_interval')})
        scenarios.append({'inventory_size':fleet_size,'batches':batches})
    # Copy reported training results for traceability; never present them as new validation.
    ai_dir=Path(__file__).resolve().parents[1]/'ai'
    metadata_path=ai_dir/'models/model_metadata.json'
    model_path=ai_dir/'models/cost_model.joblib'
    metadata=json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    result={'generated_at':datetime.now(timezone.utc).isoformat(),
      'scope':'Synthetic engine scenarios. Each batch is an independent single-day capacity experiment; batches are not a combined feasible schedule. Excludes database, network and AI time. No clinical, cost-saving or actual-completion claims.',
      'assumptions':{'task_limit':100,'technicians':5,'availability_minutes_each':420,
         'planned_downtime':'Full reserved task duration, not measured unplanned downtime.',
         'cost':'Not calculated: approved labour rates and parts costs are unavailable.',
         'priority':'Deterministic test-fixture labels, not AI predictions.'},
      'ai_validation':{'status':'Existing model metadata, not independently recomputed',
        'model_version':hashlib.sha256(model_path.read_bytes()).hexdigest()[:16] if model_path.exists() else None,
        'reported_metadata':metadata,
        'classification_metrics':{'recall':None,'f1':None,'false_negative_rate':None,
          'reason':'No labelled failure outcomes or validated failure classifier. Repair-intensity bands cannot be used as failure ground truth.'},
        'limitation':'Model selection and reported cross-validation use the same small synthetic dataset. Independent outcome validation remains required.'},
      'scenarios':scenarios}
    target=Path(__file__).parent/'validation'
    target.mkdir(exist_ok=True)
    (target/'prototype-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (target/'prototype-summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['inventory','batch_offset','strategy','scheduled','unassigned','high_within_target','utilization_percent','service_late','conflicts','mean_engine_ms'])
        for scenario in scenarios:
            for batch in scenario['batches']:
                for strategy in ('risk','fixed_interval'):
                    r=batch[strategy];m=r['metrics']
                    writer.writerow([scenario['inventory_size'],batch['offset'],strategy,m['scheduled_count'],m['unscheduled_count'],
                      m['high_priority_scheduled_within_target'],m['selected_task_utilization_percent'],m['service_interval_scheduled_late'],m['conflicts'],r['mean_engine_ms']])
    print('Saved validation/prototype-results.json and validation/prototype-summary.csv')


if __name__=='__main__': run()
