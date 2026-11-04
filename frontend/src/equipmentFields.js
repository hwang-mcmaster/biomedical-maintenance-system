// Operational metadata is separate from the original eight-column training export.
export const equipmentFields = [
  { key: 'asset_tag', label: 'Asset Tag', type: 'text', maxLength: 50, group: 'Identity and description' },
  { key: 'serial_number', label: 'Serial No.', type: 'text', maxLength: 100, group: 'Identity and description' },
  { key: 'manufacturer', label: 'Manufacturer', type: 'text', maxLength: 100, group: 'Identity and description' },
  { key: 'model_number', label: 'Model number', type: 'text', maxLength: 100, optional: true, group: 'Identity and description' },
  { key: 'model_name', label: 'Model name', type: 'text', maxLength: 100, optional: true, group: 'Identity and description' },
  { key: 'device_type', label: 'Device type', type: 'select', optionsKey: 'device_types', optional: true, group: 'Identity and description' },
  { key: 'firmware_version', label: 'Firmware version', type: 'text', maxLength: 50, optional: true, group: 'Identity and description' },
  { key: 'description', label: 'Description', type: 'textarea', maxLength: 2000, optional: true, group: 'Identity and description' },
  { key: 'department', label: 'Department', type: 'text', maxLength: 100, optional: true, group: 'Location and status' },
  { key: 'department_code', label: 'Department code', type: 'text', maxLength: 30, optional: true, group: 'Location and status' },
  { key: 'location', label: 'Physical location / room', type: 'text', maxLength: 200, optional: true, group: 'Location and status' },
  { key: 'status', label: 'Status', type: 'select', optionsKey: 'statuses', optional: true, group: 'Location and status' },
  { key: 'in_service_date', label: 'In-Service Date', type: 'date', group: 'Lifecycle costs and reference life' },
  { key: 'age_years', label: 'Age (years)', calculated: true, group: 'Lifecycle costs and reference life' },
  { key: 'repair_events', label: 'Repair Events (n)', type: 'number', decimals: 0, defaultValue: '0', group: 'Lifecycle costs and reference life' },
  { key: 'total_historical_cost', label: 'Total Historical Cost (CAD $)', type: 'number', decimals: 2, defaultValue: '0', group: 'Lifecycle costs and reference life' },
  { key: 'avg_annual_cost', label: 'Historical average annual cost (CAD $)', calculated: true, group: 'Lifecycle costs and reference life' },
  { key: 'replacement_cost', label: 'Replacement cost (CAD $)', type: 'number', decimals: 2, optional: true, group: 'Lifecycle costs and reference life' },
  { key: 'expected_useful_life', label: 'Expected useful life (reference years)', type: 'number', decimals: 0, optional: true, group: 'Lifecycle costs and reference life' },
  { key: 'reference_remaining_life_years', label: 'Reference life remaining (years, not AI-predicted)', calculated: true, group: 'Lifecycle costs and reference life' },
]
export const sourceFields = equipmentFields.filter((field) => !field.calculated)
export const fieldGroups = [...new Set(equipmentFields.map((field) => field.group))]
const tableKeys = ['asset_tag', 'serial_number', 'manufacturer', 'model_name', 'device_type', 'department', 'status', 'age_years']
export const inventoryFields = tableKeys.map((key) => equipmentFields.find((field) => field.key === key))

export function displayValue(key, value) {
  if (value == null || value === '') return ['age_years', 'avg_annual_cost', 'reference_remaining_life_years'].includes(key) ? 'N/A' : 'Not recorded'
  if (key === 'age_years' || key === 'reference_remaining_life_years') return Number(value).toFixed(2)
  if (['total_historical_cost', 'avg_annual_cost', 'replacement_cost'].includes(key)) {
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
