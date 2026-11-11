import { JSDOM } from 'jsdom'
import { readFileSync, readdirSync } from 'node:fs'
import assert from 'node:assert/strict'

const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173', runScripts: 'outside-only' })
const w = dom.window
const id = '49e7403c-a464-44be-bc4c-c1741b53ec11'
let equipment = [{ id, asset_tag: 'SCHEDULE-TEST-1', serial_number: '0001', manufacturer: 'Getinge',
  model_name: 'SERVOi', device_type: 'Ventilator', department: 'ICU', status: 'Operational',
  in_service_date: '2020-01-01', repair_events: 3, total_historical_cost: '1000.00',
  age_years: '6.00', avg_annual_cost: '166.67', calculated_as_of: '2026-11-04' }]
let calls = 0, releasePreview, fail = false, unassigned = false
const response = (body, status = 200) => ({ ok: status < 300, status, json: async () => body })
w.fetch = async (url, options = {}) => {
  const path = new URL(url).pathname
  if (path.startsWith('/api/workflow/')) return response(path.includes('/equipment/') ? {tasks:[],assignments:[],history:[],events:[]} : [])
  if (path === '/api/scheduling/preview') {
    calls++
    const payload = JSON.parse(options.body)
    assert.equal(payload.tasks.length, 3)
    assert.equal(payload.technicians.length, 2)
    assert.equal(payload.existing_bookings.length, 1)
    assert.ok(payload.tasks.every(task => task.equipment_id === id))
    assert.equal(typeof payload.tasks[0].duration_minutes, 'number')
    assert.ok(Array.isArray(payload.technicians[0].qualifications))
    if (calls === 1) await new Promise(resolve => { releasePreview = resolve })
    if (fail) return response({ detail: 'Scheduling connection unavailable. Retry.' }, 503)
    const times = [['10:00', '11:00'], ['13:00', '14:30'], ['11:00', '11:30']]
    const assignments = payload.tasks.slice(0, unassigned ? 2 : 3).map((task, index) => ({
      task_id: task.id, title: task.title, equipment_id: id, asset_tag: 'SCHEDULE-TEST-1',
      technician_id: payload.technicians[index === 2 ? 1 : 0].id, technician_name: payload.technicians[index === 2 ? 1 : 0].name,
      priority: task.priority, required_qualification: task.required_qualification,
      duration_minutes: task.duration_minutes, start: `${payload.schedule_date}T${times[index][0]}:00-05:00`, end: `${payload.schedule_date}T${times[index][1]}:00-05:00`,
    }))
    return response({ schedule_date: payload.schedule_date, timezone: 'America/Toronto', persisted: false,
      algorithm: 'Priority first, earliest feasible slot', assignments,
      unscheduled: unassigned ? [{ task_id: payload.tasks[2].id, title: payload.tasks[2].title, asset_tag: 'SCHEDULE-TEST-1', priority: 'Low', reason: 'No qualified technician available.' }] : [],
      notices: ['Preview only; not saved.'] })
  }
  if (path.endsWith('/options')) return response({ device_types: ['Ventilator','Other'], statuses: ['Operational','Under Maintenance','Inactive'] })
  if (path.endsWith('/health')) return response({ status: 'ok', message: 'API ready' })
  if (path.endsWith('/ready')) return response({ status: 'ok', message: 'Database ready' })
  return response(equipment)
}
const bundle = readdirSync('dist/assets').find(name => name.endsWith('.js'))
w.eval(readFileSync(`dist/assets/${bundle}`, 'utf8'))
const wait = () => new Promise(resolve => setTimeout(resolve, 40))
async function until(check, label) {
  for (let index = 0; index < 100; index++) { if (check()) return; await wait() }
  throw new Error(`Timed out: ${label}. ${w.document.body.textContent}`)
}
const button = (label) => [...w.document.querySelectorAll('button')].find(node => node.textContent === label)
const text = () => w.document.body.textContent
const submit = () => w.document.getElementById('scheduling-form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }))
async function setInput(label, value) {
  const input = w.document.querySelector(`[aria-label="${label}"]`)
  const proto = input.tagName === 'SELECT' ? w.HTMLSelectElement.prototype : w.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(input, value)
  input.dispatchEvent(new w.Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  await wait()
}
await until(() => button('Load demo scheduling inputs') && !button('Load demo scheduling inputs').disabled, 'inventory loaded')
button('Load demo scheduling inputs').click(); await wait()
assert.match(text(), /Demo task\/technician data loaded/)
await setInput('Task 1 duration (minutes)', '0')
submit(); await wait(); assert.equal(calls, 0)
assert.match(text(), /duration from 1 to 1440/)
await setInput('Task 1 duration (minutes)', '60')
submit(); await until(() => releasePreview, 'request started')
assert.ok(button('Generating…').disabled)
submit(); await wait(); assert.equal(calls, 1)
releasePreview()
await until(() => text().includes('3 scheduled, 0 unassigned'), 'preview results')
assert.match(text(), /Preview only; not saved/)
assert.ok(w.document.querySelector('.schedule-results table'))
await setInput('Task 1 title', 'Updated inspection')
assert.equal(w.document.querySelector('.schedule-results'), null)
fail = true
submit(); await until(() => text().includes('Scheduling connection unavailable'), 'server failure')
assert.ok(!button('Generate schedule preview').disabled)
fail = false; unassigned = true
submit(); await until(() => text().includes('2 scheduled, 1 unassigned'), 'retry with unassigned task')
assert.match(text(), /No qualified technician available/)
equipment = equipment.map(item => ({ ...item, model_name: 'External update' }))
button('Refresh table').click()
await until(() => text().includes('Equipment or inputs changed'), 'stale result invalidated')
assert.equal(w.document.querySelector('.schedule-results'), null)
button('Clear scheduling inputs').click(); await wait()
submit(); await wait()
assert.match(text(), /Add at least one technician/)
assert.match(text(), /Add at least one maintenance task/)
console.log('Scheduling UI passed: real-equipment references, demo input editing, validation, disabled state, duplicate prevention, preview, unassigned reasons, retry and stale results.')
dom.window.close()
