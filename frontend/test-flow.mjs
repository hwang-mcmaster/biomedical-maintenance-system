import { JSDOM } from 'jsdom'
import { readFileSync, readdirSync } from 'node:fs'
import assert from 'node:assert/strict'
const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5173', runScripts: 'outside-only' })
const w = dom.window
let records = [], posts = 0, releaseSave
w.fetch = async (url, options = {}) => {
  if (options.method === 'POST') {
    posts++
    const payload = JSON.parse(options.body)
    await new Promise(resolve => { releaseSave = resolve })
    const record = { ...payload, id: 7 }; records.push(record)
    return { ok: true, json: async () => record }
  }
  return { ok: true, json: async () => url.endsWith('/health') ? { status: 'ok', message: 'Ready' } : [...records] }
}
const bundle = readdirSync('dist/assets').find(name => name.endsWith('.js'))
w.eval(readFileSync(`dist/assets/${bundle}`, 'utf8'))
const wait = () => new Promise(resolve => setTimeout(resolve, 80))
await wait()
let form = w.document.querySelector('form')
const submit = () => form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }))
submit(); await wait()
assert.equal(posts, 0)
assert.match(w.document.body.textContent, /This field is required/)
for (const [id, value] of Object.entries({ name: 'Pump', type: 'Infusion', location: 'ICU' })) {
  const input = w.document.getElementById(id)
  Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype, 'value').set.call(input, value)
  input.dispatchEvent(new w.Event('input', { bubbles: true }))
  await wait()
}
submit(); await wait()
assert.equal(posts, 1)
assert.equal(w.document.querySelector('fieldset').disabled, true)
submit(); await wait(); assert.equal(posts, 1)
releaseSave(); await wait(); await wait()
assert.match(w.document.body.textContent, /Equipment saved \(ID 7\)/)
assert.equal(w.document.getElementById('name').value, '')
assert.match(w.document.querySelector('tbody').textContent, /Pump/)
assert.equal(w.document.querySelector('fieldset').disabled, false)
w.fetch = async () => { throw new w.TypeError('Failed to fetch') }
for (const id of ['name','type','location']) {
  const input = w.document.getElementById(id)
  Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype, 'value').set.call(input, 'test')
  input.dispatchEvent(new w.Event('input', { bubbles: true })); await wait()
}
submit(); await wait()
assert.match(w.document.body.textContent, /Cannot reach the backend/)
console.log('Frontend DOM flow passed: required validation, POST, duplicate prevention, saving state, reset, table refresh, network error.')
dom.window.close()

