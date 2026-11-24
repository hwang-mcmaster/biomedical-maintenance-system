export default function ScheduleMeasurements({plan}) {
  const risk=plan.metrics, baseline=plan.comparison?.baseline?.metrics
  if(!risk)return null
  function download() {
    const url=URL.createObjectURL(new Blob([JSON.stringify(plan,null,2)],{type:'application/json'}))
    const link=document.createElement('a');link.href=url;link.download=`schedule-review-${plan.id||plan.schedule_date}.json`;link.click()
    setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
  const rows=[['Scheduled tasks','scheduled_count'],['Unassigned tasks','unscheduled_count'],
    ['High priority scheduled within target','high_priority_scheduled_within_target'],['After review target','after_target_count'],
    ['Service interval: scheduled on time','service_interval_scheduled_on_time'],['Service interval: scheduled late','service_interval_scheduled_late'],
    ['Selected-task utilization (%)','selected_task_utilization_percent'],['Planned work / equipment downtime (minutes)','planned_work_minutes'],
    ['Booking conflicts','conflicts'],['Placement computation (ms)','engine_ms']]
  return <section className="schedule-measurements" aria-label="Schedule validation results">
    <h4>Validation and baseline comparison</h4>
    <p>{plan.sample?'Illustrative layout sample; no constraints or results were measured.':risk.validation?.passed?'Constraint checks passed.':'Detailed constraint checks are unavailable for this older draft. Generate a new preview.'} {risk.validation?.checks?.length?risk.validation.checks.join(', ')+'.':''}</p>
    {baseline&&<><p>Baseline: {plan.comparison.baseline_name}. Service intervals recorded: {plan.comparison.service_interval_coverage}.</p>
    <div className="table-wrapper"><table><caption>Same inputs, different task order</caption><thead><tr><th>Measure</th><th>Risk priority</th><th>Due-date baseline</th></tr></thead><tbody>{rows.map(([label,key])=><tr key={key}><th scope="row">{label}</th><td>{risk[key]??'N/A'}</td><td>{baseline[key]??'N/A'}</td></tr>)}</tbody></table></div><p>{plan.comparison.scope}</p></>}
    <p>These are planned assignments, not completed work or avoided failures. Downtime assumes the equipment is unavailable for the full task. Cost savings have not been measured. Replacement decisions require human review.</p>
    <button type="button" className="secondary" onClick={download}>Download validation results</button>
  </section>
}
