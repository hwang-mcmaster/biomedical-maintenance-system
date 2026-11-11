import { useRef, useState } from 'react'
import { request } from '../api'

export function nextTorontoDay() {
  const today = new Intl.DateTimeFormat('en-CA', {timeZone:'America/Toronto',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
  return new Date(Date.parse(`${today}T00:00:00Z`) + 86400000).toISOString().slice(0,10)
}
export const torontoTime = value => new Date(value).toLocaleString('en-CA', {timeZone:'America/Toronto'})
export function useMutation() {
  const pending=useRef(false)
  const [busy,setBusy]=useState(false), [error,setError]=useState(''), [message,setMessage]=useState('')
  async function run(path,body,done,method='POST') {
    if(pending.current) return
    pending.current=true;setBusy(true);setError('');setMessage('')
    try {const result=await request(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      done?.(result);setMessage('Saved successfully.')
    } catch(e) {setError(e.validationMessages?.length ? e.validationMessages.join('; ') : e.message)}
    finally {pending.current=false;setBusy(false)}
  }
  return {busy,error,message,run}
}
