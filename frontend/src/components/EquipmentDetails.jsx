import { useRef, useState } from 'react'
import { request } from '../api'
import { equipmentFields, displayValue } from '../equipmentFields'

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
    try { setAssessment(await request(`/api/equipment/${device.id}/assessment`, { method: 'GET', cache: 'no-store' })) }
    catch (failure) { setError(failure.message) }
    finally { pending.current = false; setLoading(false) }
  }
  const prediction = assessment?.prediction
  return (
    <section className="panel" aria-labelledby="details-heading">
      <div className="section-heading"><h2 id="details-heading">Equipment details: {device.asset_tag}</h2>
        <button type="button" className="secondary" onClick={onClose}>Close details</button></div>
      <dl className="details-grid">
        {equipmentFields.map(({ key, label }) => <div key={key}><dt>{label}</dt><dd>{displayValue(key, device[key])}</dd></div>)}
      </dl>
      <h3>AI-assisted maintenance review</h3>
      <p className="subtitle">Prototype trained on synthetic ventilator data. Repair intensity is not failure probability or a clinical safety assessment.</p>
      <p className="subtitle">This dataset does not specify device type. Confirm that the item belongs to the ventilator fleet before interpreting the model output.</p>
      <button type="button" disabled={loading} onClick={assess}>{loading ? 'Assessing…' : 'Assess equipment'}</button>
      {error && <p role="alert" className="error">{error}</p>}
      {assessment && <div className="assessment" role="status" aria-live="polite">
        <p><strong>Repair intensity: {assessment.risk_level}</strong></p>
        <p>{assessment.recommendation}</p>
        <dl className="details-grid">
          <div><dt>Risk score (relative repair intensity, 0 to 1)</dt><dd>{assessment.risk_score.toFixed(3)}</dd></div>
          <div><dt>Score meaning</dt><dd>Share of the training fleet with an equal or lower repair rate; not the chance of failure.</dd></div>
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
