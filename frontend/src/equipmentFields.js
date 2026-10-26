// The agreed dataset order, shared by the form, table and details screen.
export const equipmentFields = [
  { key: 'asset_tag', label: 'Asset Tag', type: 'text', maxLength: 50 },
  { key: 'serial_number', label: 'Serial No.', type: 'text', maxLength: 100 },
  { key: 'manufacturer', label: 'Manufacturer', type: 'text', maxLength: 100 },
  { key: 'in_service_date', label: 'In-Service Date', type: 'date' },
  { key: 'age_years', label: 'Age (years)', type: 'number', decimals: 2, calculated: true },
  { key: 'repair_events', label: 'Repair Events (n)', type: 'number', decimals: 0, defaultValue: '0' },
  { key: 'total_historical_cost', label: 'Total Historical Cost (CAD $)', type: 'number', decimals: 2, defaultValue: '0' },
  { key: 'avg_annual_cost', label: 'Avg. Annual Cost (CAD $)', type: 'number', decimals: 2, calculated: true },
]

export const sourceFields = equipmentFields.filter((field) => !field.calculated)

export function displayValue(key, value) {
  if (value == null) return 'N/A'
  if (key === 'age_years') return Number(value).toFixed(2)
  if (key === 'total_historical_cost' || key === 'avg_annual_cost') {
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return String(value)
}

export function torontoToday() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Toronto', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date())
  const get = (type) => parts.find((part) => part.type === type).value
  return `${get('year')}-${get('month')}-${get('day')}`
}

export function previewMetrics(inServiceDate, totalCost, asOf) {
  const start = Date.parse(`${inServiceDate}T00:00:00Z`)
  const end = Date.parse(`${asOf}T00:00:00Z`)
  if (!Number.isFinite(start) || !Number.isFinite(end)) return { age_years: null, avg_annual_cost: null }
  const age = Math.max(0, (end - start) / 86400000) / 365.25
  const cost = Number(totalCost || 0)
  return { age_years: age, avg_annual_cost: age > 0 && Number.isFinite(cost) && cost >= 0 ? cost / age : null }
}
