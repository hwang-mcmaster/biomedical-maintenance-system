// Only Vite development mode can enable this local, read-only sample workspace.
export const UI_PREVIEW = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1'
const day = new Date(Date.now()+86400000).toISOString().slice(0,10)
const stamp = `${day}T10:00:00-05:00`
const user = {id:'preview-user',name:'UI Preview',email:'preview@example.test',role:'admin',is_active:true}
const devices = ['Ventilator','Infusion Pump','Patient Monitor'].map((device_type,i)=>({
 id:`preview-equipment-${i}`,asset_tag:`DEMO-00${i+1}`,serial_number:`00000${i+1}`,manufacturer:['Getinge','BD','Philips'][i],
 model_name:['SERVOi','Alaris','IntelliVue'][i],device_type,status:i===1?'Under Maintenance':'Operational',
 department:['ICU','Emergency','Operating Room'][i],location:`Room ${i+1}`,in_service_date:'2020-01-01',
 calculated_as_of:new Date().toISOString().slice(0,10),age_years:'6.00',repair_events:[12,3,5][i],total_historical_cost:'4200.00',
 avg_annual_cost:'700.00',replacement_cost:'20000.00',expected_useful_life:15,reference_remaining_life_years:'9.00'
}))
const assessment={equipment_id:devices[0].id,risk_level:'high',risk_score:.85,repair_rate_percentile:.85,assessed_at:stamp,
 recommendation:'Sample: prioritize an engineering review of repeated repairs.',limitation:'UI preview sample only. No AI prediction has been requested.',
 prediction:{model_version:'ui-sample',model_input_category:'Getinge SERVOi',predicted_annual_cost:700,cost_error_range:149.08,
 repair_rate_per_year:2,training_repair_rate_min:.8,training_repair_rate_max:2.3,projected_cost_next_years:3500,projection_years:5,
 maintenance_to_replacement_ratio:.035,warnings:['Illustrative sample data for checking layout only.']}}
const technicians=[{id:'preview-tech',name:'Sample technician A',qualifications:['ventilator'],availability:[{date:day,start:'09:00',end:'17:00'}]},
 {id:'preview-tech-b',name:'Sample technician B',qualifications:['infusion pump','patient monitor'],availability:[{date:day,start:'09:00',end:'17:00'}]}]
const tasks=[{id:'preview-task',equipment_id:devices[0].id,asset_tag:devices[0].asset_tag,title:'Ventilator maintenance review',priority:'High',
 priority_reason:'Sample assessment: high repair intensity. This is a workload review priority, not failure probability.',
 duration_minutes:60,required_qualification:'ventilator',status:'scheduled',due_date:day,assessment},
 {id:'preview-task-b',equipment_id:devices[1].id,asset_tag:devices[1].asset_tag,title:'Infusion pump inspection',priority:'Medium',
 priority_reason:'Sample manual engineering review.',duration_minutes:45,required_qualification:'infusion pump',status:'pending',due_date:day}]
const assignments=[{...tasks[0],id:'preview-assignment',task_id:tasks[0].id,technician_id:technicians[0].id,technician_name:technicians[0].name,
 starts_at:stamp,ends_at:`${day}T11:00:00-05:00`}]
export async function previewRequest(path,options={}) {
 if(!['GET','HEAD'].includes((options.method||'GET').toUpperCase())) throw new Error('UI preview is read-only. Nothing was sent to the backend or saved.')
 if(path==='/api/auth/me')return {user,csrf_token:'ui-preview-only'}
 if(path==='/api/auth/users')return [user]
 if(path==='/api/auth/audit')return [{id:'sample',name:'UI Preview',action:'Sample workspace opened',created_at:stamp}]
 if(path==='/api/health'||path==='/api/ready')return {status:'preview',message:'Sample data only. No backend or database connection.'}
 if(path==='/api/equipment/options')return {device_types:['Ventilator','Infusion Pump','Patient Monitor','Defibrillator','Other'],statuses:['Operational','Under Maintenance','Inactive']}
 if(path==='/api/equipment')return structuredClone(devices)
 if(path.endsWith('/assessment'))return structuredClone(assessment)
 if(path.startsWith('/api/workflow/equipment/'))return {tasks:structuredClone(tasks.filter(t=>t.equipment_id===path.split('/').at(-1))),
 assignments:structuredClone(assignments.filter(a=>a.equipment_id===path.split('/').at(-1))),history:[],events:[],
 latest_saved_assessment:path.endsWith(devices[0].id)?{snapshot:assessment,created_at:stamp}:null}
 if(path==='/api/workflow/tasks')return structuredClone(tasks)
 if(path==='/api/workflow/technicians')return structuredClone(technicians)
 if(path==='/api/workflow/assignments'||path==='/api/workflow/my-work')return structuredClone(assignments)
 if(path==='/api/workflow/metrics')return {high_priority_completion:{completed:0,completed_within_target:0}}
 if(path==='/api/workflow/schedules')return [{id:'preview-run',schedule_date:day,status:'confirmed',result:{metrics:{scheduled_count:1,computation_ms:1.2}}}]
 if(path==='/api/maintenance-schedules')return []
 throw new Error('This endpoint is not available in the sample UI preview.')
}
