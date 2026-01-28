<template>
  <form @submit.prevent="submitForm">
    <h2>Quote / Charter Booking</h2>

    <!-- Duplicate From Existing -->
    <div class="container-box">
      <h3>Duplicate From Existing</h3>
      <div class="form-row">
        <input v-model="dupQuery" @input="searchExisting" placeholder="Search by reserve # or client name" />
        <button type="button" @click="showDupModal = true">Browse…</button>
      </div>
      <ul v-if="dupResults.length" class="search-results">
        <li v-for="r in dupResults" :key="r.charter_id" @click="applyDuplicate(r)">
          #{{ r.reserve_number || r.charter_id }} — {{ r.client_name }} — {{ r.charter_date?.slice(0,10) }}
        </li>
      </ul>
    </div>

    <!-- Basic Details -->
    <div class="container-box">
      <h3>Charter Details</h3>
      <div class="form-row"><label>Date</label><input v-model="form.date" type="date" /></div>
      <div class="form-row"><label>Client Name</label>
        <div style="flex:1; position: relative;">
          <input v-model="form.client_name" type="text" @input="onClientInput" @focus="clientDropdownOpen=true" autocomplete="off" />
          <ul v-if="clientDropdownOpen && clientOptions.length" class="search-results" style="position:absolute; z-index:10; background:#fff; border:1px solid #ddd; width:100%; max-height:200px; overflow:auto;">
            <li v-for="c in clientOptions" :key="c.client_id" @click="selectClient(c)">
              {{ c.client_name }} <small v-if="c.phone">— {{ c.phone }}</small>
            </li>
          </ul>
        </div>
      </div>
      <div class="form-row"><label>Phone</label><input v-model="form.phone" type="tel" /></div>
      <div class="form-row"><label>Email</label><input v-model="form.email" type="email" /></div>
      <div class="form-row"><label>Vehicle Type Requested</label><input v-model="form.vehicle_type_requested" type="text" placeholder="e.g. sedan, party bus" /></div>
      <div class="form-row"><label>Vehicle Booked ID</label><input v-model="form.vehicle_booked_id" type="text" placeholder="e.g. L-24" /></div>
      <div class="form-row"><label>Driver Name</label><input v-model="form.driver_name" type="text" /></div>
      <div class="form-row"><label>Passenger Load</label><input v-model="form.passenger_load" type="number" /></div>
    </div>

    <!-- Itinerary Section -->
    <div class="container-box">
      <h3>Itinerary</h3>
      <div v-for="(stop, idx) in form.itinerary" :key="idx" class="itinerary-row">
        <input v-model="stop.time24" type="time" placeholder="24h" />
        <select v-model="stop.type">
          <option>Leave Red Deer For</option>
          <option>Returned to Red Deer</option>
          <option>Pick Up At</option>
          <option>Drop Off At</option>
        </select>
        <input v-model="stop.directions" type="text" placeholder="Directions" />
        <button type="button" @click="removeStop(idx)">Remove</button>
      </div>
      <button type="button" @click="addStop">Add Stop</button>
    </div>

    <!-- Invoice Section -->
    <div class="container-box">
      <h3>Invoice</h3>
      <div class="form-row"><label>Default Hourly Charge</label><input v-model="form.default_hourly_charge" type="number" /></div>
      <div class="form-row"><label>Package Rate</label><input v-model="form.package_rate" type="number" /></div>
      <div class="form-row"><label>GST</label><input v-model="form.gst" type="number" /></div>
      <div class="form-row"><label>Total</label><input v-model="form.total" type="number" /></div>
    </div>

    <!-- Notes Section -->
    <div class="container-box">
      <label>Client Notes</label>
      <textarea v-model="form.client_notes" rows="3" placeholder="Notes for client and staff..."></textarea>
    </div>

    <button type="submit">Save Booking / Quote</button>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { toast } from '@/toast/toastStore'

const form = ref({
  date: '',
  client_name: '',
  phone: '',
  email: '',
  vehicle_type_requested: '',
  vehicle_booked_id: '',
  driver_name: '',
  passenger_load: '',
  itinerary: [],
  default_hourly_charge: '',
  package_rate: '',
  gst: '',
  total: '',
  client_notes: ''
})

const dupQuery = ref('')
const dupResults = ref([])
const showDupModal = ref(false)
const clientOptions = ref([])
const clientDropdownOpen = ref(false)
const selectedClientId = ref(null)

async function searchExisting() {
  const q = dupQuery.value.trim()
  if (!q) { dupResults.value = []; return }
  try {
    const res = await fetch(`/api/bookings/search?q=${encodeURIComponent(q)}&limit=10`)
    if (res.ok) {
      const data = await res.json()
      dupResults.value = data.results || []
    }
  } catch (e) { /* ignore */ }
}

