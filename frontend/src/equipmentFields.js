// The agreed dataset order, shared by the form, table and details screen.
export const equipmentFields = [
  { key: 'asset_tag', label: 'Asset Tag', type: 'text', maxLength: 50 },
  { key: 'serial_number', label: 'Serial No.', type: 'text', maxLength: 100 },
  { key: 'manufacturer', label: 'Manufacturer', type: 'text', maxLength: 100 },
  { key: 'in_service_date', label: 'In-Service Date', type: 'date' },
  { key: 'age_years', label: 'Age (years)', type: 'number', decimals: 3 },
  { key: 'repair_events', label: 'Repair Events (n)', type: 'number', decimals: 0 },
  { key: 'total_historical_cost', label: 'Total Historical Cost ($)', type: 'number', decimals: 2 },
  { key: 'avg_annual_cost', label: 'Avg. Annual Cost ($)', type: 'number', decimals: 2 },
]

export function displayValue(key, value) {
  if (key === 'total_historical_cost' || key === 'avg_annual_cost') {
    return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return String(value)
}
