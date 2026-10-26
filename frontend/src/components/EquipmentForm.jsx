import { useRef, useState } from 'react'
import { request } from '../api'
import { equipmentFields, sourceFields, displayValue, torontoToday, previewMetrics } from '../equipmentFields'

const emptyForm = Object.fromEntries(sourceFields.map(({ key, defaultValue }) => [key, defaultValue ?? '']))

export default function EquipmentForm({ device, onSaved, onCancel }) {
  const [form, setForm] = useState(() => device
    ? Object.fromEntries(sourceFields.map(({ key }) => [key, String(device[key])])) : emptyForm)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const submitting = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()]))
    const found = {}
    sourceFields.forEach(({ key, type, maxLength, decimals, defaultValue }) => {
      if (!payload[key] && defaultValue !== undefined) payload[key] = defaultValue
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
          const limit = 10000000000
          if (!pattern.test(value) || number >= limit) found[key] = `Enter a value below ${limit} with up to ${decimals} decimal places.`
          // Keep decimal text intact; the backend stores exact NUMERIC values.
        }
      }
    })
    if (payload.in_service_date >= torontoToday()) found.in_service_date = 'In-service date must be before today.'
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

  const asOf = torontoToday()
  const preview = previewMetrics(form.in_service_date, form.total_historical_cost, asOf)

  return (
    <section className="panel" aria-labelledby="form-heading">
      <h2 id="form-heading">{device ? `Edit equipment: ${device.asset_tag}` : 'Add equipment'}</h2>
      <p className="subtitle">Enter the six source fields. Asset tags and serial numbers must be unique.</p>
      <p className="subtitle">Age and average annual cost are calculated. Previews use today in Toronto; saved results come from the backend.</p>
      <form onSubmit={submit} noValidate>
        <fieldset disabled={saving}>
          <legend className="sr-only">Equipment dataset</legend>
          <div className="form-grid">
            {equipmentFields.map(({ key, label, type, maxLength, decimals, calculated, defaultValue }) => (
              <div className="form-field" key={key}>
                <label htmlFor={key}>{label} {calculated ? '(calculated preview)' : defaultValue !== undefined ? '(defaults to 0)' : '(required)'}</label>
                {calculated ? <output id={key} aria-live="polite">{displayValue(key, preview[key])}</output> : (
                <input id={key} type={type} value={form[key]} maxLength={maxLength} required={defaultValue === undefined}
                  min={type === 'number' ? 0 : undefined}
                  step={type === 'number' ? 10 ** -decimals : undefined}
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
