<template>
  <div>
    <h1>Dashboard</h1>
    
    <!-- New Dashboard Metrics -->
    <div class="metrics-grid">
      <div class="metric-card open-quotes">
        <div class="metric-value">{{ dashboardMetrics.open_quotes }}</div>
        <div class="metric-label">Open Quotes</div>
      </div>
      <div class="metric-card open-charters">
        <div class="metric-value">{{ dashboardMetrics.open_charters }}</div>
        <div class="metric-label">Open Charters</div>
      </div>
      <div class="metric-card balance-owing" :class="{ 'warning': dashboardMetrics.balance_owing_count > 0 }">
        <div class="metric-value">${{ dashboardMetrics.balance_owing_total.toFixed(2) }}</div>
        <div class="metric-label">Balance Owing ({{ dashboardMetrics.balance_owing_count }} records)</div>
      </div>
      <div class="metric-card vehicle-warning">
        <div class="metric-value">{{ dashboardMetrics.vehicle_warning }}</div>
        <div class="metric-label">Vehicle Status</div>
      </div>
      <div class="metric-card driver-warning">
        <div class="metric-value">{{ dashboardMetrics.driver_warning }}</div>
        <div class="metric-label">Driver Status</div>
      </div>
    </div>
    
    <h2 style="margin-top:2rem;">Recent Bookings</h2>
    <div class="booking-filters">
      <div class="date-selector-group">
        <select v-model="quickDateFilter" @change="onQuickDateChange" class="quick-date-selector">
          <option value="">All Dates</option>
          <option value="today">Today</option>
          <option value="tomorrow">Tomorrow</option>
          <option value="this_week">This Week</option>
          <option value="last_week">Last Week</option>
          <option value="this_month">This Month</option>
          <option value="not_closed">Not Closed</option>
        </select>
        <span v-if="quickDateFilter" class="date-display">{{ formatDateRange(quickDateFilter) }}</span>
      </div>
      <input v-model="searchText" placeholder="Search (fuzzy: client, vehicle, notes, etc.)" />
      <input v-model="searchDate" type="date" placeholder="Date" />
      <input v-model="searchClient" placeholder="Client name or ID" />
    </div>
    <table class="bookings-table">
      <thead>
        <tr>
          <th>Reserve Number</th>
          <th>Date</th>
          <th>Client Name</th>
          <th>Vehicle Requested</th>
          <th>Vehicle Assigned</th>
          <th>Driver</th>
          <th>Vehicle Desc</th>
          <th>Passengers</th>
          <th>Retainer</th>
          <th>Odo Start</th>
          <th>Odo End</th>
          <th>Fuel</th>
          <th>Notes</th>
          <th>Itinerary Stops</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="b in filteredBookings" :key="b.charter_id">
          <td
            class="reserve-number-cell"
            @click="openBooking(b)"
            style="cursor:pointer;font-weight:bold;color:#007bff;text-decoration:underline;"
            title="Click to open booking form"
          >
            {{ b['reserve_number'] }}
          </td>
          <td v-for="field in bookingFields" :key="field" class="editable-cell">
            <input
              v-if="editing.row === b.charter_id && editing.field === field"
              v-model="b[field]"
              @blur="saveEdit(b, field)"
              @keyup.enter="saveEdit(b, field)"
              class="inline-edit"
            />
            <span v-else @click="startEdit(b, field)">
              {{ field === 'itinerary' ? (b.itinerary ? b.itinerary.length : 0) : b[field] }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()

// Open booking in Charter dashboard on double-click
function openBooking(booking) {
  router.push({ path: '/charter', query: { id: booking.charter_id } })
}
import { ref, onMounted, computed } from 'vue'
const bookings = ref([])
const reserveNumbers = ref([])
const dashboardMetrics = ref({
  open_quotes: 0,
  open_charters: 0,
  balance_owing_count: 0,
  balance_owing_total: 0.0,
  driver_warning: 'Loading...',
  vehicle_warning: 'Loading...'
})
const searchText = ref("")
const searchDate = ref("")
const searchClient = ref("")
const quickDateFilter = ref("")

// List of all editable booking fields (column order)
const bookingFields = [
  'charter_date',
  'client_name',
  'vehicle_type_requested',
  'vehicle_booked_id',
  'driver_name',
  'vehicle_description',
  'passenger_load',
  'retainer',
  'odometer_start',
  'odometer_end',
  'fuel_added',
  'vehicle_notes',
  'itinerary'
]

// Inline editing state
const editing = ref({ row: null, field: null })
function startEdit(row, field) {
  editing.value = { row: row.charter_id, field }
}
async function saveEdit(row, field) {
  // PATCH to backend
  await updateBooking(row, field, row[field])
  editing.value = { row: null, field: null }
  // Re-fetch bookings to ensure live data
  await fetchBookings()
}

const filteredBookings = computed(() => {
  return bookings.value.filter(b => {
    // Fuzzy search: client, vehicle, notes, etc.
    const text = searchText.value.toLowerCase()
    const client = (b.client_name || "").toString().toLowerCase()
    const vehicle = (b.vehicle_description || "").toString().toLowerCase()
    const notes = (b.vehicle_notes || "").toString().toLowerCase()
    const reserveNum = (b.reserve_number || "").toString().toLowerCase()
    const matchText =
      !text ||
      client.includes(text) ||
      vehicle.includes(text) ||
      notes.includes(text) ||
      reserveNum.includes(text)
    
    // Quick date filter
    const matchQuickDate = checkQuickDateFilter(b.charter_date)
    
    // Specific date filter
    const matchDate = !searchDate.value || (b.charter_date && b.charter_date.startsWith(searchDate.value))
    // Client filter
    const matchClient = !searchClient.value || client.includes(searchClient.value.toLowerCase()) || reserveNum.includes(searchClient.value.toLowerCase())
    return matchText && matchQuickDate && matchDate && matchClient
  })
})

// Helper function for quick date filtering
const checkQuickDateFilter = (charterDate) => {
  if (!quickDateFilter.value || !charterDate) return true
  
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  const tomorrow = new Date(today)
  tomorrow.setDate(today.getDate() + 1)
  
  const charterDateObj = new Date(charterDate)
  charterDateObj.setHours(0, 0, 0, 0)
  
  switch (quickDateFilter.value) {
    case 'today':
      return charterDateObj.getTime() === today.getTime()
    case 'tomorrow':
      return charterDateObj.getTime() === tomorrow.getTime()
    case 'this_week':
      const startOfWeek = new Date(today)
      startOfWeek.setDate(today.getDate() - today.getDay())
      const endOfWeek = new Date(startOfWeek)
      endOfWeek.setDate(startOfWeek.getDate() + 6)
      return charterDateObj >= startOfWeek && charterDateObj <= endOfWeek
    case 'last_week':
      const startOfLastWeek = new Date(today)
      startOfLastWeek.setDate(today.getDate() - today.getDay() - 7)
      const endOfLastWeek = new Date(startOfLastWeek)
      endOfLastWeek.setDate(startOfLastWeek.getDate() + 6)
      return charterDateObj >= startOfLastWeek && charterDateObj <= endOfLastWeek
    case 'this_month':
      return charterDateObj.getMonth() === today.getMonth() && charterDateObj.getFullYear() === today.getFullYear()
    case 'not_closed':
      // For not_closed, we'll rely on backend filtering - return true here
      return true
    default:
      return true
  }
}

// Handle quick date selector change
const onQuickDateChange = () => {
  if (quickDateFilter.value) {
    searchDate.value = "" // Clear specific date when using quick filter
  }
  // Refresh dashboard metrics with new date filter
  fetchDashboardMetrics()
}

// Update booking field (for dispatch editing)
const updateBooking = async (booking, field, value) => {
  try {
    const response = await fetch(`/api/bookings/${booking.charter_id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        [field]: value
      })
    })
    if (response.ok) {
      console.log(`Updated ${field} for charter ${booking.charter_id}`)
    } else {
      console.error(`Failed to update ${field}:`, response.statusText)
    }
  } catch (error) {
    console.error(`Error updating ${field}:`, error)
  }
}

// Fetch bookings from backend
const fetchBookings = async () => {
  try {
    const res = await fetch('/api/bookings')
    if (res.ok) {
      const data = await res.json()
      bookings.value = data.bookings || []
    }
  } catch (e) {
    console.error('Failed to fetch bookings:', e)
  }
}

// Fetch dashboard metrics with current date filter
const fetchDashboardMetrics = async () => {
  try {
    const params = new URLSearchParams()
    if (quickDateFilter.value) {
      params.append('date_filter', quickDateFilter.value)
    }
    
    const url = `/api/dashboard${params.toString() ? '?' + params.toString() : ''}`
    const metricsRes = await fetch(url)
    
    if (metricsRes.ok) {
      const metricsData = await metricsRes.json()
      dashboardMetrics.value = {
        open_quotes: metricsData.open_quotes || 0,
        open_charters: metricsData.open_charters || 0,
        balance_owing_count: metricsData.balance_owing_count || 0,
        balance_owing_total: metricsData.balance_owing_total || 0.0,
        driver_warning: metricsData.driver_warning || 'No data',
        vehicle_warning: metricsData.vehicle_warning || 'No data'
      }
    }
  } catch (e) {
    console.error('Failed to fetch dashboard metrics:', e)
  }
}

// Format date range for display in dd mmm yy format
const formatDateRange = (filterType) => {
  const today = new Date()
  const formatDate = (date) => {
    const day = date.getDate().toString().padStart(2, '0')
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const month = months[date.getMonth()]
    const year = date.getFullYear().toString().slice(-2)
    return `${day} ${month} ${year}`
  }
  
  switch (filterType) {
    case 'today':
      return formatDate(today)
    case 'tomorrow':
      const tomorrow = new Date(today)
      tomorrow.setDate(today.getDate() + 1)
      return formatDate(tomorrow)
    case 'this_week':
      const startOfWeek = new Date(today)
      startOfWeek.setDate(today.getDate() - today.getDay())
      const endOfWeek = new Date(startOfWeek)
      endOfWeek.setDate(startOfWeek.getDate() + 6)
      return `${formatDate(startOfWeek)} - ${formatDate(endOfWeek)}`
    case 'last_week':
      const startOfLastWeek = new Date(today)
      startOfLastWeek.setDate(today.getDate() - today.getDay() - 7)
      const endOfLastWeek = new Date(startOfLastWeek)
      endOfLastWeek.setDate(startOfLastWeek.getDate() + 6)
      return `${formatDate(startOfLastWeek)} - ${formatDate(endOfLastWeek)}`
    case 'this_month':
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
      const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0)
      return `${formatDate(startOfMonth)} - ${formatDate(endOfMonth)}`
    case 'not_closed':
      return 'Open/Active Only'
    default:
      return ''
  }
}

// Fetch reserve numbers for dropdown
const fetchReserveNumbers = async () => {
  try {
    const response = await fetch('/api/reserve-numbers')
    if (response.ok) {
      reserveNumbers.value = await response.json()
    } else {
      console.error('Failed to fetch reserve numbers:', response.status)
    }
  } catch (error) {
    console.error('Error fetching reserve numbers:', error)
  }
}

onMounted(async () => {
  // Fetch dashboard metrics
  await fetchDashboardMetrics()
  // Fetch bookings from backend
  await fetchBookings()
  // Fetch reserve numbers for dropdown
  await fetchReserveNumbers()
})
</script>

<style scoped>
.booking-filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: center;
}

.date-selector-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.quick-date-selector {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  font-size: 0.9rem;
  min-width: 120px;
}

.date-display {
  font-size: 0.85rem;
  color: #555;
  background: #e9ecef;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-weight: 500;
  white-space: nowrap;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.metric-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  text-align: center;
  border-left: 4px solid #007bff;
}

.metric-card.open-quotes {
  border-left-color: #28a745;
}

.metric-card.open-charters {
  border-left-color: #17a2b8;
}

.metric-card.balance-owing {
  border-left-color: #ffc107;
}

.metric-card.balance-owing.warning {
  border-left-color: #dc3545;
  background: #fff5f5;
}

.metric-card.vehicle-warning, .metric-card.driver-warning {
  border-left-color: #6c757d;
}

.metric-value {
  font-size: 1.8rem;
  font-weight: bold;
  color: #333;
  margin-bottom: 0.5rem;
}

.metric-label {
  font-size: 0.9rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.bookings-table {
  width: 100%;
  margin-top: 2rem;
  border-collapse: collapse;
}
.bookings-table th, .bookings-table td {
  border: 1px solid #ddd;
  padding: 0.5rem 0.75rem;
  text-align: left;
}
.bookings-table th {
  background: #f0f4fa;
}

.editable-cell {
  padding: 0.25rem !important;
}

.inline-edit {
  width: 100%;
  border: 1px solid transparent;
  padding: 0.25rem;
  background: transparent;
  font-size: 0.9rem;
}

.inline-edit:hover {
  border-color: #ddd;
  background: #fff;
}

.inline-edit:focus {
  border-color: #007bff;
  background: #fff;
  outline: none;
}

.reserve-select {
  min-width: 150px;
  max-width: 200px;
}

.reserve-number-cell {
  padding: 0.5rem 0.75rem !important;
  transition: background-color 0.2s ease;
}

.reserve-number-cell:hover {
  background-color: #f8f9fa;
}
</style>
