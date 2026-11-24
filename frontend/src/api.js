import {UI_PREVIEW,previewRequest} from './uiPreview'
let csrfToken = ''
export function setCsrfToken(value) { csrfToken = value || '' }
export const API_URL = import.meta.env.VITE_API_URL || ''

export async function request(path, options = {}) {
  if (UI_PREVIEW) return previewRequest(path, options)
  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      credentials: 'include',
      headers: {...options.headers, ...(csrfToken ? {'X-CSRF-Token': csrfToken} : {})},
      signal: options.signal
        ? AbortSignal.any([options.signal, AbortSignal.timeout(20000)])
        : AbortSignal.timeout(20000),
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new Error('Cannot reach the service or the request timed out. Check the backend connection. After a save, refresh the table before retrying.')
  }
  if (response.status === 204) return null
  let body
  try { body = await response.json() } catch {
    throw new Error(`The server returned an unreadable response (HTTP ${response.status}).`)
  }
  if (!response.ok) {
    const detail = body?.detail
    const fallback = {401:'Your session expired. Sign in again.',403:'You do not have permission for this action. Reload if your account has changed.',409:'The record changed or conflicts with existing work. Refresh before retrying.',422:'Please correct the form inputs.',429:'Too many requests. Please wait and retry.',503:'The service is temporarily unavailable. Please retry shortly.'}
    const message = typeof detail === 'string' ? detail : fallback[response.status] || `The request failed (HTTP ${response.status}). Please retry or contact the administrator.`
    if (response.status === 401 && !['/api/auth/login','/api/auth/activate','/api/auth/me'].includes(path)) {
      csrfToken = ''
      window.dispatchEvent(new CustomEvent('session-expired', {detail: message}))
    }
    const error = new Error(message)
    error.status = response.status
    error.validationMessages = Array.isArray(detail)
      ? detail.map((item) => `${(item.loc || []).filter((part) => part !== 'body').join(' > ')}: ${item.msg}`) : []
    error.fields = Array.isArray(detail)
      ? Object.fromEntries(detail.map((item) => [(item.loc || []).at(-1), item.msg])) : {}
    throw error
  }
  return body
}
