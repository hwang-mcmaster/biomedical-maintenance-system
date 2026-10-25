import { useState } from 'react'
import './App.css'
import { useApi } from './useApi'
import EquipmentForm from './components/EquipmentForm'
import EquipmentTable from './components/EquipmentTable'
import EquipmentDetails from './components/EquipmentDetails'

function App() {
  const health = useApi('/api/health')
  const [revision, setRevision] = useState(0)
  const ready = useApi('/api/ready', revision)
  const equipment = useApi('/api/equipment', revision)
  const [editing, setEditing] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [message, setMessage] = useState('')
  const devices = equipment.data || []
  const selected = devices.find((device) => device.id === selectedId)
  function refresh() { setRevision((value) => value + 1) }
  function saved(device, updated) {
    setMessage(`Equipment ${updated ? 'updated' : 'saved'} (ID ${device.id}). Refreshing the inventory…`)
    setEditing(null)
    setSelectedId(null)
    refresh()
  }
  function deleted(device) {
    setMessage(`Equipment ${device.asset_tag} deleted.`)
    if (editing?.id === device.id) setEditing(null)
    if (selectedId === device.id) setSelectedId(null)
    refresh()
  }
  return (
    <main>
      <header>
        <p className="eyebrow">Senior Engineering Project · Equipment & maintenance review</p>
        <h1>Biomedical Maintenance System</h1>
        <p className="subtitle">Manage equipment and review AI-assisted maintenance estimates.</p>
      </header>
      <section className="panel" aria-labelledby="backend-heading">
        <h2 id="backend-heading">Connection status</h2>
        <div role="status" aria-live="polite">
          {health.loading && <p>Checking the backend connection…</p>}
          {health.error && <p className="error">Backend unavailable. {health.error}</p>}
          {health.data && <p><span className="badge">{health.data.status}</span> {health.data.message}</p>}
          {ready.loading && <p>Checking equipment database…</p>}
          {ready.error && <p className="error">Database not ready. {ready.error}</p>}
          {ready.data && !ready.loading && !ready.error && <p>{ready.data.message}</p>}
        </div>
      </section>
      <p role="status" aria-live="polite">{message}</p>
      <EquipmentForm key={editing?.id || 'new'} device={editing} onSaved={saved} onCancel={() => setEditing(null)} />
      <EquipmentTable devices={devices} loading={equipment.loading} error={equipment.error}
        onRefresh={refresh} onDetails={setSelectedId} onEdit={setEditing} onDeleted={deleted} />
      {selected && <EquipmentDetails key={JSON.stringify(selected)} device={selected} onClose={() => setSelectedId(null)} />}
    </main>
  )
}
export default App
