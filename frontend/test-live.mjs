// Opt-in end-to-end test: real React, FastAPI, RDS and the existing AI service.
import { JSDOM } from 'jsdom'
import { readFileSync, readdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import assert from 'node:assert/strict'

const api = process.env.TEST_API_URL || 'http://localhost:8000'
const tag = `CODEX-UI-${randomUUID().replaceAll('-', '')}`
const serialNumber = `000${randomUUID().replaceAll('-', '')}`
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173', runScripts: 'outside-only' })
const w = dom.window
let savedId, assessedResult, scheduleResult, scheduleInput
w.fetch = async (url, options = {}) => {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  options.signal?.addEventListener('abort', abort, { once: true })
  try {
    const path = new URL(url).pathname
    const response = await fetch(`${api}${path}`, { ...options, signal: controller.signal })
    if (path === '/api/scheduling/preview' && response.ok) {
      scheduleInput = JSON.parse(options.body)
      scheduleResult = await response.clone().json()
    }
    if (path.endsWith('/assessment')) {
      assert.equal(options.method, 'GET')
      if (response.ok) assessedResult = await response.clone().json()
    }
    if (options.method === 'POST' && path === '/api/equipment' && response.ok) {
      savedId = (await response.clone().json()).id
    }
    return response
  } finally { options.signal?.removeEventListener('abort', abort) }
}
const wait = () => new Promise(resolve => setTimeout(resolve, 50))
async function until(check, label) {
  for (let i = 0; i < 600; i++) { if (check()) return; await wait() }
  throw new Error(`Timed out: ${label}. Screen: ${w.document.body.textContent}`)
}
const text = () => w.document.body.textContent
const row = () => [...w.document.querySelectorAll('tbody tr')].find(r => r.textContent.includes(tag))
const button = (label, root = w.document) => [...root.querySelectorAll('button')].find(b => b.textContent === label)
async function setInput(key, value) {
  const input = w.document.getElementById(key)
  Object.getOwnPropertyDescriptor(input.tagName === 'SELECT' ? w.HTMLSelectElement.prototype : input.tagName === 'TEXTAREA' ? w.HTMLTextAreaElement.prototype : w.HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new w.Event(input.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  await wait()
}
async function setInputByLabel(label, value) {
  const element = w.document.querySelector(`[aria-label="${label}"]`)
  const prototype = element.tagName === 'SELECT' ? w.HTMLSelectElement.prototype : w.HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, value)
  element.dispatchEvent(new w.Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  await wait()
}
const submit = () => w.document.querySelector('form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }))
try {
  const ready = await fetch(`${api}/api/ready`)
  assert.equal(ready.status, 200, await ready.text())
  const bundle = readdirSync('dist/assets').find(name => name.endsWith('.js'))
  w.eval(readFileSync(`dist/assets/${bundle}`, 'utf8'))
  await until(() => button('Add equipment') && !text().includes('Checking equipment database'), 'initial load')
  assert.equal(w.document.querySelectorAll('#equipment-form input').length, 14)
  for (const [key, value] of Object.entries({
    asset_tag: tag, serial_number: serialNumber, manufacturer: 'Getinge', model_name: 'SERVOi', model_number: 'SERVOi', device_type: 'Ventilator',
    department: 'ICU', department_code: '001', location: 'Room 12', status: 'Operational',
    firmware_version: '1.0', description: 'Live test device', replacement_cost: '20000.00', expected_useful_life: '25',
    in_service_date: '2003-03-03', repair_events: '19', total_historical_cost: '9678.12',
  })) await setInput(key, value)
  submit()
  await until(() => row(), 'saved device in table')
  assert.ok(savedId)
  const persisted = await (await fetch(`${api}/api/equipment/${savedId}`)).json()
  assert.equal(persisted.asset_tag, tag)
  assert.equal(persisted.serial_number, serialNumber)
  const age = (Date.parse(`${persisted.calculated_as_of}T00:00:00Z`) - Date.parse('2003-03-03T00:00:00Z')) / 86400000 / 365.25
  assert.equal(persisted.age_years, age.toFixed(2))
  assert.equal(persisted.avg_annual_cost, (9678.12 / age).toFixed(2))
  assert.equal(persisted.department_code, '001')
  assert.equal(persisted.location, 'Room 12')
  assert.equal(persisted.device_type, 'Ventilator')
  assert.equal(Number(persisted.replacement_cost), 20000)
  const exported = await fetch(`${api}/api/equipment/export`)
  assert.equal(exported.status, 200)
  assert.equal(exported.headers.get('x-calculated-as-of'), persisted.calculated_as_of)
  assert.ok((await exported.text()).includes(tag))
  button('Details & assessment', row()).click(); await wait()
  button('Assess equipment').click()
  await until(() => text().includes('Repair intensity:'), 'real AI result')
  assert.match(text(), /Prioritize|Review repair history|routine maintenance/)
  assert.match(text(), /synthetic ventilator data/)
  assert.match(text(), /Model-estimated annual cost/)
  assert.equal(assessedResult.equipment_id, savedId)
  assert.ok(assessedResult.risk_score >= 0 && assessedResult.risk_score <= 1)
  assert.equal(assessedResult.risk_score, assessedResult.prediction.risk_score)
  assert.equal(assessedResult.repair_rate_percentile, assessedResult.risk_score)
  const formattedPercentile = new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 }).format(assessedResult.repair_rate_percentile)
  assert.ok(text().includes(formattedPercentile))
  assert.ok(button('Reassess equipment'))
  assert.ok(assessedResult.prediction.training_repair_rate_min != null)
  assert.equal(Math.round(assessedResult.prediction.projected_cost_next_years * 100), Math.round(assessedResult.prediction.predicted_annual_cost * 100) * assessedResult.prediction.projection_years)
  assert.ok(text().includes(assessedResult.recommendation))
  assert.equal(assessedResult.prediction.model_input_category, 'Getinge SERVOi')
  assert.equal(assessedResult.prediction.assumed_replacement_cost, 20000)
  button('Edit', row()).click(); await wait()
  await setInput('total_historical_cost', '321.09')
  await setInput('model_name', 'Updated model')
  await setInput('status', 'Under Maintenance')
  await setInput('repair_events', '15')
  submit()
  await until(() => row()?.textContent.includes('Updated model'), 'persisted edit')
  const updated = await (await fetch(`${api}/api/equipment/${savedId}`)).json()
  assert.equal(updated.repair_events, 15)
  assert.equal(updated.status, 'Under Maintenance')
  assert.equal(Number(updated.total_historical_cost), 321.09)
  assert.equal(updated.avg_annual_cost, (321.09 / age).toFixed(2))
  assert.equal(updated.age_years, age.toFixed(2))
  assert.doesNotMatch(text(), /Repair intensity:/)
  // Use the generated RDS fixture as the source for a real scheduling preview.
  await setInputByLabel('Equipment for demo inputs', savedId)
  button('Load demo scheduling inputs').click(); await wait()
  w.document.getElementById('scheduling-form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }))
  await until(() => text().includes('Schedule preview generated:'), 'real schedule preview')
  assert.equal(scheduleResult.persisted, false)
  assert.equal(scheduleResult.assignments.length, 3)
  assert.equal(scheduleResult.unscheduled.length, 0)
  for (let i = 0; i < scheduleResult.assignments.length; i++) {
    const assignment = scheduleResult.assignments[i]
    assert.equal(assignment.equipment_id, savedId)
    assert.equal(assignment.asset_tag, tag)
    assert.equal((Date.parse(assignment.end) - Date.parse(assignment.start)) / 60000, assignment.duration_minutes)
    const technician = scheduleInput.technicians.find(item => item.id === assignment.technician_id)
    assert.ok(technician.qualifications.some(skill => skill.toLowerCase() === assignment.required_qualification.toLowerCase()))
    const format = value => new Intl.DateTimeFormat('en-GB', { timeZone: 'America/Toronto', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value))
    assert.ok(technician.availability.some(window => format(assignment.start) >= window.start && format(assignment.end) <= window.end))
    for (const other of scheduleResult.assignments.slice(i + 1)) {
      if (assignment.technician_id === other.technician_id || assignment.equipment_id === other.equipment_id) {
        assert.ok(Date.parse(assignment.end) <= Date.parse(other.start) || Date.parse(other.end) <= Date.parse(assignment.start))
      }
    }
    for (const booking of scheduleInput.existing_bookings) {
      if (booking.technician_id === assignment.technician_id || booking.equipment_id === assignment.equipment_id) {
        assert.ok(format(assignment.end) <= booking.start || format(assignment.start) >= booking.end)
      }
    }
  }
  // CRUD supports other types; both UI and API must prevent unsupported assessment.
  button('Edit', row()).click(); await wait()
  await setInput('device_type', 'Other')
  submit()
  await until(() => row()?.textContent.includes('Other'), 'unsupported type persisted')
  button('Details & assessment', row()).click(); await wait()
  assert.ok(button('Assess equipment').disabled)
  assert.equal((await fetch(`${api}/api/equipment/${savedId}/assessment`)).status, 422)
  button('Delete', row()).click(); await wait()
  button('Confirm delete', row()).click()
  await until(() => !row(), 'deleted row removed')
  assert.equal((await fetch(`${api}/api/equipment/${savedId}`)).status, 404)
  console.log('Live frontend flow passed: React → FastAPI → RDS persistence → existing AI prediction → scheduling constraints → edit → delete.')
} finally {
  try {
    const response = await fetch(`${api}/api/equipment`)
    if (response.ok) {
      for (const record of await response.json()) {
        if (record.asset_tag === tag && record.serial_number === serialNumber) {
          const deletion = await fetch(`${api}/api/equipment/${record.id}`, { method: 'DELETE' })
          assert.ok([204, 404].includes(deletion.status), 'Temporary UI record cleanup failed')
        }
      }
    }
  } finally { dom.window.close() }
}