async function applyDuplicate(hit) {
  try {
    const res = await fetch(`/api/bookings/${hit.charter_id}`)
    if (!res.ok) return
    const b = await res.json()
    // Map fields to our form model
    form.value.date = (b.charter_date || '').slice(0,10)
    form.value.client_name = b.client_name || ''
    form.value.phone = ''
    form.value.email = ''
    form.value.vehicle_type_requested = b.vehicle_type_requested || ''
    form.value.vehicle_booked_id = b.vehicle_booked_id || ''
    form.value.driver_name = b.driver_name || ''
    form.value.passenger_load = b.passenger_load || ''
    form.value.pickup_address = b.pickup_address || ''
    form.value.dropoff_address = b.dropoff_address || ''
    form.value.client_notes = (b.vehicle_notes || b.notes || '')
    // Clear pricing and itinerary for safety
    form.value.itinerary = []
    form.value.default_hourly_charge = ''
    form.value.package_rate = ''
    form.value.gst = ''
    form.value.total = ''
    dupResults.value = []
  } catch (e) { /* ignore */ }
}

function addStop() {
  form.value.itinerary.push({ time24: '', type: 'Leave Red Deer For', directions: '' })
}

function removeStop(idx) {
  form.value.itinerary.splice(idx, 1)
}

async function resolveClientIdByName(name) {
  const query = (name || '').trim().toLowerCase()
  if (!query) return null
  try {
    const res = await fetch('/api/clients')
    if (res.ok) {
      const arr = await res.json()
      const hit = (Array.isArray(arr) ? arr : []).find(c => (c.client_name || c.name || '').toLowerCase() === query)
      if (hit) return hit.client_id || hit.id || null
    }
  } catch (_) { /* ignore */ }
  return null
}

async function createClientIfNeeded(name, phone, email) {
  if (selectedClientId.value) return selectedClientId.value
  const existingId = await resolveClientIdByName(name)
  if (existingId) return existingId
  if (!name) return null
  try {
    const res = await fetch('/api/clients', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_name: name, phone, email })
    })
    const data = await res.json().catch(() => ({}))
    // Return either id or client_id depending on backend
    return data.id || data.client_id || null
  } catch (_) { return null }
}

async function submitForm() {
  const clientId = await createClientIfNeeded(form.value.client_name, form.value.phone, form.value.email)
  // Map UI form fields to charters table columns (safe; backend intersects too)
  const payload = {
    client_id: clientId,
    charter_date: form.value.date || null,
    vehicle_type_requested: form.value.vehicle_type_requested || null,
    vehicle_booked_id: form.value.vehicle_booked_id || null,
    driver_name: form.value.driver_name || null,
    passenger_load: form.value.passenger_load || null,
    pickup_address: form.value.pickup_address || null,
    dropoff_address: form.value.dropoff_address || null,
    vehicle_notes: form.value.client_notes || null,
    notes: form.value.client_notes || null,
    status: 'quote'
  }
  try {
    const res = await fetch('/api/charters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json().catch(() => ({}))
    if (res.ok) {
      toast.success('Charter saved' + (data.charter_id ? ` (ID ${data.charter_id})` : '!'))
    } else {
      toast.error('Save failed: ' + (data.error || data.detail || res.statusText))
    }
  } catch (e) {
    toast.error('Save failed: ' + e)
  }
}

// Client autocomplete handlers
let clientSearchTimer = null
async function onClientInput() {
  selectedClientId.value = null
  const q = (form.value.client_name || '').trim()
  if (clientSearchTimer) clearTimeout(clientSearchTimer)
  if (!q) { clientOptions.value = []; return }
  clientSearchTimer = setTimeout(async () => {
    try {
      const res = await fetch(`/api/clients/search?query=${encodeURIComponent(q)}&limit=10`)
      const data = await res.json().catch(() => ({}))
      clientOptions.value = data.results || []
      clientDropdownOpen.value = true
    } catch (_) { clientOptions.value = [] }
  }, 200)
}
function selectClient(c) {
  form.value.client_name = c.client_name
  selectedClientId.value = c.client_id
  clientDropdownOpen.value = false
}
</script>

<style scoped>
.container-box {
  border: 2px solid #1976d2;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  background: #f5f8ff;
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
}
.form-row {
  display: flex;
  flex-direction: row;
  gap: 1rem;
  margin-bottom: 1rem;
}
label {
  font-weight: 500;
  min-width: 150px;
}
input, select, textarea {
  padding: 0.5rem;
  border-radius: 5px;
  border: 1px solid #ddd;
  font-size: 1rem;
  flex: 1;
}
button {
  margin-top: 1rem;
  padding: 0.75rem 2rem;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1.1rem;
  cursor: pointer;
}
button:hover { background: #4f46e5; }
.itinerary-row { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
h2, h3 { color: #1976d2; }
</style>
