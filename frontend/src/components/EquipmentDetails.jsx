import { useRef, useState } from 'react'
import { request } from '../api'

const amount = (value) => Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export default function EquipmentDetails({ device, onClose }) {
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  async function assess() {
    if (pending.current) return
    pending.current = true
    setLoading(true)
    setError('')
    setAssessment(null)
    try { setAssessment(await request(`/api/equipment/${device.id}/assessment`, { method: 'POST' })) }
    catch (failure) { setError(failure.message) }
    finally { pending.current = false; setLoading(false) }
  }
  const prediction = assessment?.prediction
  const supported = device.type.toLowerCase().includes('ventilator')
  return (
    <section className="panel" aria-labelledby="details-heading">
      <div className="section-heading"><h2 id="details-heading">Equipment details: {device.asset_tag}</h2>
        <button type="button" className="secondary" onClick={onClose}>Close details</button></div>
      <dl className="details-grid">
        {Object.entries({ ID: device.id, 'Name / model': device.name, Manufacturer: device.manufacturer,
          'Serial number': device.serial_number, Firmware: device.firmware_version,
          'In service': device.in_service_date, 'Repair events': device.repair_events,
          'Historical cost ($)': amount(device.total_historical_cost),
          'Replacement cost ($)': device.assumed_replacement_cost == null ? 'Not provided' : amount(device.assumed_replacement_cost),
        }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>
      <h3>AI-assisted maintenance review</h3>
      <p className="subtitle">Prototype trained on synthetic ventilator data. Repair intensity is not failure probability or a clinical safety assessment.</p>
      {!supported && <p>This model supports ventilators only. Assessment is unavailable for this equipment type.</p>}
      <button type="button" disabled={loading || !supported} onClick={assess}>{loading ? 'Assessing…' : 'Assess equipment'}</button>
      {error && <p role="alert" className="error">{error}</p>}
      {assessment && <div className="assessment" role="status" aria-live="polite">
        <p><strong>Repair intensity: {prediction.risk_level}</strong></p>
        <p>{assessment.recommendation}</p>
        <dl className="details-grid">
          <div><dt>Predicted annual maintenance cost</dt><dd>${amount(prediction.predicted_annual_cost)}</dd></div>
          <div><dt>Typical validation error (MAE)</dt><dd>${amount(prediction.cost_error_range)} / year (not a confidence interval)</dd></div>
          <div><dt>Repair events / year</dt><dd>{prediction.repair_rate_per_year}</dd></div>
          <div><dt>Projected cost over {prediction.projection_years} years</dt><dd>${amount(prediction.projected_cost_next_years)}</dd></div>
        </dl>
        {prediction.warnings.map((warning, index) => <p key={index} className="error">{warning}</p>)}
        <p className="subtitle">{assessment.limitation}</p>
        <p className="subtitle">Assessed {new Date(assessment.assessed_at).toLocaleString()}. Results are calculated on demand and are not stored.</p>
      </div>}
    </section>
  )
}
