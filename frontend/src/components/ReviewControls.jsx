import {useState} from 'react'
import {useMutation} from './workflowHelpers'
import MutationStatus from './MutationStatus'

export default function ReviewControls({device,data,readOnly,onChanged}) {
 const action=useMutation(),[decision,setDecision]=useState('accepted')
 function review(e){e.preventDefault();const f=new FormData(e.currentTarget);action.run(`/api/workflow/equipment/${device.id}/reviews`,{decision,rationale:f.get('rationale')},onChanged)}
 function policy(e){e.preventDefault();const f=new FormData(e.currentTarget);action.run(`/api/workflow/equipment/${device.id}/service-policy`,{title:f.get('title'),interval_days:Number(f.get('interval')),last_service_date:f.get('last'),duration_minutes:Number(f.get('duration')),required_qualification:f.get('qualification'),priority:f.get('priority'),source:f.get('source'),active:f.get('active')==='on'},onChanged,'PUT')}
 function reconcile(e,id){e.preventDefault();const f=new FormData(e.currentTarget);action.run(`/api/workflow/history/${id}/reconcile`,{repair_event:f.get('repair')==='on',reason:f.get('reason')},onChanged)}
 const p=data?.service_policy
 return <section aria-label="Engineering review and service policy">
 <MutationStatus action={action}/>
 {!readOnly&&device.device_type==='Ventilator'&&<form onSubmit={review}><fieldset disabled={action.busy}><legend>Record recommendation review</legend><p>Submitting requests a fresh assessment. Acceptance records your engineering review; it does not authorize replacement or book work.</p><label>Decision<select value={decision} onChange={e=>setDecision(e.target.value)}>{['accepted','rejected','deferred'].map(v=><option key={v}>{v}</option>)}</select></label><label>Review rationale<textarea name="rationale" required minLength={3} maxLength={2000}/></label><button>Save reviewed assessment</button></fieldset></form>}
 <ul>{data?.reviews?.map(r=><li key={r.id}><strong>{r.snapshot.recommendation_category || 'Recommendation'}: {r.decision}</strong>. {r.rationale} — {new Date(r.created_at).toLocaleString()} (reviewer {r.actor_id})</li>)}</ul>
 {!readOnly&&data&&<details><summary>Recurring service policy</summary><form key={p?.updated_at||'new'} onSubmit={policy}><fieldset disabled={action.busy}><legend>Approved equipment service policy</legend><p>Use an approved manufacturer/engineering interval. Generate a pending task for the next service date; repeated generation does not duplicate it. Scheduling still requires human confirmation.</p><div className="form-grid">
 <label>Service title<input name="title" required maxLength={100} defaultValue={p?.title||'Routine service'}/></label>
 <label>Interval (days)<input name="interval" type="number" min="1" max="3650" required defaultValue={p?.interval_days||365}/></label>
 <label>Last service date<input name="last" type="date" required defaultValue={p?.last_service_date||''}/></label>
 <label>Duration (minutes)<input name="duration" type="number" required min="1" max="1440" defaultValue={p?.duration_minutes||60}/></label>
 <label>Qualification<input name="qualification" required maxLength={100} defaultValue={p?.required_qualification||device.device_type||'General'}/></label>
 <label>Priority<select name="priority" defaultValue={p?.priority||'Medium'}>{['Low','Medium','High'].map(v=><option key={v}>{v}</option>)}</select></label>
 <label>Approved policy source / rationale<textarea name="source" required minLength={3} maxLength={2000} defaultValue={p?.source||''}/></label></div>
 <label><input name="active" type="checkbox" defaultChecked={p?.active??true}/> Policy active</label><button>Save service policy</button>
 </fieldset></form>{p&&<button disabled={action.busy||!p.active} onClick={()=>action.run(`/api/workflow/equipment/${device.id}/service-policy/generate`,{},onChanged)}>Generate next service task</button>}</details>}
 {data?.history?.some(h=>!h.aggregates_applied)&&!readOnly&&<details><summary>Reconcile completed work with lifecycle totals</summary><p>Apply only costs and repairs that are not already included in this equipment’s totals. Each record can be applied once. Routine service need not count as a repair.</p>{data.history.filter(h=>!h.aggregates_applied).map(h=><form key={h.id} onSubmit={e=>reconcile(e,h.id)}><fieldset disabled={action.busy}><legend>{h.title}: CAD {h.actual_cost}</legend><label><input type="checkbox" name="repair"/> This was a repair event</label><label>Confirm why this is not already included<textarea name="reason" required minLength={3} maxLength={2000}/></label><button>Apply to lifecycle totals</button></fieldset></form>)}</details>}
 </section>
}
