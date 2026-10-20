import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000'

// Each endpoint keeps its own loading, result, and error state.
function useApi(path, revision = 0) {
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
  }, [path, revision])

  return result
}

function App() {
  const health = useApi('/api/health')
  const [revision, setRevision] = useState(0)
  const equipment = useApi('/api/equipment', revision)
  const emptyForm = { name: '', type: '', location: '', status: 'Operational' }
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const submitting = useRef(false)
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState('')

  async function submitEquipment(event) {
    event.preventDefault()
    if (submitting.current) return
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()]))
    const requiredErrors = Object.fromEntries(Object.entries(payload)
      .filter(([, value]) => !value).map(([key]) => [key, 'This field is required.']))
    setErrors(requiredErrors)
    setMessage('')
    if (Object.keys(requiredErrors).length) return
    submitting.current = true
    setSaving(true)
    try {
      const response = await fetch(`${API_URL}/api/equipment`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const body = await response.json()
      if (!response.ok) {
        if (Array.isArray(body.detail)) {
          const fieldErrors = {}
          body.detail.forEach((item) => { fieldErrors[item.loc.at(-1)] = item.msg })
          setErrors(fieldErrors)
          throw new Error('Please correct the highlighted fields.')
        }
        throw new Error(typeof body.detail === 'string' ? body.detail : `Save failed (HTTP ${response.status}).`)
      }
      setForm(emptyForm)
      setMessage(`Equipment saved (ID ${body.id}).`)
      setRevision((value) => value + 1)
    } catch (error) {
      setErrors((current) => ({ ...current, submit: error instanceof TypeError
        ? 'Cannot reach the backend. Check your connection and that the backend is running. If the connection dropped after saving, check the table before retrying.'
        : error.message }))
    } finally {
      submitting.current = false
      setSaving(false)
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Senior Engineering Project · Week 4</p>
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

      <section aria-labelledby="add-heading" className="panel">
        <h2 id="add-heading">Add equipment</h2>
        <form onSubmit={submitEquipment} noValidate>
          <fieldset disabled={saving}>
            <legend className="sr-only">Equipment details</legend>
            {['name', 'type', 'location', 'status'].map((field) => (
              <div className="form-field" key={field}>
                <label htmlFor={field}>{field[0].toUpperCase() + field.slice(1)} (required)</label>
                {field === 'status' ? (
                  <select id={field} value={form[field]} required
                    aria-invalid={Boolean(errors[field])} aria-describedby={errors[field] ? `${field}-error` : undefined}
                    onChange={(event) => setForm({ ...form, [field]: event.target.value })}>
                    {['Operational', 'Under Maintenance', 'Inactive'].map((status) => <option key={status}>{status}</option>)}
                  </select>
                ) : (
                  <input id={field} value={form[field]} required maxLength={255}
                    aria-invalid={Boolean(errors[field])} aria-describedby={errors[field] ? `${field}-error` : undefined}
                    onChange={(event) => setForm({ ...form, [field]: event.target.value })} />
                )}
                {errors[field] && <p id={`${field}-error`} className="error">{errors[field]}</p>}
              </div>
            ))}
            <button type="submit">{saving ? 'Saving…' : 'Add equipment'}</button>
          </fieldset>
          {errors.submit && <p role="alert" className="error">{errors.submit}</p>}
          <p role="status" aria-live="polite">{message}</p>
        </form>
      </section>

      <section aria-labelledby="equipment-heading" className="panel">
        <h2 id="equipment-heading">Equipment</h2>
        <p className="subtitle">Equipment saved in the maintenance database.</p>
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
