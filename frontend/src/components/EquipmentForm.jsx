import { useRef, useState } from 'react'
import { request } from '../api'
import { equipmentFields, sourceFields, fieldGroups, displayValue, torontoToday, previewMetrics } from '../equipmentFields'

const emptyForm = Object.fromEntries(sourceFields.map(({ key, defaultValue }) => [key, defaultValue ?? '']))

export default function EquipmentForm({ device, onSaved, onCancel, options, onRetryOptions }) {
  const [form, setForm] = useState(() => device
    ? Object.fromEntries(sourceFields.map(({ key }) => [key, String(device[key] ?? '')])) : emptyForm)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const submitting = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (submitting.current || options.loading || options.error) return
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value.trim()]))
    const found = {}
    sourceFields.forEach(({ key, type, maxLength, decimals, defaultValue, optional, optionsKey }) => {
      if (!payload[key] && defaultValue !== undefined) payload[key] = defaultValue
      const value = payload[key]
      if (!value && optional) { payload[key] = null; return }
      if (!value) found[key] = 'This field is required.'
      else if (maxLength && value.length > maxLength) found[key] = `Use ${maxLength} characters or fewer.`
      else if (type === 'select' && !(options.data?.[optionsKey] || []).includes(value)) found[key] = 'Choose an available value.'
      else if (type === 'number') {
        const number = Number(value)
        if (!Number.isFinite(number) || number < 0) found[key] = 'Enter a non-negative number.'
        else if (decimals === 0) {
          const minimum = key === 'expected_useful_life' ? 1 : 0
          if (!Number.isInteger(number) || number < minimum || number > 2147483647) found[key] = `Enter a whole number from ${minimum} to 2147483647.`
          payload[key] = number
        } else {
          const pattern = new RegExp(`^\\d+(?:\\.\\d{1,${decimals}})?$`)
          if (!pattern.test(value) || number >= 10000000000) found[key] = 'Enter an amount below 10000000000 with up to 2 decimal places.'
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
    } catch (error) { setErrors({ ...error.fields, submit: error.message }) }
    finally { submitting.current = false; setSaving(false) }
  }

  const preview = previewMetrics(form.in_service_date, form.total_historical_cost, torontoToday())
  const life = Number(form.expected_useful_life)
  preview.reference_remaining_life_years = form.expected_useful_life && Number.isInteger(life) && life > 0 && preview.age_years != null
    ? Math.max(0, life - preview.age_years) : null
  function fieldControl(field) {
    const { key, type, maxLength, decimals, calculated, defaultValue, optional, optionsKey } = field
    if (calculated) return <output id={key} aria-live="polite">{displayValue(key, preview[key])}</output>
    const shared = { id: key, value: form[key], required: !optional && defaultValue === undefined,
      'aria-invalid': Boolean(errors[key]), 'aria-describedby': errors[key] ? `${key}-error` : undefined,
      onChange: (event) => setForm({ ...form, [key]: event.target.value }) }
    if (type === 'select') return <select {...shared}><option value="">Not recorded</option>
      {(options.data?.[optionsKey] || []).map((value) => <option key={value}>{value}</option>)}</select>
    if (type === 'textarea') return <textarea {...shared} maxLength={maxLength} rows={3} />
    return <input {...shared} type={type} maxLength={maxLength} min={type === 'number' ? (key === 'expected_useful_life' ? 1 : 0) : undefined}
      step={type === 'number' ? 10 ** -decimals : undefined} />
  }
  return (
    <section className="panel" aria-labelledby="form-heading">
      <h2 id="form-heading">{device ? `Edit equipment: ${device.asset_tag}` : 'Add equipment'}</h2>
      <p className="subtitle">Required identity and lifecycle inputs are marked. New operational fields are optional; leave unknown values blank.</p>
      <p className="subtitle">Age and historical annual cost are calculated. Useful life is a reference in years, not an AI prediction. Department and physical location are separate.</p>
      {options.loading && <p role="status">Loading equipment choices…</p>}
      {options.error && <p role="alert" className="error">{options.error} <button type="button" onClick={onRetryOptions}>Retry equipment choices</button></p>}
      <form onSubmit={submit} noValidate>
        <fieldset disabled={saving || options.loading || Boolean(options.error)}>
          <legend className="sr-only">Equipment record</legend>
          {fieldGroups.map((group) => <div className="form-group" key={group}><h3>{group}</h3><div className="form-grid">
            {equipmentFields.filter((field) => field.group === group).map((field) => <div className="form-field" key={field.key}>
              <label htmlFor={field.key}>{field.label} {field.calculated ? '(calculated preview)' : field.optional ? '(optional)' : field.defaultValue !== undefined ? '(defaults to 0)' : '(required)'}</label>
              {fieldControl(field)}
              {errors[field.key] && <p className="error" id={`${field.key}-error`}>{errors[field.key]}</p>}
            </div>)}
          </div></div>)}
          <div className="actions"><button type="submit">{saving ? 'Saving…' : device ? 'Save changes' : 'Add equipment'}</button>
            {device && <button type="button" className="secondary" onClick={onCancel}>Cancel editing</button>}</div>
        </fieldset>
        {errors.submit && <p className="error" role="alert">{errors.submit}</p>}
      </form>
    </section>
  )
}
