const TIME_PATTERN = /^\d{2}:\d{2}(?::\d{2})?$/

const ROUTE_LABELS = {
  pickup_at: 'Pickup At',
  dropoff_at: 'Drop-off At',
  leave_red_deer: 'Leave Red Deer',
  pickup_in: 'Pickup In',
  drop_off_at: 'Drop Off At',
  return_to_red_deer: 'Return to Red Deer',
  standby_stop: 'Standby',
  breakdown_at: 'Breakdown At',
  new_vehicle_arrived: 'New Vehicle Arrived',
  extra_time_starts: 'Extra Time Starts',
  travel_arrangement: 'Travel Arrangement'
}

function normalizeTime(value) {
  if (!value) return ''
  const raw = String(value).trim()
  if (TIME_PATTERN.test(raw)) return raw.slice(0, 5)

  const parsed = new Date(raw)
  if (!Number.isNaN(parsed.getTime())) {
    return `${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}`
  }

  return ''
}

function timeToHours(timeStart, timeFinish) {
  const start = normalizeTime(timeStart)
  const finish = normalizeTime(timeFinish)
  if (!start || !finish) return 0

  const [startHours = 0, startMinutes = 0] = start.split(':').map(Number)
  const [finishHours = 0, finishMinutes = 0] = finish.split(':').map(Number)

  let minutes = (finishHours * 60 + finishMinutes) - (startHours * 60 + startMinutes)
  if (minutes < 0) {
    minutes += 24 * 60
  }

  return Math.max(0, Math.round((minutes / 60) * 100) / 100)
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(2)}`
}

function isStandbyRoute(route = {}) {
  const routeType = String(route.route_type || route.type || route.event_type_code || '').toLowerCase()
  const notes = String(route.notes || route.route_notes || route.description || '').toLowerCase()
  return routeType.includes('standby') || routeType.includes('wait') || notes.includes('standby') || notes.includes('wait')
}

function getRouteLabel(route = {}, index = 0) {
  const routeType = String(route.route_type || route.type || route.event_type_code || '').toLowerCase()
  const baseLabel = ROUTE_LABELS[routeType] || routeType.replaceAll('_', ' ').replace(/\b\w/g, (match) => match.toUpperCase()) || `Route ${index + 1}`
  const description = String(route.description || route.address || '').trim()
  return description ? `${baseLabel} - ${description}` : baseLabel
}

function getRouteHours(route = {}) {
  const billedHours = Number.parseFloat(route.billed_hours ?? route.billedTime ?? 0)
  if (Number.isFinite(billedHours) && billedHours > 0) {
    return Math.round(billedHours * 100) / 100
  }

  return timeToHours(route.time_start || route.timeStart, route.time_finish || route.timeFinish)
}

function getRouteRate(route = {}, hourlyRate = 0, standbyRate = 0) {
  if (route.is_billable === false || route.billable === false) return 0
  return isStandbyRoute(route) ? Number(standbyRate || hourlyRate || 0) : Number(hourlyRate || 0)
}

function getRouteCharge(route = {}, hourlyRate = 0, standbyRate = 0) {
  const hours = getRouteHours(route)
  const rate = getRouteRate(route, hourlyRate, standbyRate)
  return Math.round(hours * rate * 100) / 100
}

export function buildRouteChargeBreakdown(routes = [], hourlyRate = 0, standbyRate = 0) {
  const lineItems = (Array.isArray(routes) ? routes : []).map((route, index) => {
    const hours = getRouteHours(route)
    const rate = getRouteRate(route, hourlyRate, standbyRate)
    const amount = Math.round(hours * rate * 100) / 100
    return {
      index,
      label: getRouteLabel(route, index),
      hours,
      rate,
      amount,
      isBillable: route.is_billable !== false && route.billable !== false,
      isStandby: isStandbyRoute(route),
      timeRange: [normalizeTime(route.time_start || route.timeStart), normalizeTime(route.time_finish || route.timeFinish)].filter(Boolean).join(' → ')
    }
  })

  const total = Math.round(lineItems.reduce((sum, item) => sum + item.amount, 0) * 100) / 100
  return {
    total,
    lineItems
  }
}

export { formatCurrency, getRouteCharge, getRouteHours, getRouteLabel, getRouteRate, isStandbyRoute, timeToHours }
