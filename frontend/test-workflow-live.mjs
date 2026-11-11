import {JSDOM} from 'jsdom'
import {readFileSync,readdirSync} from 'node:fs'
import {execFileSync} from 'node:child_process'
import {randomUUID} from 'node:crypto'
import assert from 'node:assert/strict'

const base='http://127.0.0.1:8000',token=randomUUID().replaceAll('-',''),name=`CODEX-W10-UI-${token}`
const techIds=[],runIds=[]
let equipmentId,dom
const bundle=readFileSync(`dist/assets/${readdirSync('dist/assets').find(f=>f.endsWith('.js'))}`,'utf8')
const wait=()=>new Promise(r=>setTimeout(r,50))
async function until(check,label){for(let i=0;i<600;i++){if(check())return;await wait()}throw new Error('Timed out: '+label)}
async function api(path,body){const r=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.ok(r.ok,await r.clone().text());return r.json()}
function mount(){const d=new JSDOM('<div id="root"></div>',{url:'http://localhost:5173',runScripts:'outside-only'});d.window.fetch=async(url,options={})=>{
  const controller=new AbortController(),abort=()=>controller.abort()
  if(options.signal?.aborted)controller.abort()
  options.signal?.addEventListener('abort',abort,{once:true})
  let r
  try {r=await fetch(url.replace('http://localhost:8000',base),{...options,signal:controller.signal})}
  finally {options.signal?.removeEventListener('abort',abort)}
  const path=new URL(url).pathname
  if(r.ok&&options.method==='POST') {const body=await r.clone().json();if(path==='/api/workflow/technicians')techIds.push(body.id);if(path==='/api/workflow/schedules/preview')runIds.push(body.id)}
  return r
};d.window.eval(bundle);return d}
async function fill(form,label,value){const input=[...form.querySelectorAll('label')].find(l=>l.textContent.startsWith(label))?.querySelector('input,select,textarea');assert.ok(input,label)
 const w=dom.window,proto=input.tagName==='SELECT'?w.HTMLSelectElement.prototype:input.tagName==='TEXTAREA'?w.HTMLTextAreaElement.prototype:w.HTMLInputElement.prototype
 Object.getOwnPropertyDescriptor(proto,'value').set.call(input,value);input.dispatchEvent(new w.Event(input.tagName==='SELECT'?'change':'input',{bubbles:true}));await wait()}
function submit(id){dom.window.document.getElementById(id).dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}))}
function button(text){return [...dom.window.document.querySelectorAll('button')].find(b=>b.textContent===text)}
try {
 const eq=await api('/api/equipment',{asset_tag:name,serial_number:'000'+token,manufacturer:'Getinge',model_name:'SERVOi',model_number:'SERVOi',device_type:'Ventilator',in_service_date:'2020-01-01',repair_events:20,total_historical_cost:'10000.00'})
 equipmentId=eq.id;dom=mount()
 await until(()=>[...dom.window.document.querySelectorAll('td[data-field=asset_tag]')].some(e=>e.textContent===name),'inventory')
 const row=[...dom.window.document.querySelectorAll('tr')].find(r=>r.textContent.includes(name));[...row.querySelectorAll('button')].find(b=>b.textContent==='Details & assessment').click()
 await until(()=>dom.window.document.getElementById('maintenance-task-form'),'task form')
 let form=dom.window.document.getElementById('maintenance-task-form');await fill(form,'Task title',name);await fill(form,'Required qualification',token)
 submit('maintenance-task-form')
 await until(()=>[...dom.window.document.querySelectorAll('.workflow-table tbody tr')].some(r=>r.textContent.includes(name)&&r.textContent.includes('Repair intensity')),'assessment-created task')
 form=dom.window.document.getElementById('technician-form');await fill(form,'Technician name',name);await fill(form,'Qualifications',token);submit('technician-form')
 await until(()=>techIds.length===1&&!button('Save technician').disabled,'saved technician')
 const checkbox=dom.window.document.querySelector(`input[aria-label="Schedule ${name} for ${name}"]`);assert.ok(checkbox);checkbox.click();await wait()
 await until(()=>!button('Generate saved schedule preview').disabled,'loaded planning inputs');submit('saved-schedule-form')
 await until(()=>button('Confirm schedule'),'preview')
 assert.match(dom.window.document.querySelector('.schedule-results').textContent,/Repair intensity/)
 button('Confirm schedule').click()
 await until(()=>!button('Confirm schedule')&&[...dom.window.document.querySelectorAll('table')].some(t=>t.querySelector('caption')?.textContent==='Upcoming work and assignment history'&&t.textContent.includes(name)),'confirmed assignment')
 dom.window.close();dom=mount()
 await until(()=>[...dom.window.document.querySelectorAll('table')].some(t=>t.querySelector('caption')?.textContent==='Upcoming work and assignment history'&&t.textContent.includes(name)),'persisted after reload')
 const context=await (await fetch(base+'/api/workflow/equipment/'+equipmentId)).json()
 assert.equal(context.assignments.length,1);assert.equal(context.tasks[0].status,'scheduled');assert.ok(context.latest_saved_assessment.snapshot.prediction.model_version)
 assert.equal(context.assignments[0].technician_id,techIds[0]);assert.match(context.assignments[0].priority_reason,/Repair intensity/)
 console.log('Live saved workflow passed: equipment → AI assessment → priority/task → saved technician → preview → confirmation → reload/persisted assignment.')
} finally {
 dom?.window.close()
 if(equipmentId)execFileSync('../backend/venv/Scripts/python.exe',['-c',`
import json,sys
from app.database import get_connection
e,techs,runs=json.loads(sys.argv[1])
with get_connection() as c:
 c.execute('SELECT pg_advisory_xact_lock(74102026)')
 c.execute('DELETE FROM workflow_events WHERE task_id IN (SELECT id FROM workflow_tasks WHERE equipment_id=%s)',(e,))
 c.execute('DELETE FROM workflow_history WHERE equipment_id=%s',(e,))
 c.execute('DELETE FROM workflow_assignments WHERE equipment_id=%s',(e,))
 c.execute('DELETE FROM workflow_tasks WHERE equipment_id=%s',(e,))
 c.execute('DELETE FROM workflow_assessments WHERE equipment_id=%s',(e,))
 for run in runs:c.execute('DELETE FROM workflow_schedules WHERE id=%s',(run,))
 for tech in techs:c.execute('DELETE FROM workflow_technicians WHERE id=%s',(tech,))
 c.execute('DELETE FROM equipment WHERE equipment_id=%s',(e,))
 c.execute('DELETE FROM workflow_qualifications WHERE name=%s',(sys.argv[2],))
`,JSON.stringify([equipmentId,techIds,runIds]),token],{cwd:'../backend',stdio:'pipe'})
}
