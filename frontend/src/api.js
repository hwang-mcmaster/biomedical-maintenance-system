let csrfToken = ''
export function setCsrfToken(value) { csrfToken = value || '' }
export const API_URL = import.meta.env.VITE_API_URL || ''

export async function request(path, options = {}) {
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
    if (response.status === 401) window.dispatchEvent(new Event('session-expired'))
    const error = new Error(typeof body.detail === 'string' ? body.detail : 'Please correct the highlighted fields.')
    error.validationMessages = Array.isArray(body.detail)
      ? body.detail.map((item) => `${item.loc.filter((part) => part !== 'body').join(' > ')}: ${item.msg}`) : []
    error.fields = Array.isArray(body.detail)
      ? Object.fromEntries(body.detail.map((item) => [item.loc.at(-1), item.msg])) : {}
    throw error
  }
  return body
}
