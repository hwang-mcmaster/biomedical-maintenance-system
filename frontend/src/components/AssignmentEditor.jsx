import {useState} from 'react'
import {useMutation,nextTorontoDay} from './workflowHelpers'
import MutationStatus from './MutationStatus'

export default function AssignmentEditor({assignment,technicians,onChanged}) {
 const [open,setOpen]=useState(false),action=useMutation()
 function submit(e){e.preventDefault();const f=new FormData(e.currentTarget);action.run(`/api/workflow/assignments/${assignment.id}/reschedule`,{technician_id:f.get('technician'),date:f.get('date'),start:f.get('start'),expected_technician_id:assignment.technician_id,expected_start:assignment.starts_at,reason:f.get('reason'),acknowledge_late:f.get('late')==='on'},()=>{setOpen(false);onChanged()})}
 return <><button type="button" className="secondary" onClick={()=>setOpen(!open)}>Change assignment</button>{open&&<form onSubmit={submit}><fieldset disabled={action.busy}><legend>Reschedule {assignment.title}</legend><label>Technician<select name="technician" defaultValue={assignment.technician_id}>{technicians.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label><label>Toronto date<input name="date" type="date" required defaultValue={nextTorontoDay()}/></label><label>Toronto start<input name="start" type="time" required defaultValue="09:00"/></label><label>Reason<textarea name="reason" required minLength={3} maxLength={2000}/></label><label><input type="checkbox" name="late"/> Acknowledge a late service/review target if applicable</label><p>Duration remains unchanged. Qualifications, availability and booking conflicts are checked before saving.</p><button>Confirm assignment change</button></fieldset></form>}<MutationStatus action={action}/></>
}
