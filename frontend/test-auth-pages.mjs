import {JSDOM} from 'jsdom'
import {readFileSync,readdirSync} from 'node:fs'
import assert from 'node:assert/strict'
const bundle=readFileSync(`dist/assets/${readdirSync('dist/assets').find(f=>f.endsWith('.js'))}`,'utf8')
const pause=()=>new Promise(r=>setTimeout(r,40))
async function scenario(role){const d=new JSDOM('<div id="root"></div>',{url:'http://localhost:5173/#/overview',runScripts:'outside-only'}),w=d.window;let signed=false,seen=[]
w.fetch=async(url,options={})=>{const path=new URL(url,w.location.origin).pathname;seen.push(path);const reply=(body,status=200)=>({ok:status<400,status,json:async()=>body})
if(path==='/api/auth/me')return reply({detail:'Sign in'},401)
if(path==='/api/auth/login'){signed=true;return reply({user:{name:'Fixture',role},csrf_token:'fixture'})}
if(path==='/api/auth/logout'){assert.equal(options.headers['X-CSRF-Token'],'fixture');return reply({})}
assert.ok(signed,'Operational request before login');return reply([])}
w.eval(bundle);for(let i=0;i<60&&!w.document.querySelector('input[name=email]');i++)await pause()
assert.equal(seen.filter(p=>p!=='/api/auth/me').length,0)
for(const [name,value] of [['email','fixture@example.test'],['password','fixture-long-password']]){const input=w.document.querySelector(`input[name=${name}]`);input.value=value}
w.document.querySelector('form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));for(let i=0;i<60&&!w.document.querySelector('.service-sidebar');i++)await pause()
assert.ok(w.document.querySelector('.service-sidebar'))
assert.equal(!!w.document.querySelector('nav a[href="#/administration"]'),role==='admin')
assert.equal(!!w.document.querySelector('nav a[href="#/scheduling"]'),role!=='technician')
w.location.hash='/equipment';await pause();assert.match(w.document.body.textContent,/Equipment inventory/)
assert.equal(!![...w.document.querySelectorAll('button')].find(b=>b.textContent==='Add equipment'),role!=='technician')
;[...w.document.querySelectorAll('button')].find(b=>b.textContent==='Sign out').click();await pause();assert.ok(w.document.querySelector('input[name=email]'));d.window.close()}
for(const role of ['admin','coordinator','technician'])await scenario(role)
console.log('Account UI passed: login gate, navigation, role-aware actions, CSRF logout and session clearing.')
