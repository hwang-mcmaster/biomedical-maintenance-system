import { useEffect, useState } from 'react'
import { request } from './api'

export function useApi(path, revision = 0) {
  const [result, setResult] = useState({ data: null, error: '', path: null, revision: null })
  useEffect(() => {
    const controller = new AbortController()
    request(path, { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) setResult({ data, error: '', path, revision })
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setResult((previous) => ({ ...previous, error: error.message, path, revision }))
      }
    })
    return () => controller.abort()
  }, [path, revision])
  const loading = result.path !== path || result.revision !== revision
  return { ...result, loading, error: loading ? '' : result.error }
}
