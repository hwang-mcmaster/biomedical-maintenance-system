import { useEffect, useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000'

// Each endpoint keeps its own loading, result, and error state.
function useApi(path) {
  const [result, setResult] = useState({ data: null, loading: true, error: '' })

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch(`${API_URL}${path}`, { signal: controller.signal })
        if (!response.ok) throw new Error(`Request failed (HTTP ${response.status}).`)
        const data = await response.json()
        setResult({ data, loading: false, error: '' })
      } catch (error) {
        if (controller.signal.aborted) return
        setResult({
          data: null,
          loading: false,
          error: `${error.message} Check that the backend is running at ${API_URL}, then reload this page.`,
        })
      }
    }

    load()
    return () => controller.abort()
  }, [path])

  return result
}

function App() {
  const health = useApi('/api/health')
  const equipment = useApi('/api/equipment')

  return (
    <main>
      <header>
        <p className="eyebrow">Senior Engineering Project · Phase 1</p>
        <h1>Biomedical Maintenance System</h1>
        <p className="subtitle">A simple equipment overview connected to the maintenance API.</p>
      </header>

      <section aria-labelledby="backend-heading" className="panel">
        <h2 id="backend-heading">Backend status</h2>
        <div role="status" aria-live="polite">
          {health.loading && <p>Checking the backend connection…</p>}
          {health.error && <p className="error">Backend unavailable. {health.error}</p>}
          {health.data && (
            <p><span className="badge">{health.data.status}</span> {health.data.message}</p>
          )}
        </div>
      </section>

      <section aria-labelledby="equipment-heading" className="panel">
        <h2 id="equipment-heading">Equipment</h2>
        <p className="subtitle">Sample biomedical devices returned by the backend.</p>
        <div role="status" aria-live="polite">
          {equipment.loading && <p>Loading equipment…</p>}
          {equipment.error && <p className="error">Unable to load equipment. {equipment.error}</p>}
          {equipment.data?.length === 0 && <p>No equipment found.</p>}
        </div>
        {equipment.data?.length > 0 && (
          <div className="table-wrapper">
            <table>
              <caption className="sr-only">Biomedical equipment inventory</caption>
              <thead>
                <tr>{['ID', 'Name', 'Type', 'Location', 'Status'].map((heading) => (
                  <th key={heading} scope="col">{heading}</th>
                ))}</tr>
              </thead>
              <tbody>
                {equipment.data.map((device) => (
                  <tr key={device.id}>
                    <td>{device.id}</td><td>{device.name}</td><td>{device.type}</td>
                    <td>{device.location}</td><td>{device.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
