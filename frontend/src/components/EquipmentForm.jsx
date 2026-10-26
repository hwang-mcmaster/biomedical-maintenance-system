import { useRef, useState } from 'react'
import { request } from '../api'
import { equipmentFields } from '../equipmentFields'

const emptyForm = Object.fromEntries(equipmentFields.map(({ key }) => [key, '']))

export default function EquipmentForm({ device, onSaved, onCancel }) {
  const [form, setForm] = useState(() => device
    ? Object.fromEntries(equipmentFields.map(({ key }) => [key, String(device[key])])) : emptyForm)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const submitting = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()]))
    const found = {}
    equipmentFields.forEach(({ key, type, maxLength, decimals }) => {
      const value = payload[key]
      if (!value) found[key] = 'This field is required.'
      else if (maxLength && value.length > maxLength) found[key] = `Use ${maxLength} characters or fewer.`
      else if (type === 'number') {
        const number = Number(value)
        if (!Number.isFinite(number) || number < 0) found[key] = 'Enter a non-negative number.'
        else if (key === 'repair_events') {
          if (!Number.isInteger(number) || number > 2147483647) found[key] = 'Enter a whole number from 0 to 2147483647.'
          payload[key] = number
        } else {
          const pattern = new RegExp(`^\\d+(?:\\.\\d{1,${decimals}})?$`)
          const limit = key === 'age_years' ? 100000 : 10000000000
          if (!pattern.test(value) || number >= limit) found[key] = `Enter a value below ${limit} with up to ${decimals} decimal places.`
          // Keep decimal text intact; the backend stores exact NUMERIC values.
        }
      }
    })
    const today = new Date()
    const localDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
    if (payload.in_service_date > localDate) found.in_service_date = 'In-service date cannot be in the future.'
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
      <p className="subtitle">All eight dataset fields are required. Asset tags and serial numbers must be unique.</p>
      <p className="subtitle">Enter the supplied age and historical annual average. These values are preserved, not recalculated from today.</p>
      <form onSubmit={submit} noValidate>
        <fieldset disabled={saving}>
          <legend className="sr-only">Equipment dataset</legend>
          <div className="form-grid">
            {equipmentFields.map(({ key, label, type, maxLength, decimals }) => (
              <div className="form-field" key={key}>
                <label htmlFor={key}>{label} (required)</label>
                <input id={key} type={type} value={form[key]} maxLength={maxLength} required
                  min={type === 'number' ? 0 : undefined}
                  step={type === 'number' ? 10 ** -decimals : undefined}
                  aria-invalid={Boolean(errors[key])} aria-describedby={errors[key] ? `${key}-error` : undefined}
                  onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
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
