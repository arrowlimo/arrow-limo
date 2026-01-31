<template>
    <!-- Quick Add Beverage Button -->
    <button @click="showBeverageModal = true" class="btn-primary" style="margin-bottom:1.5rem;">Quick Add Beverage</button>

    <!-- Beverage Modal -->
    <div v-if="showBeverageModal" class="modal-overlay">
      <div class="modal-content">
        <h3>Add Beverages to Charter/Client</h3>
        <div class="form-row">
          <label>Charter # or Client Name</label>
          <input v-model="beverageSearch" @input="onBeverageSearch" placeholder="Type to search..." />
          <ul v-if="beverageSearchResults.length" class="search-results">
            <li v-for="result in beverageSearchResults" :key="result.id" @click="selectBeverageTarget(result)">
              {{ result.display }}
            </li>
          </ul>
        </div>
        <div v-if="selectedBeverageTarget">
          <div><strong>Selected:</strong> {{ selectedBeverageTarget.display }}</div>
          <div class="form-row">
            <label>Beverages</label>
            <div v-for="bev in beverageList" :key="bev.id" style="margin-bottom:0.5rem;">
              <span>{{ bev.name }} (${{ bev.price.toFixed(2) }})</span>
              <input type="number" min="0" v-model.number="bev.qty" style="width:60px;margin-left:1rem;" />
            </div>
          </div>
          <button @click="confirmBeverageCart">Confirm Cart</button>
        </div>
        <div v-if="beverageCart.length">
          <h4>Order Summary</h4>
          <table style="width:100%;margin-top:1rem;">
            <thead><tr><th>Beverage</th><th>Qty</th><th>Price</th><th>GST</th><th>Total</th><th>Edit</th></tr></thead>
            <tbody>
              <tr v-for="(item, idx) in beverageCart" :key="item.id">
                <td>{{ item.name }}</td>
                <td>
                  <input type="number" min="0" v-model.number="item.qty" style="width:60px" @change="updateBeverageQty(idx)" />
                </td>
                <td>${{ item.price.toFixed(2) }}</td>
                <td>${{ (item.price * gstRate).toFixed(2) }}</td>
                <td>${{ (item.price * item.qty * (1 + gstRate)).toFixed(2) }}</td>
                <td><button @click="removeBeverage(idx)">Remove</button></td>
              </tr>
            </tbody>
          </table>
          <div style="margin-top:1rem;font-weight:bold;">Subtotal: ${{ beverageSubtotal.toFixed(2) }} | GST: ${{ beverageGST.toFixed(2) }} | Total: ${{ beverageTotal.toFixed(2) }}</div>
          <div style="margin-top:0.5rem;">(Non-printable) Our Cost: ${{ beverageCostTotal.toFixed(2) }}</div>
          <div style="margin-top:0.75rem; display:flex; align-items:center; gap:0.75rem;">
            <label style="display:flex; align-items:center; gap:0.5rem;">
              <input type="checkbox" v-model="beverageInvoiceSeparately" /> Invoice beverages separately
            </label>
            <button @click="persistBeverageOrders" :disabled="!selectedBeverageTarget || selectedBeverageTarget.type !== 'charter'">Save to Charter</button>
            <button @click="printBeverageOrder">Print Order</button>
            <button @click="showBeverageModal = false">Close</button>
          </div>
        </div>
        <button v-if="!beverageCart.length" @click="showBeverageModal = false" style="margin-top:1rem;">Cancel</button>
      </div>
    </div>
  <div>
    <h1>Main</h1>
    
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
          <option value="day">Day</option>
          <option value="today">Today</option>
          <option value="upcoming_week">Upcoming Week</option>
          <option value="this_month">This Month</option>
          <option value="this_year">This Year</option>
          <option value="future_all">Future (All)</option>
        </select>
        <span v-if="quickDateFilter" class="date-display">{{ formatDateRange(quickDateFilter) }}</span>
      </div>
      <select v-model="statusFilter" class="quick-date-selector">
        <option value="">All Statuses</option>
        <option value="Quote">Quote</option>
        <option value="Pending">Pending</option>
        <option value="Confirmed">Confirmed</option>
        <option value="Assigned">Assigned</option>
        <option value="Active">Active</option>
        <option value="Completed">Completed</option>
        <option value="Closed">Closed</option>
        <option value="Cancelled">Cancelled</option>
      </select>
      <select v-model="balanceFilter" class="quick-date-selector">
        <option value="">All Balances</option>
        <option value="positive">Balance &gt; 0</option>
        <option value="negative">Balance &lt; 0</option>
      </select>
      <select v-model="reconciledFilter" class="quick-date-selector">
        <option value="">All Reconciliation</option>
        <option value="Reconciled">Reconciled</option>
        <option value="Not Reconciled">Not Reconciled</option>
        <option value="Cancelled">Cancelled</option>
      </select>
      <label class="inline-filter">
        <input type="checkbox" v-model="nrrOnly" /> NRR Only
      </label>
      <label class="inline-filter">
        <input type="checkbox" v-model="beverageThisWeekOnly" /> Beverage Orders This Week
      </label>
      <input v-model="searchText" placeholder="Search (fuzzy: client, vehicle, notes, etc.)" />
      <input v-model="searchDate" type="date" placeholder="Date" />
      <input v-model="searchClient" placeholder="Client name or ID" />
    </div>
    <table class="bookings-table">
      <thead>
        <tr>
          <th class="sortable-header" @click="sortBy('reserve_number')">
            Reserve Number
            <span class="sort-indicator" v-if="sortField === 'reserve_number'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('charter_date')">
            Date
            <span class="sort-indicator" v-if="sortField === 'charter_date'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('client_name')">
            Client Name
            <span class="sort-indicator" v-if="sortField === 'client_name'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('vehicle')">
            Vehicle
            <span class="sort-indicator" v-if="sortField === 'vehicle'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('vehicle_description')">
            Vehicle Desc
            <span class="sort-indicator" v-if="sortField === 'vehicle_description'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('driver')">
            Driver
            <span class="sort-indicator" v-if="sortField === 'driver'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('pickup_address')">
            Pickup
            <span class="sort-indicator" v-if="sortField === 'pickup_address'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('dropoff_address')">
            Dropoff
            <span class="sort-indicator" v-if="sortField === 'dropoff_address'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('nrr_amount')">
            NRR
            <span class="sort-indicator" v-if="sortField === 'nrr_amount'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('reconciliation_status')">
            Reconciled
            <span class="sort-indicator" v-if="sortField === 'reconciliation_status'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
          <th class="sortable-header" @click="sortBy('status')">
            Status
            <span class="sort-indicator" v-if="sortField === 'status'">
              {{ sortDirection === 'asc' ? '↑' : '↓' }}
            </span>
          </th>
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
              {{ field === 'itinerary_stops' ? (b.itinerary_stops || 0) : displayValue(b, field) }}
            </span>
          </td>
        </tr>
      </tbody>
    </table>
    
    <!-- Booking Detail Modal -->
    <BookingDetail 
      :booking="selectedBooking" 
      :visible="showBookingDetail" 
      @close="closeBookingDetail"
      @edit="editBooking"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import BookingDetail from '@/components/BookingDetail.vue'
