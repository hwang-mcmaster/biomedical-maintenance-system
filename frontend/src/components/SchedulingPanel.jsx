import { useRef, useState } from 'react'
import { request } from '../api'
import { torontoToday } from '../equipmentFields'

const nextDay = () => new Date(Date.parse(`${torontoToday()}T00:00:00Z`) + 86400000).toISOString().slice(0, 10)
const clock = (instant) => new Intl.DateTimeFormat(undefined, { timeZone: 'America/Toronto', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(instant))
const qualifications = (text) => [...new Set(text.split(',').map(value => value.trim()).filter(Boolean))]

export default function SchedulingPanel({ devices, equipmentLoading, equipmentError }) {
  const [day, setDay] = useState(nextDay)
  const [technicians, setTechnicians] = useState([])
  const [tasks, setTasks] = useState([])
  const [bookings, setBookings] = useState([])
  const [demoEquipment, setDemoEquipment] = useState('')
  const [demo, setDemo] = useState(false)
  const [errors, setErrors] = useState([])
  const [generating, setGenerating] = useState(false)
  const [result, setResult] = useState(null)
  const pending = useRef(false)
  const sequence = useRef(0)
  const identifier = (prefix) => `${prefix}-${++sequence.current}`
  const signature = JSON.stringify({ day, technicians, tasks, bookings, devices })
  const preview = result?.signature === signature ? result.data : null

  function invalidate() { setResult(null); setErrors([]) }
  function update(setter, id, patch) {
    invalidate()
    setter(previous => previous.map(item => item.id === id ? { ...item, ...patch } : item))
  }
  function remove(setter, id) { invalidate(); setter(previous => previous.filter(item => item.id !== id)) }
  function loadDemo() {
    const device = devices.find(item => item.id === demoEquipment) || devices[0]
    if (!device) return
    const skill = device.device_type || 'General'
    const first = identifier('tech'), second = identifier('tech')
    setTechnicians([
      { id: first, name: 'Demo technician A', qualifications: [...new Set([skill, 'General'])].join(', '), availability: [{ start: '09:00', end: '12:00' }, { start: '13:00', end: '17:00' }] },
      { id: second, name: 'Demo technician B', qualifications: 'General', availability: [{ start: '10:00', end: '16:00' }] },
    ])
    setTasks([
      { id: identifier('task'), equipment_id: device.id, title: 'Equipment inspection', priority: 'High', required_qualification: skill, duration_minutes: '60' },
      { id: identifier('task'), equipment_id: device.id, title: 'Preventive maintenance', priority: 'Medium', required_qualification: skill, duration_minutes: '90' },
      { id: identifier('task'), equipment_id: device.id, title: 'Review service records', priority: 'Low', required_qualification: 'General', duration_minutes: '30' },
    ])
    setBookings([{ id: identifier('booking'), equipment_id: device.id, technician_id: first, start: '09:00', end: '10:00' }])
    setDemo(true)
    invalidate()
  }
  function addTechnician() {
    invalidate()
    setTechnicians(previous => [...previous, { id: identifier('tech'), name: '', qualifications: '', availability: [{ start: '09:00', end: '17:00' }] }])
  }
  function addTask() {
    invalidate()
    setTasks(previous => [...previous, { id: identifier('task'), equipment_id: devices[0]?.id || '', title: '', priority: 'Medium', required_qualification: devices[0]?.device_type || 'General', duration_minutes: '60' }])
  }
  async function generate(event) {
    event.preventDefault()
    if (pending.current) return
    const found = []
    if (!day || day < torontoToday()) found.push('Choose today or a future schedule date.')
    if (!technicians.length) found.push('Add at least one technician.')
    if (!tasks.length) found.push('Add at least one maintenance task.')
    const equipmentIds = new Set(devices.map(device => device.id))
    technicians.forEach((tech, index) => {
      if (!tech.name.trim() || !qualifications(tech.qualifications).length) found.push(`Technician ${index + 1} needs a name and at least one qualification.`)
      tech.availability.forEach(window => { if (!window.start || !window.end || window.start >= window.end) found.push(`Technician ${index + 1}: each availability end must be after its start.`) })
    })
    tasks.forEach((task, index) => {
      if (!equipmentIds.has(task.equipment_id)) found.push(`Task ${index + 1}: choose an equipment item from the current inventory.`)
      if (!task.title.trim() || !task.required_qualification.trim()) found.push(`Task ${index + 1} needs a title and required qualification.`)
      const duration = Number(task.duration_minutes)
      if (!task.duration_minutes || !Number.isInteger(duration) || duration < 1 || duration > 1440) found.push(`Task ${index + 1}: enter a duration from 1 to 1440 whole minutes.`)
    })
    bookings.forEach((booking, index) => {
      if (!equipmentIds.has(booking.equipment_id) || !technicians.some(tech => tech.id === booking.technician_id)) found.push(`Booking ${index + 1}: choose existing equipment and a supplied technician.`)
      if (!booking.start || !booking.end || booking.start >= booking.end) found.push(`Booking ${index + 1}: end must be after start.`)
    })
    setErrors(found)
    setResult(null)
    if (found.length) return
    const payload = { schedule_date: day,
      technicians: technicians.map(tech => ({ ...tech, name: tech.name.trim(), qualifications: qualifications(tech.qualifications) })),
      tasks: tasks.map(task => ({ ...task, title: task.title.trim(), required_qualification: task.required_qualification.trim(), duration_minutes: Number(task.duration_minutes) })),
      existing_bookings: bookings,
    }
    pending.current = true
    setGenerating(true)
    try { setResult({ signature, data: await request('/api/scheduling/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }) }) }
    catch (error) { setErrors(error.validationMessages?.length ? error.validationMessages : [error.message]) }
    finally { pending.current = false; setGenerating(false) }
  }
  function input(label, value, onChange, type = 'text', attributes = {}) {
    return <label className="schedule-field">{label}<input aria-label={label} type={type} value={value} onChange={event => onChange(event.target.value)} {...attributes} /></label>
  }
  function equipmentSelect(label, value, onChange) {
    return <label className="schedule-field">{label}<select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
      <option value="">{label === 'Equipment for demo inputs' ? 'Use first saved equipment' : 'Choose equipment'}</option>{devices.map(device => <option key={device.id} value={device.id}>{device.asset_tag} · {device.device_type || 'type not recorded'}</option>)}
    </select></label>
  }
  return (
    <section className="panel" aria-labelledby="scheduling-heading">
      <h2 id="scheduling-heading">Scheduling prototype</h2>
      <p>Generate a single-day draft using saved equipment, task requirements and entered technician availability. All times use America/Toronto.</p>
      <p className="subtitle">Priorities are entered workload priorities, not AI failure probabilities. Qualifications are project labels, not verified personnel credentials. Drafts are not saved or booked.</p>
      {equipmentLoading && <p role="status">Refreshing equipment for scheduling…</p>}
      {equipmentError && <p className="error">Refresh the equipment table before scheduling. {equipmentError}</p>}
      {!devices.length && <p>Add equipment before creating maintenance tasks.</p>}
      <form id="scheduling-form" onSubmit={generate} noValidate>
        <fieldset disabled={generating || equipmentLoading || Boolean(equipmentError)}>
          <legend className="sr-only">Scheduling inputs</legend>
          <div className="form-grid">
            {input('Schedule date', day, value => { setDay(value); invalidate() }, 'date', { min: torontoToday() })}
            {equipmentSelect('Equipment for demo inputs', demoEquipment, setDemoEquipment)}
          </div>
          <div className="actions"><button type="button" className="secondary" disabled={!devices.length} onClick={loadDemo}>Load demo scheduling inputs</button>
            <button type="button" className="secondary" onClick={() => { setTasks([]); setTechnicians([]); setBookings([]); setDemo(false); invalidate() }}>Clear scheduling inputs</button></div>
          {demo && <p className="notice">Demo task/technician data loaded. Equipment references are real saved records; names, qualifications, durations and availability are demonstration inputs.</p>}
          <h3>Technicians and availability</h3>
          <button type="button" className="secondary" onClick={addTechnician} disabled={technicians.length >= 30}>Add technician</button>
          {technicians.map((tech, index) => <div className="schedule-card" key={tech.id}>
            <h4>Technician {index + 1} · {tech.id}</h4>
            <div className="form-grid">
              {input(`Technician ${index + 1} name`, tech.name, name => update(setTechnicians, tech.id, { name }), 'text', { maxLength: 100 })}
              {input(`Technician ${index + 1} qualifications (comma separated)`, tech.qualifications, value => update(setTechnicians, tech.id, { qualifications: value }))}
            </div>
            {tech.availability.map((window, windowIndex) => <div className="schedule-window" key={windowIndex}>
              {input(`Technician ${index + 1} window ${windowIndex + 1} start`, window.start, start => update(setTechnicians, tech.id, { availability: tech.availability.map((item, i) => i === windowIndex ? { ...item, start } : item) }), 'time')}
              {input(`Technician ${index + 1} window ${windowIndex + 1} end`, window.end, end => update(setTechnicians, tech.id, { availability: tech.availability.map((item, i) => i === windowIndex ? { ...item, end } : item) }), 'time')}
              <button type="button" className="secondary" onClick={() => update(setTechnicians, tech.id, { availability: tech.availability.filter((_, i) => i !== windowIndex) })}>Remove availability window</button>
            </div>)}
            <div className="actions"><button type="button" className="secondary" disabled={tech.availability.length >= 10} onClick={() => update(setTechnicians, tech.id, { availability: [...tech.availability, { start: '09:00', end: '17:00' }] })}>Add availability window</button>
              <button type="button" className="secondary" onClick={() => { remove(setTechnicians, tech.id); setBookings(previous => previous.filter(booking => booking.technician_id !== tech.id)) }}>Remove technician</button></div>
          </div>)}
          <h3>Maintenance tasks</h3>
          <button type="button" className="secondary" onClick={addTask} disabled={!devices.length || tasks.length >= 100}>Add maintenance task</button>
          {tasks.map((task, index) => <div className="schedule-card" key={task.id}>
            <h4>Task {index + 1} · {task.id}</h4><div className="form-grid">
              {equipmentSelect(`Task ${index + 1} equipment`, task.equipment_id, equipment_id => update(setTasks, task.id, { equipment_id, required_qualification: devices.find(device => device.id === equipment_id)?.device_type || 'General' }))}
              {input(`Task ${index + 1} title`, task.title, title => update(setTasks, task.id, { title }), 'text', { maxLength: 150 })}
              <label className="schedule-field">Task {index + 1} priority<select aria-label={`Task ${index + 1} priority`} value={task.priority} onChange={event => update(setTasks, task.id, { priority: event.target.value })}>{['High', 'Medium', 'Low'].map(priority => <option key={priority}>{priority}</option>)}</select></label>
              {input(`Task ${index + 1} required qualification`, task.required_qualification, required_qualification => update(setTasks, task.id, { required_qualification }), 'text', { maxLength: 100 })}
              {input(`Task ${index + 1} duration (minutes)`, task.duration_minutes, duration_minutes => update(setTasks, task.id, { duration_minutes }), 'number', { min: 1, max: 1440, step: 1 })}
            </div><button type="button" className="secondary" onClick={() => remove(setTasks, task.id)}>Remove task</button>
          </div>)}
          <h3>Existing bookings to avoid</h3>
          <p className="subtitle">Enter known bookings for this day. The prototype has no saved booking database.</p>
          <button type="button" className="secondary" disabled={!technicians.length || !devices.length || bookings.length >= 200} onClick={() => { invalidate(); setBookings(previous => [...previous, { id: identifier('booking'), equipment_id: devices[0].id, technician_id: technicians[0].id, start: '09:00', end: '10:00' }]) }}>Add existing booking</button>
          {bookings.map((booking, index) => <div className="schedule-card" key={booking.id}><div className="form-grid">
            {equipmentSelect(`Booking ${index + 1} equipment`, booking.equipment_id, equipment_id => update(setBookings, booking.id, { equipment_id }))}
            <label className="schedule-field">Booking {index + 1} technician<select aria-label={`Booking ${index + 1} technician`} value={booking.technician_id} onChange={event => update(setBookings, booking.id, { technician_id: event.target.value })}>{technicians.map(tech => <option key={tech.id} value={tech.id}>{tech.name || tech.id}</option>)}</select></label>
            {input(`Booking ${index + 1} start`, booking.start, start => update(setBookings, booking.id, { start }), 'time')}
            {input(`Booking ${index + 1} end`, booking.end, end => update(setBookings, booking.id, { end }), 'time')}
          </div><button type="button" className="secondary" onClick={() => remove(setBookings, booking.id)}>Remove booking</button></div>)}
          <div className="actions"><button type="submit" disabled={generating || !devices.length}>{generating ? 'Generating…' : 'Generate schedule preview'}</button></div>
        </fieldset>
        {errors.length > 0 && <div role="alert" className="error"><p>Schedule could not be generated:</p><ul>{errors.map((message, index) => <li key={index}>{message}</li>)}</ul></div>}
      </form>
      {result && !preview && <p role="status">Equipment or inputs changed. Generate a new preview.</p>}
      {preview && <div className="schedule-results">
        <p role="status">Schedule preview generated: {preview.assignments.length} scheduled, {preview.unscheduled.length} unassigned.</p>
        <p>{preview.schedule_date} · {preview.timezone}. Preview only; not saved.</p>
        <p className="subtitle">{preview.algorithm}</p>
        {preview.assignments.length > 0 && <div className="table-wrapper"><table><caption>Proposed assignments</caption>
          <thead><tr>{['Equipment', 'Task', 'Priority', 'Qualification', 'Technician', 'Start', 'End', 'Minutes'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
          <tbody>{preview.assignments.map(item => <tr key={item.task_id}><td>{item.asset_tag}</td><td>{item.title}</td><td>{item.priority}</td><td>{item.required_qualification}</td><td>{item.technician_name}</td><td>{clock(item.start)}</td><td>{clock(item.end)}</td><td>{item.duration_minutes}</td></tr>)}</tbody>
        </table></div>}
        {preview.unscheduled.length > 0 && <div className="table-wrapper"><table><caption>Unassigned tasks</caption>
          <thead><tr><th>Equipment</th><th>Task</th><th>Priority</th><th>Reason</th></tr></thead>
          <tbody>{preview.unscheduled.map(item => <tr key={item.task_id}><td>{item.asset_tag}</td><td>{item.title}</td><td>{item.priority}</td><td>{item.reason}</td></tr>)}</tbody>
        </table></div>}
        <ul className="subtitle">{preview.notices.map(notice => <li key={notice}>{notice}</li>)}</ul>
      </div>}
    </section>
  )
}
