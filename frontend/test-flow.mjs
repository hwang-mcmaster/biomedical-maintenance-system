import { JSDOM } from 'jsdom'
import { readFileSync, readdirSync } from 'node:fs'
import assert from 'node:assert/strict'

const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173', runScripts: 'outside-only' })
const w = dom.window
const id = '49e7403c-a464-44be-bc4c-c1741b53ec11'
let records = [], posts = 0, releaseSave, assessmentCalls = 0
let failList = false, failAssessment = false
const response = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body })
const asOf = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Toronto', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const calculated = (record) => {
  const age = Math.max(0, (Date.parse(`${asOf}T00:00:00Z`) - Date.parse(`${record.in_service_date}T00:00:00Z`)) / 86400000) / 365.25
  return { ...record, calculated_as_of: asOf, age_years: age.toFixed(2), avg_annual_cost: age > 0 ? (Number(record.total_historical_cost) / age).toFixed(2) : null }
}
w.fetch = async (url, options = {}) => {
  const path = new URL(url).pathname
  if (path.endsWith('/assessment')) {
    assert.equal(options.method, 'GET')
    assert.equal(options.cache, 'no-store')
    assessmentCalls++
    if (failAssessment) return response({ detail: 'Assessment service unavailable. Retry later.' }, 503)
    return response({ equipment_id: id, risk_score: 0.625, risk_level: 'medium', assessed_at: '2026-10-20T12:00:00Z', method: 'AI model',
      recommendation: 'Review repair history with the engineering team.', limitation: 'Synthetic data; not failure probability.',
      prediction: { risk_level: 'medium', repair_rate_per_year: 1.2, predicted_annual_cost: 600,
        cost_error_range: 149.08, projected_cost_next_years: 3000, projection_years: 5,
        warnings: ['Manufacturer not in training data.'] } })
  }
  if (options.method === 'POST') {
    posts++
    const payload = JSON.parse(options.body)
    if (records.some((r) => r.asset_tag === payload.asset_tag)) return response({ detail: 'Asset tag or serial number already exists. Use unique values.' }, 409)
    await new Promise(resolve => { releaseSave = resolve })
    const record = { ...payload, id }; records.push(record)
    assert.equal(Object.keys(payload).length, 6)
    assert.equal('age_years' in payload, false)
    assert.equal('avg_annual_cost' in payload, false)
    return response(calculated(record), 201)
  }
  if (options.method === 'PUT') {
    records = [{ ...JSON.parse(options.body), id }]
    return response(calculated(records[0]))
  }
  if (options.method === 'DELETE') { records = []; return response(null, 204) }
  if (path.endsWith('/health')) return response({ status: 'ok', message: 'API ready' })
  if (path.endsWith('/ready')) return response({ status: 'ok', message: 'Database ready' })
  return failList ? response({ detail: 'Database unavailable.' }, 503) : response(records.map(calculated))
}
const bundle = readdirSync('dist/assets').find(name => name.endsWith('.js'))
w.eval(readFileSync(`dist/assets/${bundle}`, 'utf8'))
const wait = () => new Promise(resolve => setTimeout(resolve, 50))
async function until(check, label) {
  for (let i = 0; i < 60; i++) { if (check()) return; await wait() }
  throw new Error(`Timed out: ${label}`)
}
const text = () => w.document.body.textContent
const button = (label) => [...w.document.querySelectorAll('button')].find(b => b.textContent === label)
async function setInput(key, value) {
  const input = w.document.getElementById(key)
  const prototype = input.tagName === 'SELECT' ? w.HTMLSelectElement.prototype : w.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value)
  input.dispatchEvent(new w.Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  await wait()
}
const submit = () => w.document.querySelector('form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }))
const values = { asset_tag: 'TEST-1', serial_number: '0000123', manufacturer: 'Getinge SERVOi',
  in_service_date: '2003-03-03', repair_events: '19', total_historical_cost: '9678.12' }
await until(() => text().includes('No equipment found'), 'initial inventory')
assert.equal(w.document.querySelectorAll('form input').length, 6)
assert.equal(w.document.querySelectorAll('form select').length, 0)
for (const key of ['name', 'type', 'location', 'status', 'firmware_version', 'assumed_replacement_cost']) assert.equal(w.document.getElementById(key), null)
submit(); await wait(); assert.equal(posts, 0); assert.match(text(), /This field is required/)
for (const [key, value] of Object.entries(values)) await setInput(key, value)
assert.equal(w.document.querySelectorAll('form output').length, 2)
assert.equal(w.document.getElementById('age_years').tagName, 'OUTPUT')
assert.equal(w.document.getElementById('avg_annual_cost').tagName, 'OUTPUT')
assert.equal(w.document.getElementById('avg_annual_cost').textContent, Number(calculated(values).avg_annual_cost).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
await setInput('total_historical_cost', '-1')
submit(); await wait(); assert.equal(posts, 0)
assert.match(w.document.getElementById('total_historical_cost-error').textContent, /non-negative/)
await setInput('total_historical_cost', '9678.12')
await setInput('in_service_date', asOf)
submit(); await wait(); assert.equal(posts, 0)
assert.match(w.document.getElementById('in_service_date-error').textContent, /before today/)
await setInput('in_service_date', '2003-03-03')
submit(); await until(() => posts === 1, 'POST')
assert.equal(w.document.querySelector('fieldset').disabled, true)
submit(); await wait(); assert.equal(posts, 1)
releaseSave()
await until(() => w.document.querySelector('tbody'), 'table refresh')
assert.match(text(), /Equipment saved/)
assert.equal(w.document.getElementById('asset_tag').value, '')
assert.match(w.document.querySelector('tbody').textContent, /0000123/)
assert.equal(w.document.querySelector('td[data-field=age_years]').textContent, calculated(values).age_years)
assert.equal(records[0].age_years, undefined)
assert.equal(w.document.getElementById('repair_events').value, '0')
assert.equal(w.document.getElementById('total_historical_cost').value, '0')
assert.equal(w.document.querySelector('fieldset').disabled, false)
button('Details & assessment').click(); await wait()
button('Assess equipment').click()
await until(() => text().includes('Repair intensity: medium'), 'assessment')
assert.equal(assessmentCalls, 1)
assert.match(text(), /0\.625/)
assert.match(text(), /not the chance of failure/)
assert.match(text(), /600\.00/)
assert.match(text(), /Manufacturer not in training data/)
assert.match(text(), /not failure probability/)
failAssessment = true
button('Assess equipment').click()
await until(() => text().includes('Assessment service unavailable'), 'assessment error')
assert.doesNotMatch(text(), /Repair intensity: medium/)
failAssessment = false
button('Assess equipment').click()
await until(() => text().includes('Repair intensity: medium'), 'assessment retry')
button('Edit').click(); await wait()
assert.equal(w.document.getElementById('asset_tag').value, 'TEST-1')
const oldAgePreview = w.document.getElementById('age_years').textContent
await setInput('in_service_date', '2000-01-01')
assert.notEqual(w.document.getElementById('age_years').textContent, oldAgePreview)
await setInput('total_historical_cost', '321.09')
await setInput('repair_events', '12')
submit(); await until(() => text().includes('Equipment updated'), 'update')
await until(() => w.document.querySelector('tbody').textContent.includes('321.09'), 'updated table')
assert.equal(records[0].repair_events, 12)
assert.doesNotMatch(text(), /Repair intensity: medium/)
for (const [key, value] of Object.entries(values)) await setInput(key, value)
submit(); await until(() => text().includes('already exists'), 'duplicate conflict')
assert.equal(w.document.getElementById('serial_number').value, '0000123')
failList = true
button('Refresh table').click()
await until(() => text().includes('Unable to refresh equipment'), 'refresh failure')
assert.match(w.document.querySelector('tbody').textContent, /TEST-1/)
failList = false
button('Refresh table').click()
await until(() => !text().includes('Unable to refresh equipment') && !button('Refresh table').disabled, 'refresh retry')
button('Delete').click(); await wait()
button('Cancel').click(); await wait(); assert.equal(records.length, 1)
button('Delete').click(); await wait(); button('Confirm delete').click()
await until(() => text().includes('No equipment found'), 'delete and refresh')
assert.equal(records.length, 0)
w.fetch = async () => { throw new w.TypeError('Failed to fetch') }
submit(); await until(() => text().includes('Cannot reach the service'), 'connection error')
console.log('Frontend flow passed: required validation, save/refresh, duplicate prevention, AI results/warnings/retry, edit, duplicate conflict, refresh failure/retry, delete confirmation, and connection errors.')
dom.window.close()