import { formatDate, formatDateRange } from '@/utils/dateFormatter'

const router = useRouter()

// Beverage modal state
const showBeverageModal = ref(false)
const beverageSearch = ref("")
const beverageSearchResults = ref([])
const selectedBeverageTarget = ref(null)
const beverageList = ref([
  { id: 1, name: 'Water', price: 2.5, cost: 1.0, qty: 0 },
  { id: 2, name: 'Soda', price: 3.0, cost: 1.2, qty: 0 },
  { id: 3, name: 'Beer', price: 6.0, cost: 2.5, qty: 0 },
  { id: 4, name: 'Wine', price: 12.0, cost: 5.0, qty: 0 },
  { id: 5, name: 'Champagne', price: 25.0, cost: 10.0, qty: 0 }
])
const beverageCart = ref([])
const beverageInvoiceSeparately = ref(false)

function updateBeverageQty(idx) {
  // Remove if qty is 0 or less
  if (beverageCart.value[idx].qty <= 0) {
    beverageCart.value.splice(idx, 1)
  }
}

function removeBeverage(idx) {
  beverageCart.value.splice(idx, 1)
}
const gstRate = 0.05
const beverageSubtotal = computed(() => beverageCart.value.reduce((sum, item) => sum + item.price * item.qty, 0))
const beverageGST = computed(() => beverageCart.value.reduce((sum, item) => sum + item.price * item.qty * gstRate, 0))
const beverageTotal = computed(() => beverageSubtotal.value + beverageGST.value)
const beverageCostTotal = computed(() => beverageCart.value.reduce((sum, item) => sum + item.cost * item.qty * (1 + gstRate), 0))

