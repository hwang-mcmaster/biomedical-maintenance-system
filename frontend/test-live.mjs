// Opt-in end-to-end test: real React, FastAPI, RDS and the existing AI service.
import { JSDOM } from 'jsdom'
import { readFileSync, readdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import assert from 'node:assert/strict'

const api = process.env.TEST_API_URL || 'http://localhost:8000'
const tag = `CODEX-UI-${randomUUID().replaceAll('-', '')}`
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173', runScripts: 'outside-only' })
const w = dom.window
let savedId
w.fetch = async (url, options = {}) => {
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  options.signal?.addEventListener('abort', abort, { once: true })
  try {
    const path = new URL(url).pathname
    const response = await fetch(`${api}${path}`, { ...options, signal: controller.signal })
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
  Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new w.Event('input', { bubbles: true }))
  await wait()
}
const submit = () => w.document.querySelector('form').dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }))
try {
  const ready = await fetch(`${api}/api/ready`)
  assert.equal(ready.status, 200, await ready.text())
  const bundle = readdirSync('dist/assets').find(name => name.endsWith('.js'))
  w.eval(readFileSync(`dist/assets/${bundle}`, 'utf8'))
  await until(() => button('Add equipment') && !text().includes('Checking equipment database'), 'initial load')
  for (const [key, value] of Object.entries({ name: 'Live integration test ventilator', type: 'Ventilator',
    location: 'Test lab', asset_tag: tag, serial_number: tag, manufacturer: 'Getinge SERVOi',
    firmware_version: '1.0', in_service_date: '2020-01-01', repair_events: '10',
    total_historical_cost: '1000', assumed_replacement_cost: '20000',
  })) await setInput(key, value)
  submit()
  await until(() => row(), 'saved device in table')
  assert.ok(savedId)
  const persisted = await (await fetch(`${api}/api/equipment/${savedId}`)).json()
  assert.equal(persisted.asset_tag, tag)
  button('Details & assessment', row()).click(); await wait()
  button('Assess equipment').click()
  await until(() => text().includes('Repair intensity:'), 'real AI result')
  assert.match(text(), /Prioritize|Review repair history|routine maintenance/)
  assert.match(text(), /synthetic ventilator data/)
  assert.match(text(), /Predicted annual maintenance cost/)
  button('Edit', row()).click(); await wait()
  await setInput('location', 'Updated integration lab')
  await setInput('repair_events', '15')
  submit()
  await until(() => row()?.textContent.includes('Updated integration lab'), 'persisted edit')
  const updated = await (await fetch(`${api}/api/equipment/${savedId}`)).json()
  assert.equal(updated.repair_events, 15)
  assert.doesNotMatch(text(), /Repair intensity:/)
  button('Delete', row()).click(); await wait()
  button('Confirm delete', row()).click()
  await until(() => !row(), 'deleted row removed')
  assert.equal((await fetch(`${api}/api/equipment/${savedId}`)).status, 404)
  console.log('Live frontend flow passed: React → FastAPI → RDS persistence → existing AI prediction → edit → delete.')
} finally {
  try {
    const response = await fetch(`${api}/api/equipment`)
    if (response.ok) {
      for (const record of await response.json()) {
        if (record.asset_tag === tag && record.serial_number === tag) {
          const deletion = await fetch(`${api}/api/equipment/${record.id}`, { method: 'DELETE' })
          assert.ok([204, 404].includes(deletion.status), 'Temporary UI record cleanup failed')
        }
      }
    }
  } finally { dom.window.close() }
}
