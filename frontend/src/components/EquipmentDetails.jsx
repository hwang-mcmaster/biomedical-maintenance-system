import { useRef, useState } from 'react'
import EquipmentWorkflow from './EquipmentWorkflow'
import { request } from '../api'
import { equipmentFields, fieldGroups, displayValue } from '../equipmentFields'

const amount = (value) => value == null ? 'N/A' : Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const percentile = (value) => new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 }).format(value)
const scopeNote = 'Prototype trained on synthetic ventilator data. Repair intensity is not failure probability or clinical safety. Expected useful life is a reference, not a model prediction. Recommendations require engineering review.'

export default function EquipmentDetails({ device, onClose, readOnly = false, workflowRevision = 0, onWorkflowChanged = () => {} }) {
  const [tab,setTab]=useState('overview')
  const [assessment, setAssessment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [attempted, setAttempted] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  async function assess() {
    if (pending.current) return
    pending.current = true
    setAttempted(true)
    setLoading(true)
    setError('')
    setAssessment(null)
    try { setAssessment(await request(`/api/equipment/${device.id}/assessment`, { method: 'GET', cache: 'no-store' })) }
    catch (failure) { setError(failure.message) }
    finally { pending.current = false; setLoading(false) }
  }
  const prediction = assessment?.prediction
  const notices = [...new Set(prediction?.warnings || [])]
  return (
    <section className="panel" aria-labelledby="details-heading">
      <div className="section-heading"><h2 id="details-heading">Equipment details: {device.asset_tag}</h2>
        <button type="button" className="secondary" onClick={onClose}>Close details</button></div>
      <nav className="record-tabs" aria-label="Equipment sections">{['overview','assessment','maintenance'].map(t=><button className={tab===t?'':'secondary'} key={t} onClick={()=>setTab(t)}>{t}</button>)}</nav>
      <div hidden={tab!=='overview'}>
      {fieldGroups.map((group) => <div key={group}><h3>{group}</h3><dl className="details-grid">
        {equipmentFields.filter((field) => field.group === group).map(({ key, label }) => <div key={key}><dt>{label}</dt><dd>{displayValue(key, device[key])}</dd></div>)}
      </dl></div>)}
      <p className="subtitle">Age and historical annual average calculated as of {device.calculated_as_of}. Amounts are in CAD.</p>
      </div><div hidden={tab!=='assessment'}>
      <h3>AI-assisted maintenance review</h3>
      <aside className="notice" aria-label="Model scope"><p>{assessment?.limitation || scopeNote}</p></aside>
      <p role="status" aria-live="polite">{loading ? 'Assessing equipment…' : assessment ? 'Assessment complete.' : error ? 'Assessment failed. Please retry.' : 'Not assessed yet.'}</p>
      {device.device_type !== 'Ventilator' && <p className="notice">{device.device_type
        ? 'The current assessment model supports Ventilator equipment only. This device type needs a suitable model.'
        : 'Edit this equipment and record its device type before assessment.'}</p>}
      <button type="button" disabled={readOnly || loading || device.device_type !== 'Ventilator'} onClick={assess}>
        {loading ? 'Assessing…' : assessment ? 'Reassess equipment' : attempted ? 'Retry assessment' : 'Assess equipment'}
      </button>
      {error && <p role="alert" className="error">{error}</p>}
      {assessment && <div className="assessment">
        <p><strong>Repair intensity: {assessment.risk_level}</strong></p>
        <p>{assessment.recommendation}</p>
        {notices.length > 0 && <aside className="notice" aria-label="Assessment notes"><strong>Assessment notes</strong>
          <ul>{notices.map((notice) => <li key={notice}>{notice}</li>)}</ul>
        </aside>}
        <dl className="details-grid">
          <div><dt>Model input category</dt><dd>{prediction.model_input_category || 'Not available'}</dd></div>
          <div><dt>Historical maintenance / replacement cost</dt><dd>{prediction.maintenance_to_replacement_ratio == null ? 'N/A (positive replacement cost required)' : percentile(prediction.maintenance_to_replacement_ratio)}</dd></div>
          <div><dt>Repair-rate percentile</dt><dd>{percentile(assessment.repair_rate_percentile)}</dd></div>
          <div><dt>Percentile meaning</dt><dd>Share of training devices with an equal or lower repair rate; not the chance of failure. A percentile of 0% does not mean zero failure risk.</dd></div>
          <div><dt>Historical average annual cost (CAD $)</dt><dd>${amount(device.avg_annual_cost)}</dd></div>
          <div><dt>Model-estimated annual cost (CAD $)</dt><dd>${amount(prediction.predicted_annual_cost)}</dd></div>
          <div><dt>Typical validation error (MAE)</dt><dd>CAD ${amount(prediction.cost_error_range)} / year (not a confidence interval)</dd></div>
          <div><dt>Repair events / year</dt><dd>{prediction.repair_rate_per_year}</dd></div>
          <div><dt>Observed training repair-rate range</dt><dd>{prediction.training_repair_rate_min != null && prediction.training_repair_rate_max != null
            ? `${prediction.training_repair_rate_min.toFixed(3)} to ${prediction.training_repair_rate_max.toFixed(3)} repairs/year` : 'Unavailable'}</dd></div>
          <div><dt>Estimated cost over {prediction.projection_years} years (annual × {prediction.projection_years})</dt><dd>CAD ${amount(prediction.projected_cost_next_years)}</dd></div>
        </dl>
        <p className="subtitle">Assessed {new Date(assessment.assessed_at).toLocaleString()}. This assessment is calculated on demand. Creating a task stores a fresh assessment for traceability.</p>
      </div>}
      </div><div hidden={tab!=='maintenance'}><EquipmentWorkflow readOnly={readOnly} device={device} revision={workflowRevision} onChanged={onWorkflowChanged} /></div>
    </section>
  )
}
