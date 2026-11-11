"""Repeatable synthetic feasibility benchmark. No database writes or clinical claims."""
import json
from datetime import timedelta
from time import perf_counter
from uuid import UUID
from pathlib import Path
from app.calculations import reference_date
from app.scheduling import generate_schedule
from app.scheduling_schemas import ScheduleRequest


def scenario(count):
    day=reference_date()+timedelta(days=2)
    equipment={str(UUID(int=i+1)):{'asset_tag':f'SYNTH-{i:03}'} for i in range(count)}
    tasks=[{'id':f't{i:03}','equipment_id':key,'title':f'Synthetic inspection {i}',
      'priority':'High' if i%5==0 else 'Medium' if i%2 else 'Low',
      'required_qualification':'ventilator','duration_minutes':60} for i,key in enumerate(equipment)]
    techs=[{'id':f'tech{i}','name':f'Synthetic technician {i}','qualifications':['ventilator'],
      'availability':[{'start':'09:00','end':'17:00'}]} for i in range(5)]
    request=ScheduleRequest(schedule_date=day,tasks=tasks,technicians=techs)
    timings=[]
    for _ in range(20):
        start=perf_counter();result=generate_schedule(request,equipment);timings.append((perf_counter()-start)*1000)
    conflicts=0
    for i,a in enumerate(result.assignments):
        assert (a.end-a.start).total_seconds()==a.duration_minutes*60
        for b in result.assignments[i+1:]:
            if a.technician_id==b.technician_id or a.equipment_id==b.equipment_id:
                conflicts+=int(a.start<b.end and b.start<a.end)
    high_requested=sum(t['priority']=='High' for t in tasks)
    high_scheduled=sum(a.priority=='High' for a in result.assignments)
    assert conflicts==0 and high_scheduled==high_requested
    return {'equipment':count,'technicians':5,'runs':20,'mean_engine_ms':round(sum(timings)/len(timings),3),
      'max_engine_ms':round(max(timings),3),'scheduled':len(result.assignments),'unassigned':len(result.unscheduled),
      'independently_checked_conflicts':conflicts,'high_priority_requested':high_requested,'high_priority_scheduled':high_scheduled,
      'selected_task_utilization_percent':round(100*len(result.assignments)*60/(5*480),2)}

if __name__=='__main__':
    result={'as_of':reference_date().isoformat(),'scope':'Synthetic fixed-duration engine benchmark. Excludes DB/AI/network time. No actual completion or clinical outcomes measured.',
      'scenarios':[scenario(20),scenario(50)]}
    target=Path(__file__).parent/'validation/week10-synthetic-results.json';target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
