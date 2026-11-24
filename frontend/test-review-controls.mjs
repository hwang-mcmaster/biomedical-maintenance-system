import {JSDOM} from 'jsdom'
import {readFileSync,readdirSync} from 'node:fs'
import assert from 'node:assert/strict'
const bundle=readFileSync(`dist/assets/${readdirSync('dist/assets').find(f=>f.endsWith('.js'))}`,'utf8')
const d=new JSDOM('<div id="root"></div>',{url:'http://localhost:5173/#/equipment/eq1',runScripts:'outside-only'}),w=d.window
const device={id:'eq1',asset_tag:'REVIEW-TEST',manufacturer:'Getinge',serial_number:'001',device_type:'Ventilator',in_service_date:'2020-01-01',criticality:'Critical'}
const policy={title:'Approved service',interval_days:30,last_service_date:'2020-01-01',duration_minutes:60,required_qualification:'ventilator',priority:'Medium',source:'Approved manual',active:true}
const posts=[]
w.fetch=async(url,options={})=>{const path=new URL(url,w.location.origin).pathname,reply=body=>({ok:true,status:200,json:async()=>body})
 if(options.method&&options.method!=='GET'){assert.equal(options.headers['X-CSRF-Token'],'fixture');posts.push({path,body:JSON.parse(options.body)});return reply({id:'saved'})}
 if(path==='/api/auth/me')return reply({user:{id:'coordinator',name:'Reviewer',role:'coordinator'},csrf_token:'fixture'})
 if(path==='/api/equipment')return reply([device])
 if(path==='/api/equipment/options')return reply({device_types:['Ventilator'],statuses:['Operational'],criticalities:['Routine','Important','Critical']})
 if(path==='/api/workflow/assignments')return reply([{id:'assignment1',task_id:'task1',equipment_id:'eq1',title:'Service',status:'scheduled',starts_at:'2030-01-01T14:00:00Z',ends_at:'2030-01-01T15:00:00Z',technician_id:'tech-old',technician_name:'Old tech',priority:'High'}])
 if(path==='/api/workflow/technicians')return reply([{id:'tech-old',name:'Old tech',qualifications:['ventilator'],availability:[]},{id:'tech-new',name:'New tech',qualifications:['ventilator'],availability:[]}])
 if(path==='/api/workflow/equipment/eq1')return reply({tasks:[],assignments:[],events:[],reviews:[],service_policy:policy,history:[{id:'h1',title:'Repair',actual_cost:'30',completed_at:'2026-01-01',aggregates_applied:false}]})
 return reply([])
}
const pause=()=>new Promise(r=>setTimeout(r,20))
async function until(f){for(let i=0;i<150;i++){if(f())return;await pause()}throw Error('UI timed out')}
function button(text){return [...w.document.querySelectorAll('button')].find(b=>b.textContent===text)}
function submit(legend,values){const field=[...w.document.querySelectorAll('fieldset')].find(f=>f.querySelector('legend')?.textContent===legend);assert.ok(field,legend);for(const [name,value] of Object.entries(values))field.querySelector(`[name="${name}"]`).value=value;field.closest('form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}))}
w.eval(bundle)
await until(()=>button('maintenance'));button('maintenance').click()
await until(()=>button('Save reviewed assessment'))
submit('Record recommendation review',{rationale:'Reviewed against service history'})
await until(()=>posts.length===1);assert.equal(posts[0].body.decision,'accepted')
await pause();await pause()
submit('Approved equipment service policy',{})
await until(()=>posts.length===2);assert.equal(posts[1].body.interval_days,30);assert.equal(posts[1].body.source,'Approved manual')
await pause();await pause();button('Generate next service task').click()
await until(()=>posts.length===3);assert.match(posts[2].path,/service-policy\/generate$/)
await pause();await pause();submit('Repair: CAD 30',{reason:'Not included in imported totals'})
await until(()=>posts.length===4);assert.equal(posts[3].body.repair_event,false);assert.match(posts[3].path,/history\/h1\/reconcile$/)
await pause();await pause();w.location.hash='/scheduling'
await until(()=>button('Change assignment'));button('Change assignment').click()
await until(()=>[...w.document.querySelectorAll('legend')].some(x=>x.textContent==='Reschedule Service'))
submit('Reschedule Service',{technician:'tech-new',reason:'Reviewed new assignment'})
await until(()=>posts.length===5);assert.equal(posts[4].body.expected_technician_id,'tech-old');assert.equal(posts[4].body.technician_id,'tech-new');assert.match(posts[4].path,/assignments\/assignment1\/reschedule$/)
d.window.close()
console.log('Review controls passed: reviewed assessment, approved policy, service generation, one-time reconciliation and CSRF.')
