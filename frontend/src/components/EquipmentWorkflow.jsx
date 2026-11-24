import {useState} from 'react'
import {useApi} from '../useApi'
import {useMutation,torontoTime} from './workflowHelpers'
import ReviewControls from './ReviewControls'
import MutationStatus from './MutationStatus'

export default function EquipmentWorkflow({device,revision,onChanged,readOnly=false}) {
  const context=useApi(`/api/workflow/equipment/${device.id}`,revision)
  const action=useMutation()
  const [useAssessment,setUseAssessment]=useState(device.device_type==='Ventilator')
  const [priority,setPriority]=useState('')
  const [requestId,setRequestId]=useState(()=>crypto.randomUUID())
  const data=context.data
  function submit(e) {
    e.preventDefault();const f=new FormData(e.currentTarget)
    action.run('/api/workflow/tasks',{request_id:requestId,equipment_id:device.id,title:f.get('title'),duration_minutes:Number(f.get('duration')),
      required_qualification:f.get('qualification'),use_assessment:useAssessment,priority_override:priority||null,
      override_reason:f.get('reason')||null,due_date:f.get('due')||null,
      last_service_date:f.get('last_service')||null,service_interval_days:f.get('interval')?Number(f.get('interval')):null},()=>{setRequestId(crypto.randomUUID());onChanged()})
  }
  return <div>
    <h3>Maintenance tasks and history</h3>
    <ReviewControls device={device} data={data} readOnly={readOnly} onChanged={onChanged}/>
    {context.loading && <p>Loading maintenance information…</p>}
    {context.error && <p role="alert" className="error">{context.error} <button type="button" onClick={onChanged}>Retry maintenance information</button></p>}
    {data?.latest_saved_assessment && <aside className="notice"><strong>Assessment saved with latest task</strong>
      <p>Repair intensity: {data.latest_saved_assessment.snapshot.risk_level}. Repair-rate percentile: {(100*data.latest_saved_assessment.snapshot.risk_score).toFixed(1)}% (not failure probability).</p>
      <p><strong>{data.latest_saved_assessment.snapshot.recommendation_category}</strong> {data.latest_saved_assessment.snapshot.recommendation}</p>
      <small>Assessed {torontoTime(data.latest_saved_assessment.snapshot.assessed_at)}. Model: {data.latest_saved_assessment.snapshot.prediction?.model_version || 'unreported'}. Historical snapshot; create a new task for a fresh assessment.</small>
    </aside>}
    <form hidden={readOnly} id="maintenance-task-form" className="workflow-form" onChange={()=>setRequestId(crypto.randomUUID())} onSubmit={submit}>
      <fieldset disabled={action.busy}><legend>Create maintenance task</legend>
        <p>The server requests a fresh assessment and suggests priority. Manual priority requires an explanation.</p>
        <div className="form-grid">
          <label>Task title<input name="title" required maxLength={150} defaultValue="Maintenance review" /></label>
          <label>Duration (minutes)<input name="duration" type="number" required min="1" max="1440" step="1" defaultValue="60" /></label>
          <label>Required qualification<input name="qualification" required maxLength={100} defaultValue={device.device_type || 'General'} /></label>
          <label>Target date (optional)<input name="due" type="date" /></label>
          <label>Last service date (optional)<input name="last_service" type="date" /></label>
          <label>Service interval in days (optional)<input name="interval" type="number" min="1" max="3650" step="1" /></label>
          <label>Priority override<select aria-label="Task priority override" value={priority} required={!useAssessment} onChange={e=>setPriority(e.target.value)}><option value="">Use assessment suggestion</option>{['High','Medium','Low'].map(p=><option key={p}>{p}</option>)}</select></label>
          <label>Priority explanation<textarea name="reason" required={!!priority || !useAssessment} minLength={3} maxLength={2000} /></label>
        </div>
        <p className="subtitle">Enter both service fields only when the interval is known from an approved policy. The backend calculates the service due date. Overdue service remains visible; review targets cannot postpone it. Leave both empty if unknown.</p>
        <label><input type="checkbox" checked={useAssessment} disabled={device.device_type!=='Ventilator'} onChange={e=>setUseAssessment(e.target.checked)} /> Use AI-assisted assessment (Ventilator only)</label>
        {!useAssessment && <p className="notice">Manual mode: choose a priority and give its reason. Use this for unsupported equipment or unavailable AI.</p>}
        <button disabled={action.busy}>Create maintenance task</button>
      </fieldset>
    </form><MutationStatus action={action} />
    <h4>Current and upcoming assignments</h4>
    {data && !data.assignments?.length && <p>No confirmed assignments for this equipment.</p>}
    <ul>{data?.assignments?.filter(a=>['scheduled','in_progress'].includes(a.status)).map(a=><li key={a.id}>{a.title}: {a.technician_name}, {torontoTime(a.starts_at)} – {torontoTime(a.ends_at)}. Status: {a.status}. {a.priority_reason}</li>)}</ul>
    <h4>Recorded maintenance history</h4>
    {data && !data.history?.length && <p>No completed maintenance records. Aggregate repair count is separate from service history.</p>}
    <ul>{data?.history?.map(h=><li key={h.id}>{torontoTime(h.completed_at)}: {h.title}. {h.notes} Cost: CAD {h.actual_cost}</li>)}</ul>
    <h4>Task status history</h4>
    <ul>{data?.events?.map(v=><li key={v.id}>{torontoTime(v.created_at)}: {v.from_status || 'new'} → {v.to_status}. {v.note}</li>)}</ul>
  </div>
}
