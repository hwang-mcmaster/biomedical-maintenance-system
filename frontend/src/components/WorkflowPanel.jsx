import {useState} from 'react'
import {useApi} from '../useApi'
import {useMutation,nextTorontoDay,torontoTime} from './workflowHelpers'
import MutationStatus from './MutationStatus'

export default function WorkflowPanel({revision,onChanged}) {
  const techs=useApi('/api/workflow/technicians',revision),tasks=useApi('/api/workflow/tasks',revision)
  const assignments=useApi('/api/workflow/assignments',revision),schedules=useApi('/api/workflow/schedules',revision)
  const metrics=useApi('/api/workflow/metrics',revision)
  const action=useMutation(),[editTech,setEditTech]=useState(null),[techName,setTechName]=useState(''),[skills,setSkills]=useState('')
  const [windows,setWindows]=useState([{date:nextTorontoDay(),start:'09:00',end:'17:00'}])
  const [day,setDay]=useState(nextTorontoDay()),[selected,setSelected]=useState([]),[preview,setPreview]=useState(null),[statusTask,setStatusTask]=useState(null)
  const pending=(tasks.data||[]).filter(t=>t.status==='pending')
  function changed(){setPreview(null);setSelected([]);onChanged()}
  function edit(t){setEditTech(t.id);setTechName(t.name);setSkills(t.qualifications.join(', '));setWindows(t.availability)}
  function reset(){setEditTech(null);setTechName('');setSkills('');setWindows([{date:nextTorontoDay(),start:'09:00',end:'17:00'}])}
  function saveTech(e){e.preventDefault();action.run(editTech?`/api/workflow/technicians/${editTech}`:'/api/workflow/technicians',{
    name:techName,qualifications:skills.split(',').map(s=>s.trim()).filter(Boolean),availability:windows},()=>{reset();changed()},editTech?'PUT':'POST')}
  function generate(e){e.preventDefault();setPreview(null);action.run('/api/workflow/schedules/preview',{
    schedule_date:day,task_ids:selected.length?selected:pending.map(t=>t.id)},result=>{setPreview(result);onChanged()})}
  function status(e){e.preventDefault();const f=new FormData(e.currentTarget);action.run(`/api/workflow/tasks/${statusTask.id}/status`,{
    status:statusTask.next,notes:f.get('notes'),actual_cost:f.get('cost')||'0.00'},()=>{setStatusTask(null);changed()})}
  const unavailable=[techs,tasks,assignments,schedules].some(s=>s.loading||s.error)
  return <section className="panel" aria-labelledby="workflow-heading">
    <div className="section-heading"><h2 id="workflow-heading">Saved maintenance workflow</h2><button type="button" className="secondary" onClick={changed}>Refresh maintenance workflow</button></div>
    <p>Create a task in equipment details. Assessment-derived or reviewed manual priorities flow into scheduling automatically.</p>
    <aside className="notice">Priority reflects relative repair intensity and engineering review, not failure probability. Default review targets are 7/30/90 days. Confirm a preview to reserve resources.</aside>
    {[techs,tasks,assignments,schedules].some(s=>s.loading)&&<p role="status">Loading saved maintenance data…</p>}
    {[...new Set([techs,tasks,assignments,schedules].map(s=>s.error).filter(Boolean))].map(e=><p key={e} role="alert" className="error">{e}</p>)}
    <MutationStatus action={action}/>
    <h3>Technicians</h3>
    <ul>{techs.data?.map(t=><li key={t.id}><strong>{t.name}</strong>: {t.qualifications.join(', ')}. {t.availability.map(w=>`${w.date} ${w.start}–${w.end}`).join('; ') || 'No availability'} <button type="button" className="secondary" disabled={action.busy} onClick={()=>edit(t)}>Edit {t.name}</button></li>)}</ul>
    <form id="technician-form" className="workflow-form" onSubmit={saveTech}><fieldset disabled={action.busy}>
      <legend>{editTech?'Edit technician':'Add technician'}</legend><div className="form-grid">
        <label>Technician name<input required maxLength={100} value={techName} onChange={e=>setTechName(e.target.value)}/></label>
        <label>Qualifications (comma separated)<input required value={skills} onChange={e=>setSkills(e.target.value)}/></label>
      </div><p>Enter agreed qualification labels, such as Ventilator. These labels are not independently verified credentials. Times are local to Toronto.</p>
      {windows.map((w,i)=><div className="schedule-window" key={i}>{['date','start','end'].map(k=><label key={k}>Availability {k}<input type={k==='date'?'date':'time'} required value={w[k]} onChange={e=>setWindows(windows.map((old,j)=>j===i?{...old,[k]:e.target.value}:old))}/></label>)}<button type="button" className="secondary" onClick={()=>setWindows(windows.filter((_,j)=>j!==i))}>Remove window {i+1}</button></div>)}
      <div className="actions"><button type="button" className="secondary" onClick={()=>setWindows([...windows,{date:day,start:'09:00',end:'17:00'}])}>Add availability window</button><button disabled={action.busy}>{editTech?'Save technician changes':'Save technician'}</button>{editTech&&<button type="button" className="secondary" onClick={reset}>Cancel technician edit</button>}</div>
    </fieldset></form>
    <h3>Maintenance tasks</h3><p>Choose tasks below, or leave them unchecked to schedule all pending tasks (up to 100).</p>
    <div className="table-wrapper"><table className="workflow-table"><caption>Saved maintenance tasks</caption><thead><tr><th>Select</th><th>Equipment / task</th><th>Priority and reason</th><th>Requirements</th><th>Status / action</th></tr></thead><tbody>{tasks.data?.map(t=><tr key={t.id}>
      <td>{t.status==='pending'&&<input type="checkbox" aria-label={`Schedule ${t.title} for ${t.asset_tag}`} checked={selected.includes(t.id)} onChange={e=>{setPreview(null);setSelected(e.target.checked?[...selected,t.id]:selected.filter(id=>id!==t.id))}}/>}</td>
      <td>{t.asset_tag}<br/>{t.title}</td><td>{t.priority}<small>{t.priority_reason}</small><small>Target: {t.due_date}</small></td><td>{t.duration_minutes} min<br/>{t.required_qualification}</td><td>{t.status}<div className="actions">
        {t.status==='scheduled'&&<button type="button" disabled={action.busy} onClick={()=>setStatusTask({...t,next:'in_progress'})}>Start task</button>}
        {t.status==='in_progress'&&<button type="button" disabled={action.busy} onClick={()=>setStatusTask({...t,next:'completed'})}>Complete task</button>}
        {!['completed','cancelled'].includes(t.status)&&<button type="button" className="secondary" disabled={action.busy} onClick={()=>setStatusTask({...t,next:'cancelled'})}>Cancel task</button>}</div></td>
    </tr>)}</tbody></table></div>
    {statusTask&&<form id="task-status-form" className="workflow-form" onSubmit={status}><fieldset disabled={action.busy}><legend>{statusTask.title}: {statusTask.next}</legend><label>Status notes<textarea name="notes" required minLength={3} maxLength={2000}/></label>{statusTask.next==='completed'&&<label>Actual maintenance cost (CAD)<input name="cost" type="number" required min="0" step="0.01" defaultValue="0"/></label>}<div className="actions"><button disabled={action.busy}>Save task status</button><button type="button" className="secondary" onClick={()=>setStatusTask(null)}>Close status form</button></div></fieldset></form>}
    <form id="saved-schedule-form" className="workflow-form" onSubmit={generate}><fieldset disabled={action.busy||unavailable}><legend>Generate from saved records</legend><label>Planning date (Toronto)<input type="date" required value={day} onChange={e=>{setDay(e.target.value);setPreview(null)}}/></label><button disabled={action.busy||unavailable||!pending.length}>Generate saved schedule preview</button></fieldset></form>
    {preview&&<div className="schedule-results"><h3>Schedule review</h3><p>{preview.assignments.length} scheduled, {preview.unscheduled.length} unassigned. Draft ID: {preview.id}</p>
      <div className="table-wrapper"><table className="workflow-table"><caption>Proposed assignments</caption><thead><tr><th>Task / equipment</th><th>Technician</th><th>Toronto time</th><th>Priority explanation</th></tr></thead><tbody>{preview.assignments.map(a=><tr key={a.task_id}><td>{a.title}<br/>{a.asset_tag}</td><td>{a.technician_name}</td><td>{torontoTime(a.start)}<br/>{torontoTime(a.end)}</td><td>{a.priority}<small>{a.priority_reason}</small><small>{a.within_target?'Within':'After'} review target: {a.due_date}</small></td></tr>)}</tbody></table></div>
      <ul>{preview.unscheduled.map(t=><li key={t.task_id}>{t.asset_tag}: {t.title}. {t.reason}</li>)}</ul>
      <p>Computation: {preview.metrics.computation_ms} ms. Conflicts: {preview.metrics.conflicts}. High-priority tasks scheduled within target: {preview.metrics.high_priority_scheduled_within_target}/{preview.metrics.high_priority_requested}. Selected-task utilization: {preview.metrics.selected_task_utilization_percent}%.</p>
      <ul>{preview.notices.map(n=><li key={n}>{n}</li>)}</ul>
      <button type="button" disabled={action.busy||!preview.assignments.length} onClick={()=>action.run(`/api/workflow/schedules/${preview.id}/confirm`,{},()=>{setSelected([]);changed()})}>Confirm schedule</button>
    </div>}
    <h3>Confirmed maintenance assignments</h3><div className="table-wrapper"><table className="workflow-table"><caption>Upcoming work and assignment history</caption><thead><tr><th>Equipment / task</th><th>Technician</th><th>Toronto time</th><th>Status</th><th>Priority</th></tr></thead><tbody>{assignments.data?.map(a=><tr key={a.id}><td>{a.asset_tag}<br/>{a.title}</td><td>{a.technician_name}</td><td>{torontoTime(a.starts_at)}<br/>{torontoTime(a.ends_at)}</td><td>{a.status}</td><td>{a.priority}<small>{a.priority_reason}</small></td></tr>)}</tbody></table></div>
    {metrics.data?.high_priority_completion && <p>Recorded high-priority work completed within its review target: {metrics.data.high_priority_completion.completed_within_target}/{metrics.data.high_priority_completion.completed}. Completion results come from recorded work, not generated schedules.</p>}
    <details><summary>Saved schedule runs and measurements</summary><ul>{schedules.data?.map(s=><li key={s.id}>{s.schedule_date}, {s.status}: {s.result.metrics?.scheduled_count} assignments in {s.result.metrics?.computation_ms} ms. {s.status==='draft'&&<button type="button" className="secondary" onClick={()=>setPreview({...s.result,id:s.id})}>Review saved draft</button>}</li>)}</ul></details>
  </section>
}