async function onBeverageSearch() {
  const query = beverageSearch.value.trim().toLowerCase();
  if (!query) {
    beverageSearchResults.value = [];
    return;
  }
  // Fetch charters (bookings) via search endpoint
  let charters = [];
  try {
    const res = await fetch(`/api/bookings/search?q=${encodeURIComponent(query)}&limit=10`);
    if (res.ok) {
      const data = await res.json();
      charters = (data.results || []).map(b => ({
        id: `charter_${b.charter_id}`,
        display: `Charter #${b.reserve_number || b.charter_id} - ${b.client_name || ''}`.trim(),
        charter_id: b.charter_id,
        client_name: b.client_name || '',
        type: 'charter',
      }));
    }
  } catch (e) { /* ignore */ }

  // Fetch clients via search endpoint
  let clients = [];
  try {
    const res = await fetch(`/api/clients/search?query=${encodeURIComponent(query)}&limit=10`);
    if (res.ok) {
      const data = await res.json();
      clients = (data.results || []).map(c => ({
        id: `client_${c.client_id}`,
        display: `Client: ${c.client_name || c.name || c.client_id}`.trim(),
        client_id: c.client_id,
        client_name: c.client_name || c.name || '',
        type: 'client',
      }));
    }
  } catch (e) { /* ignore */ }

  // Fuzzy filter
  const results = [ ...charters, ...clients ];
  beverageSearchResults.value = results.slice(0, 10); // limit to 10 results
}
function selectBeverageTarget(result) {
  selectedBeverageTarget.value = result
  beverageSearchResults.value = []
}
function confirmBeverageCart() {
  beverageCart.value = beverageList.value.filter(b => b.qty > 0).map(b => ({ ...b }))
}
function printBeverageOrder() {
  // TODO: Implement printable order with all required fields
  window.print()
}

// Persist beverage orders to backend (if target is a charter)
async function saveBeverageOrders() {
  if (!selectedBeverageTarget.value || selectedBeverageTarget.value.type !== 'charter') return
  const runId = selectedBeverageTarget.value.charter_id
  const orders = beverageCart.value.map(({ id, name, qty, price, cost }) => ({ id, name, qty, price, cost }))
  try {
    const res = await fetch(`/api/charter/${runId}/beverage_orders`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beverage_orders: orders })
    })
    if (!res.ok) throw new Error('Failed to save beverage orders')
  } catch (e) {
    console.error('saveBeverageOrders error:', e)
  }
}

// Optionally mark beverage invoicing separate
async function invoiceBeveragesSeparately(separately = true) {
  if (!selectedBeverageTarget.value || selectedBeverageTarget.value.type !== 'charter') return
  try {
    await fetch('/api/beverage_orders/invoice_separately', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ charter_id: selectedBeverageTarget.value.charter_id, invoice_separately: separately })
    })
  } catch (e) { /* ignore */ }
}

// Combined save action from the modal
import { toast } from '@/toast/toastStore'

async function persistBeverageOrders() {
  await saveBeverageOrders()
  if (beverageInvoiceSeparately.value) {
    await invoiceBeveragesSeparately(true)
  }
  toast.success('Beverage order saved' + (beverageInvoiceSeparately.value ? ' and flagged for separate invoicing.' : '.'))
}

// Open booking in Charter dashboard on double-click
function openBooking(booking) {
  selectedBooking.value = booking
  showBookingDetail.value = true
}

const closeBookingDetail = () => {
  showBookingDetail.value = false
  selectedBooking.value = {}
}

const editBooking = (booking) => {
  // Handle booking editing - could navigate to edit form
  router.push({ path: '/charter', query: { id: booking.charter_id } })
  closeBookingDetail()
}
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
const statusFilter = ref("")
const balanceFilter = ref("")
const reconciledFilter = ref("")
const nrrOnly = ref(false)
const beverageThisWeekOnly = ref(false)

// Booking detail modal state
const showBookingDetail = ref(false)
const selectedBooking = ref({})

// Sorting state
const sortField = ref('charter_date')
const sortDirection = ref('desc')

// Sortable columns configuration
const sortableColumns = {
  'reserve_number': { field: 'reserve_number', label: 'Reserve Number' },
  'charter_date': { field: 'charter_date', label: 'Date' },
  'client_name': { field: 'client_name', label: 'Client Name' },
  'vehicle': { field: 'vehicle', label: 'Vehicle' },
  'vehicle_description': { field: 'vehicle_description', label: 'Vehicle Desc' },
  'driver': { field: 'driver', label: 'Driver' },
  'pickup_address': { field: 'pickup_address', label: 'Pickup' },
  'dropoff_address': { field: 'dropoff_address', label: 'Dropoff' },
  'nrr_amount': { field: 'nrr_amount', label: 'NRR' },
  'reconciliation_status': { field: 'reconciliation_status', label: 'Reconciled' },
  'status': { field: 'status', label: 'Status' }
}

