import {readFileSync} from 'node:fs'
import assert from 'node:assert/strict'
const source=readFileSync('src/uiPreview.js','utf8')
async function load(dev,search){globalThis.window={location:{search}};return import('data:text/javascript;base64,'+Buffer.from(source.replace('import.meta.env.DEV',String(dev))+`\n// ${Math.random()}`).toString('base64'))}
const sample=await load(true,'?preview=1');assert.equal(sample.UI_PREVIEW,true)
assert.equal((await sample.previewRequest('/api/auth/me')).user.name,'UI Preview')
assert.equal((await sample.previewRequest('/api/equipment')).length,3)
for(const method of ['POST','PUT','PATCH','DELETE'])await assert.rejects(()=>sample.previewRequest('/api/equipment',{method}),/read-only/)
assert.equal((await load(false,'?preview=1')).UI_PREVIEW,false)
assert.equal((await load(true,'')).UI_PREVIEW,false)
console.log('UI preview checks passed: explicit dev-only activation, sample reads and blocked mutations.')
