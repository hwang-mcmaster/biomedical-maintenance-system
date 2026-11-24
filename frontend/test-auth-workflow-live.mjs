// Real React + authenticated FastAPI + PostgreSQL + unchanged local AI service.
import {JSDOM} from 'jsdom'
import {readFileSync,readdirSync,writeFileSync} from 'node:fs'
import {execFileSync} from 'node:child_process'
import {randomUUID} from 'node:crypto'
import assert from 'node:assert/strict'
const base=process.env.TEST_API_URL||'http://127.0.0.1:8000',origin='http://localhost:5173',runId=randomUUID()
const bundle=readFileSync(`dist/assets/${readdirSync('dist/assets').find(f=>f.endsWith('.js'))}`,'utf8')
const pause=()=>new Promise(r=>setTimeout(r,40))
let dom,credentials,cookie='',equipmentId,plan,csrf='',assessment,confirmed=false
const timings={}
function fixture(action){return JSON.parse(execFileSync('../backend/venv/Scripts/python.exe',['ui_test_fixture.py'],{
  cwd:'../backend',input:JSON.stringify({action,run_id:runId}),encoding:'utf8',stdio:['pipe','pipe','pipe']}))}
async function until(test,label){for(let i=0;i<750;i++){if(test())return;await pause()}throw Error('Timed out: '+label)}
function button(text){return [...dom.window.document.querySelectorAll('button')].find(b=>b.textContent===text)}
async function fill(selector,value){const w=dom.window,input=w.document.querySelector(selector);assert.ok(input,selector)
 const proto=input.tagName==='SELECT'?w.HTMLSelectElement.prototype:input.tagName==='TEXTAREA'?w.HTMLTextAreaElement.prototype:w.HTMLInputElement.prototype
 Object.getOwnPropertyDescriptor(proto,'value').set.call(input,value);input.dispatchEvent(new w.Event(input.tagName==='SELECT'?'change':'input',{bubbles:true}));await pause()}
async function fillLabel(form,label,value){const controls=[...dom.window.document.querySelectorAll(`${form} label`)]
 const node=controls.find(l=>l.textContent.startsWith(label))?.querySelector('input,textarea,select');assert.ok(node,label)
 node.dataset.testField='active';await fill('[data-test-field=active]',value);delete node.dataset.testField}