// List of all editable booking fields (column order)
const bookingFields = [
  'charter_date',
  'client_name',
  'vehicle',
  'vehicle_description',
  'driver',
  'pickup_address',
  'dropoff_address',
  'nrr_amount',
  'reconciliation_status',
  'status'
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

// Sorting function
function sortBy(field) {
  if (sortField.value === field) {
    // Toggle direction if same field
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    // New field, default to ascending
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

const filteredBookings = computed(() => {
  let filtered = bookings.value.filter(b => {
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
    
    // Quick date filter - ensure it's truly empty for "All Dates"
    const matchQuickDate = !quickDateFilter.value || quickDateFilter.value === "" || checkQuickDateFilter(b.charter_date)
    
    // Specific date filter
    const matchDate = !searchDate.value || (b.charter_date && b.charter_date.startsWith(searchDate.value))
    // Client filter
    const matchClient = !searchClient.value || client.includes(searchClient.value.toLowerCase()) || reserveNum.includes(searchClient.value.toLowerCase())

    // Status filter
    const statusValue = (b.status || "").toString().toLowerCase()
    const matchStatus = !statusFilter.value || statusValue === statusFilter.value.toLowerCase()

    // Balance filters
    const balanceValue = parseFloat(b.balance || 0)
    const matchBalance = !balanceFilter.value
      || (balanceFilter.value === 'positive' && balanceValue > 0)
      || (balanceFilter.value === 'negative' && balanceValue < 0)

    // Reconciliation status filter
    const reconciledValue = (b.reconciliation_status || "").toString()
    const matchReconciled = !reconciledFilter.value || reconciledValue === reconciledFilter.value

    // NRR filter (check nrr_amount from payments)
    const matchNrr = !nrrOnly.value || parseFloat(b.nrr_amount || 0) > 0

    // Beverage orders this week filter
    const matchBeverage = !beverageThisWeekOnly.value || !!b.beverage_orders_this_week
    
    return matchText && matchQuickDate && matchDate && matchClient && matchStatus && matchBalance && matchReconciled && matchNrr && matchBeverage
  })

  // Apply sorting
  return filtered.sort((a, b) => {
    let valueA = a[sortField.value] || ''
    let valueB = b[sortField.value] || ''
    
    // Handle different data types
    if (sortField.value === 'charter_date') {
      valueA = new Date(valueA)
      valueB = new Date(valueB)
    } else if (sortField.value === 'retainer' || sortField.value === 'vehicle_capacity') {
      valueA = parseFloat(valueA) || 0
      valueB = parseFloat(valueB) || 0
    } else {
      valueA = valueA.toString().toLowerCase()
      valueB = valueB.toString().toLowerCase()
    }
    
    if (valueA < valueB) {
      return sortDirection.value === 'asc' ? -1 : 1
    }
    if (valueA > valueB) {
      return sortDirection.value === 'asc' ? 1 : -1
    }
    return 0
  })
})

// Helper function for quick date filtering
const checkQuickDateFilter = (charterDate) => {
  if (!quickDateFilter.value || !charterDate) return true
  
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  const charterDateObj = new Date(charterDate)
  charterDateObj.setHours(0, 0, 0, 0)
  
  switch (quickDateFilter.value) {
    case 'day':
      if (searchDate.value) {
        const targetDateObj = new Date(searchDate.value)
        targetDateObj.setHours(0, 0, 0, 0)
        return charterDateObj.getTime() === targetDateObj.getTime()
      }
      return charterDateObj.getTime() === today.getTime()
    case 'today':
      return charterDateObj.getTime() === today.getTime()
    case 'upcoming_week':
      const endOfUpcomingWeek = new Date(today)
      endOfUpcomingWeek.setDate(today.getDate() + 7)
      return charterDateObj >= today && charterDateObj <= endOfUpcomingWeek
    case 'this_month':
      return charterDateObj.getMonth() === today.getMonth() && charterDateObj.getFullYear() === today.getFullYear()
    case 'this_year':
      return charterDateObj.getFullYear() === today.getFullYear()
    case 'future_all':
      return charterDateObj >= today
    default:
      return true
  }
}

// Handle quick date selector change
const onQuickDateChange = () => {
  if (quickDateFilter.value && quickDateFilter.value !== 'day') {
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

// Display helper for table cells
const displayValue = (row, field) => {
  const val = row[field]
  if (field === 'charter_date') {
    return formatDate(val)
  }
  if (field === 'nrr_amount') {
    return val ? `$${parseFloat(val).toFixed(2)}` : '$0.00'
  }
  if (field === 'pickup_address' || field === 'dropoff_address') {
    return val || '(not set)'
  }
  return val || ''
}

// formatDateRange is imported from utils; remove local duplicate to avoid redeclaration

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

.inline-filter {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  color: #444;
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

.sortable-header {
  cursor: pointer;
  user-select: none;
  position: relative;
  transition: background-color 0.2s ease;
}

.sortable-header:hover {
  background-color: #e3f2fd;
}

.sort-indicator {
  font-size: 12px;
  margin-left: 5px;
  color: #007bff;
  font-weight: bold;
}

.sortable-header:active {
  background-color: #d1ecf1;
}
</style>
