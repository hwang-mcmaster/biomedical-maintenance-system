import {JSDOM} from 'jsdom'
import {readFileSync,readdirSync} from 'node:fs'
import assert from 'node:assert/strict'
const bundle=readFileSync(`dist/assets/${readdirSync('dist/assets').find(f=>f.endsWith('.js'))}`,'utf8')
const pause=()=>new Promise(r=>setTimeout(r,20))
async function until(test,label){for(let i=0;i<150;i++){if(test())return;await pause()}throw Error('Timed out: '+label)}
const devices=Array.from({length:200},(_,i)=>({id:`equipment-${i}`,asset_tag:`VALIDATION-${String(i).padStart(3,'0')}`,
  serial_number:`000${i}`,manufacturer:'Getinge',in_service_date:'2020-01-01',device_type:'Ventilator',
  repair_events:10,total_historical_cost:'1000',status:'Operational',age_years:6,avg_annual_cost:166,calculated_as_of:'2026-11-19'}))
const tasks=Array.from({length:150},(_,i)=>({id:`task-${i}`,equipment_id:devices[i].id,asset_tag:devices[i].asset_tag,
  title:`Review ${i}`,priority:'High',priority_reason:'Fixture repair intensity',status:'pending',due_date:'2030-01-01',
  duration_minutes:60,required_qualification:'ventilator'}))
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost:5173/#/equipment',runScripts:'outside-only'}),w=dom.window
let expired=false,failed=false,inventory=devices,posted
const reply=(body,status=200)=>({ok:status<400,status,json:async()=>body})
w.fetch=async(url,options={})=>{
  const path=new URL(url,w.location.origin).pathname
  if(path==='/api/auth/me')return reply({user:{id:'fixture',name:'Validation',role:'coordinator'},csrf_token:'csrf-fixture'})
  if(expired)return reply({detail:'Your session expired. Sign in again.'},401)
  if(path==='/api/equipment')return failed?reply({},503):reply(inventory)
  if(path==='/api/equipment/options')return reply({device_types:['Ventilator'],statuses:['Operational']})
  if(path==='/api/workflow/tasks')return reply(tasks)
  if(path==='/api/workflow/schedules/preview'){
    assert.equal(options.headers['X-CSRF-Token'],'csrf-fixture')
    posted=JSON.parse(options.body)
    return reply({detail:'Availability changed. Refresh before retrying.'},409)
  }
  return reply([])
}
function button(text){return [...w.document.querySelectorAll('button')].find(b=>b.textContent===text)}
function value(input,text){Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype,'value').set.call(input,text);input.dispatchEvent(new w.Event('input',{bubbles:true}))}
try{
  w.eval(bundle)
  await until(()=>w.document.querySelectorAll('td[data-field=asset_tag]').length===15,'200-record inventory')
  assert.match(w.document.body.textContent,/200 records. Page 1 of 14/)
  for(let i=0;i<13;i++){button('Next').click();await pause()}
  assert.equal(w.document.querySelectorAll('td[data-field=asset_tag]').length,5)
  // A refresh shrinking inventory must clamp the page instead of showing an empty stale page.
  inventory=devices.slice(0,1);button('Refresh table').click()
  await until(()=>w.document.querySelectorAll('td[data-field=asset_tag]').length===1,'pagination clamp')
  assert.match(w.document.body.textContent,/Page 1 of 1/)
  value(w.document.querySelector('input[placeholder]'),'missing-filter');await pause()
  assert.match(w.document.body.textContent,/No equipment matches these filters/)
  w.location.hash='/scheduling'
  await until(()=>w.document.body.textContent.includes('exceeds the 100-task limit'),'loaded scheduling cohort')
  assert.ok(button('Generate saved schedule preview').disabled)
  assert.match(w.document.body.textContent,/exceeds the 100-task limit/)
  button('Select first 100 pending tasks').click();await pause()
  assert.equal(w.document.querySelectorAll('.planning-task-list input:checked').length,100)
  assert.ok(!button('Generate saved schedule preview').disabled)
  w.document.getElementById('saved-schedule-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}))
  await until(()=>posted,'planning request')
  assert.equal(posted.task_ids.length,100)
  assert.equal(tasks.length,150,'Unselected work remains present')
  await until(()=>w.document.body.textContent.includes('Availability changed'),'conflict explanation')
  w.location.hash='/equipment';await pause();failed=true;button('Refresh table').click()
  await until(()=>w.document.body.textContent.includes('temporarily unavailable'),'API failure message')
  failed=false;expired=true;button('Refresh table').click()
  await until(()=>w.document.querySelector('input[name=email]'),'expired-session login gate')
  assert.match(w.document.body.textContent,/Your session expired/)
  console.log('Validation UI passed: 200 records, pagination, filters, explicit 100-task batching, conflict/API errors and expired session.')
}finally{w.close()}

// Direct edit URLs must wait for the saved record before initializing form state.
const editDom=new JSDOM('<div id="root"></div>',{url:'http://localhost:5173/#/equipment/equipment-0/edit',runScripts:'outside-only'}),ew=editDom.window
let release
const delayedInventory=new Promise(resolve=>{release=resolve})
ew.fetch=async url=>{
 const path=new URL(url,ew.location.origin).pathname
 if(path==='/api/auth/me')return reply({user:{name:'Validation',role:'coordinator'},csrf_token:'fixture'})
 if(path==='/api/equipment')return delayedInventory
 if(path==='/api/equipment/options')return reply({device_types:['Ventilator'],statuses:['Operational']})
 return reply([])
}
try{
 ew.eval(bundle)
 await until(()=>ew.document.body.textContent.includes('Loading equipment'),'edit waiting for record')
 assert.equal(ew.document.getElementById('equipment-form'),null)
 release(reply(devices))
 await until(()=>ew.document.getElementById('asset_tag')?.value==='VALIDATION-000','saved edit data')
 assert.match(ew.document.getElementById('form-heading').textContent,/Edit equipment: VALIDATION-000/)
 console.log('Direct edit URL passed: waits for saved equipment and initializes existing form values.')
}finally{ew.close()}
