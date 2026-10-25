import { useRef, useState } from 'react'
import { request } from '../api'

const fields = [
  ['name', 'Name / model', 'text', 100], ['type', 'Equipment type', 'text', 100],
  ['location', 'Location / department', 'text', 100], ['status', 'Status', 'select'],
  ['asset_tag', 'Asset tag', 'text', 50], ['serial_number', 'Serial number', 'text', 100],
  ['manufacturer', 'Manufacturer / model family', 'text', 100],
  ['firmware_version', 'Firmware version', 'text', 50],
  ['in_service_date', 'In-service date', 'date'],
  ['repair_events', 'Lifetime repair events', 'number'],
  ['total_historical_cost', 'Total historical maintenance cost ($)', 'number'],
  ['assumed_replacement_cost', 'Assumed replacement cost ($, optional)', 'number'],
]
const emptyForm = {
  name: '', type: '', location: '', status: 'Operational', asset_tag: '',
  serial_number: '', manufacturer: '', firmware_version: '', in_service_date: '',
  repair_events: '0', total_historical_cost: '0', assumed_replacement_cost: '',
}

export default function EquipmentForm({ device, onSaved, onCancel }) {
  const [form, setForm] = useState(() => device
    ? Object.fromEntries(Object.keys(emptyForm).map((key) => [key, String(device[key] ?? '')])) : emptyForm)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const submitting = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()]))
    const found = {}
    fields.forEach(([key, , kind, max]) => {
      const value = payload[key]
      if (!value && key !== 'assumed_replacement_cost') found[key] = 'This field is required.'
      else if (max && value.length > max) found[key] = `Use ${max} characters or fewer.`
      else if (kind === 'number' && value) {
        const number = Number(value)
        if (!Number.isFinite(number) || number < 0) found[key] = 'Enter a non-negative number.'
        else if (key === 'repair_events' && (!Number.isInteger(number) || number > 2147483647)) found[key] = 'Enter a whole number from 0 to 2147483647.'
        else if (key === 'assumed_replacement_cost' && number <= 0) found[key] = 'Enter an amount greater than zero, or leave blank.'
        payload[key] = number
      }
    })
    const today = new Date()
    const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    if (payload.in_service_date > localDate) found.in_service_date = 'In-service date cannot be in the future.'
    payload.assumed_replacement_cost = payload.assumed_replacement_cost === '' ? null : payload.assumed_replacement_cost
    setErrors(found)
    if (Object.keys(found).length) return
    submitting.current = true
    setSaving(true)
    try {
      const saved = await request(device ? `/api/equipment/${device.id}` : '/api/equipment', {
        method: device ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      if (!device) setForm(emptyForm)
      onSaved(saved, Boolean(device))
    } catch (error) {
      setErrors({ ...error.fields, submit: error.message })
    } finally {
      submitting.current = false
      setSaving(false)
    }
  }

  return (
    <section className="panel" aria-labelledby="form-heading">
      <h2 id="form-heading">{device ? `Edit equipment: ${device.asset_tag}` : 'Add equipment'}</h2>
      <p className="subtitle">Asset tags and serial numbers must be unique. The database generates the ID.</p>
      <form onSubmit={submit} noValidate>
        <fieldset disabled={saving}>
          <legend className="sr-only">Equipment details</legend>
          <div className="form-grid">
            {fields.map(([key, label, kind, max]) => (
              <div className="form-field" key={key}>
                <label htmlFor={key}>{label}{key !== 'assumed_replacement_cost' && ' (required)'}</label>
                {kind === 'select' ? (
                  <select id={key} value={form[key]} required
                    aria-invalid={Boolean(errors[key])} aria-describedby={errors[key] ? `${key}-error` : undefined}
                    onChange={(event) => setForm({ ...form, [key]: event.target.value })}>
                    {['Operational', 'Under Maintenance', 'Inactive'].map((status) => <option key={status}>{status}</option>)}
                  </select>
                ) : (
                  <input id={key} type={kind} value={form[key]} maxLength={max}
                    required={key !== 'assumed_replacement_cost'} min={kind === 'number' ? 0 : undefined}
                    step={kind === 'number' ? (key === 'repair_events' ? 1 : '0.01') : undefined}
                    aria-invalid={Boolean(errors[key])} aria-describedby={errors[key] ? `${key}-error` : undefined}
                    onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
                )}
                {errors[key] && <p className="error" id={`${key}-error`}>{errors[key]}</p>}
              </div>
            ))}
          </div>
          <div className="actions">
            <button type="submit">{saving ? 'Saving…' : device ? 'Save changes' : 'Add equipment'}</button>
            {device && <button type="button" className="secondary" onClick={onCancel}>Cancel editing</button>}
          </div>
        </fieldset>
        {errors.submit && <p className="error" role="alert">{errors.submit}</p>}
      </form>
    </section>
  )
}
