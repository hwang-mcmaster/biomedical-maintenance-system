import { useRef, useState } from 'react'
import { request } from '../api'

export default function EquipmentTable({ devices, loading, error, onRefresh, onDetails, onEdit, onDeleted }) {
  const [confirmId, setConfirmId] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [deleteError, setDeleteError] = useState('')
  const deletingRef = useRef(false)
  async function remove(device) {
    if (deletingRef.current) return
    deletingRef.current = true
    setDeleting(device.id)
    setDeleteError('')
    try {
      await request(`/api/equipment/${device.id}`, { method: 'DELETE' })
      setConfirmId(null)
      onDeleted(device)
    } catch (failure) { setDeleteError(failure.message) } finally {
      deletingRef.current = false
      setDeleting(null)
    }
  }
  return (
    <section className="panel" aria-labelledby="equipment-heading">
      <div className="section-heading"><h2 id="equipment-heading">Equipment</h2>
        <button type="button" className="secondary" disabled={loading} onClick={onRefresh}>Refresh table</button></div>
      <div role="status" aria-live="polite">
        {loading && <p>Loading equipment…</p>}
        {error && <p className="error">Unable to refresh equipment. {error} Any displayed rows are from the last successful load.</p>}
        {!loading && !error && devices.length === 0 && <p>No equipment found. Add your first item above.</p>}
      </div>
      {deleteError && <p role="alert" className="error">{deleteError}</p>}
      {devices.length > 0 && <div className="table-wrapper"><table>
        <caption className="sr-only">Biomedical equipment inventory</caption>
        <thead><tr>{['Asset tag', 'Name / model', 'Type', 'Location', 'Status', 'Actions'].map((heading) => <th key={heading} scope="col">{heading}</th>)}</tr></thead>
        <tbody>{devices.map((device) => <tr key={device.id}>
          <td>{device.asset_tag}</td><td>{device.name}</td><td>{device.type}</td><td>{device.location}</td><td>{device.status}</td>
          <td><div className="actions">
            <button type="button" className="secondary" onClick={() => onDetails(device.id)}>Details & assessment</button>
            <button type="button" className="secondary" onClick={() => onEdit(device)}>Edit</button>
            {confirmId === device.id ? <>
              <span>Delete {device.asset_tag} permanently?</span>
              <button type="button" disabled={Boolean(deleting)} onClick={() => remove(device)}>{deleting === device.id ? 'Deleting…' : 'Confirm delete'}</button>
              <button type="button" className="secondary" disabled={Boolean(deleting)} onClick={() => setConfirmId(null)}>Cancel</button>
            </> : <button type="button" className="secondary" disabled={Boolean(deleting)} onClick={() => { setConfirmId(device.id); setDeleteError('') }}>Delete</button>}
          </div></td>
        </tr>)}</tbody>
      </table></div>}
    </section>
  )
}