function submit(selector){dom.window.document.querySelector(selector).dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}))}
function mount(route='/overview'){
 dom=new JSDOM('<div id="root"></div>',{url:`${origin}/#${route}`,runScripts:'outside-only'})
 dom.window.fetch=async(url,options={})=>{
   const path=new URL(url,origin).pathname,start=performance.now()
   const controller=new AbortController(),abort=()=>controller.abort()
   if(options.signal?.aborted)controller.abort()
   options.signal?.addEventListener('abort',abort,{once:true})
   let response
   try{response=await fetch(base+path,{...options,signal:controller.signal,headers:{...options.headers,Origin:origin,...(cookie?{Cookie:cookie}:{})}})}
   finally{options.signal?.removeEventListener('abort',abort)}
   const session=response.headers.getSetCookie().find(v=>v.startsWith('maintenance_session='))
   if(session)cookie=session.split(';')[0]
   if(response.ok){
     const body=await response.clone().json()
     if(path==='/api/auth/login'||path==='/api/auth/me')csrf=body.csrf_token
     if(path==='/api/equipment'&&options.method==='POST')equipmentId=body.id
     if(path.endsWith('/assessment'))assessment=body
     if(path==='/api/workflow/schedules/preview')plan=body
     if(path.endsWith('/confirm'))confirmed=true
     if(options.method==='POST'||path.endsWith('/assessment'))timings[path]=Math.round(performance.now()-start)
   }
   return response
 }
 dom.window.eval(bundle)
}
let outcome
try{
 credentials=fixture('create');mount()
 await until(()=>dom.window.document.querySelector('input[name=email]'),'sign-in gate')
 await fill('input[name=email]',credentials.email);await fill('input[name=password]',credentials.password);submit('form')
 await until(()=>dom.window.document.querySelector('.service-sidebar'),'authenticated workspace')
 dom.window.location.hash='/equipment/new'
 await until(()=>dom.window.document.getElementById('equipment-form')&&!dom.window.document.querySelector('#equipment-form fieldset').disabled,'equipment form choices')
 for(const [key,value] of Object.entries({asset_tag:credentials.tag,serial_number:'000'+runId.replaceAll('-',''),manufacturer:'Getinge',
   in_service_date:'2020-01-01',repair_events:'20',total_historical_cost:'10000.00',device_type:'Ventilator',model_name:'SERVOi',model_number:'SERVOi',status:'Operational'}))await fill('#'+key,value)
 submit('#equipment-form')
 await until(()=>equipmentId&&dom.window.document.getElementById('details-heading')?.textContent.includes(credentials.tag),'saved equipment details')
 button('assessment').click();await pause();button('Assess equipment').click()
 await until(()=>assessment&&dom.window.document.querySelector('.assessment'),'live model recommendation')
 assert.match(dom.window.document.querySelector('.assessment').textContent,/chance of failure/)
 button('maintenance').click();await pause()
 await fillLabel('#maintenance-task-form','Task title',credentials.tag)
 await fillLabel('#maintenance-task-form','Required qualification',credentials.qualification)
 submit('#maintenance-task-form')
 await until(()=>dom.window.document.body.textContent.includes('Assessment saved with latest task'),'saved assessment and task')
 dom.window.location.hash='/technicians'
 await until(()=>dom.window.document.getElementById('technician-form'),'technician form')
 await fillLabel('#technician-form','Technician name',credentials.tag)
 await fillLabel('#technician-form','Qualifications',credentials.qualification)
 submit('#technician-form')
 await until(()=>dom.window.document.querySelector('.technician-list')?.textContent.includes(credentials.tag),'saved technician availability')
 dom.window.location.hash='/scheduling'
 await until(()=>dom.window.document.querySelector(`input[aria-label="Include ${credentials.tag} for ${credentials.tag}"]`),'task picker')
 dom.window.document.querySelector(`input[aria-label="Include ${credentials.tag} for ${credentials.tag}"]`).click();await pause()
 await until(()=>!button('Generate saved schedule preview').disabled,'planning ready')
 submit('#saved-schedule-form')
 await until(()=>plan&&button('Confirm schedule'),'saved plan')
 assert.ok(plan.metrics.validation.passed);assert.ok(plan.comparison.same_inputs)
 assert.ok(dom.window.document.querySelector('.schedule-measurements'))
 button('Confirm schedule').click();await until(()=>confirmed&&!button('Confirm schedule'),'booking confirmation')
 dom.window.close();mount('/equipment/'+equipmentId)
 await until(()=>dom.window.document.getElementById('details-heading'),'authenticated reload')
 button('maintenance').click()
 await until(()=>dom.window.document.body.textContent.includes('Status: scheduled'),'persisted assignment display')
 const response=await fetch(base+'/api/workflow/equipment/'+equipmentId,{headers:{Cookie:cookie,Origin:origin,'X-CSRF-Token':csrf}})
 assert.equal(response.status,200);const context=await response.json()
 assert.equal(context.assignments.length,1);assert.equal(context.tasks[0].status,'scheduled')
 assert.match(context.assignments[0].priority_reason,/Repair intensity/)
 outcome={generated_at:new Date().toISOString(),scope:'Real React rendered in JSDOM; real HTTP, session/CSRF, PostgreSQL and local AI. Layout verified separately.',
   passed:true,flow:['login','React equipment creation','PostgreSQL retrieval','AI assessment','recommendation/task priority','technician availability','baseline comparison','confirmation','reload'],
   model_version:assessment.prediction.model_version,sample_recommendation:assessment.recommendation,
   risk_level:assessment.risk_level,repair_rate_percentile:assessment.risk_score,request_timings_ms:timings,
   schedule:{metrics:plan.metrics,comparison:plan.comparison},screenshots:'See the separate demo guide; JSDOM does not capture screenshots.'}
 console.log('Authenticated live flow passed: React creation → PostgreSQL → AI recommendation → task → technician → schedule comparison → confirmation → reload.')
}finally{
 dom?.window.close()
 const cleaned=fixture('cleanup')
 if(outcome){outcome.fixture_cleanup=cleaned.cleaned;writeFileSync('../backend/validation/authenticated-ui-results.json',JSON.stringify(outcome,null,2)+'\n')}
}
