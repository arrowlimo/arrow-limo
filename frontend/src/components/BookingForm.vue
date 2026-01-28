<template>
  <form @submit.prevent="submitForm">
    <h2>Quote / Charter Booking</h2>

    <!-- Client Lookup Section -->
    <div class="container-box">
      <h3>Client Information</h3>
      <div class="form-row">
        <label>Client Name *</label>
        <div style="flex:1; position: relative;">
          <input 
            ref="clientNameInput"
            v-model="form.client_name" 
            type="text" 
            placeholder="Type client name (fuzzy search)"
            @input="onClientNameInput"
            @keydown.enter="selectClientFromList"
            @keydown.down="focusFirstClient"
            @focus="showClientDropdown = true"
            @blur="setTimeout(() => showClientDropdown = false, 200)"
            autocomplete="off"
            tabindex="1"
          />
          <!-- Dropdown with fuzzy matched clients -->
          <ul v-if="showClientDropdown && filteredClients.length" 
              class="dropdown-list"
              style="position:absolute; z-index:10; background:#fff; border:1px solid #ccc; width:100%; max-height:250px; overflow-y:auto; list-style:none; padding:0; margin:0.2em 0 0 0;">
            <li 
              v-for="(c, idx) in filteredClients" 
              :key="c.client_id"
              :ref="el => { if (idx === 0) firstClientItem = el }"
              @click="selectClient(c)"
              style="padding:0.5em; cursor:pointer; border-bottom:1px solid #eee; hover-bg:#f5f5f5"
              @mouseenter="hoveredClientIdx = idx"
              :style="{ backgroundColor: hoveredClientIdx === idx ? '#f5f5f5' : 'transparent' }"
            >
              <strong>{{ c.client_name }}</strong> 
              <small v-if="c.phone">— {{ c.phone }}</small>
              <small v-if="c.email"> — {{ c.email }}</small>
            </li>
          </ul>
          <!-- "Add New Client" option -->
          <div v-if="form.client_name && !selectedClientId && filteredClients.length === 0"
               style="position:absolute; z-index:9; background:#f9f9f9; border:1px solid #ccc; width:100%; padding:0.5em; margin-top:0.2em;">
            <strong style="color:#666;">Client not found</strong><br/>
            <small>Fill in details below and new client will be created on save</small>
          </div>
        </div>
      </div>

      <!-- Auto-filled from selection -->
      <div class="form-row">
        <label>Phone</label>
        <input v-model="form.phone" type="tel" placeholder="(123) 456-7890" tabindex="2" />
      </div>
      <div class="form-row">
        <label>Email</label>
        <input v-model="form.email" type="email" placeholder="email@example.com" tabindex="3" />
      </div>
    </div>

    <!-- Charter Details -->
    <div class="container-box">
      <h3>Charter Details</h3>
      <div class="form-row">
        <label>Date *</label>
        <input v-model="form.date" type="date" tabindex="4" />
      </div>
      <div class="form-row">
        <label>Vehicle Type Requested</label>
        <input v-model="form.vehicle_type_requested" type="text" placeholder="e.g. sedan, party bus" tabindex="5" />
      </div>
      <div class="form-row">
        <label>Vehicle Booked ID</label>
        <input v-model="form.vehicle_booked_id" type="text" placeholder="e.g. L-24" tabindex="6" />
      </div>
      <div class="form-row">
        <label>Driver Name</label>
        <input v-model="form.driver_name" type="text" tabindex="7" />
      </div>
      <div class="form-row">
        <label>Passenger Load *</label>
        <input v-model="form.passenger_load" type="number" tabindex="8" />
      </div>
    </div>

    <!-- Itinerary Section -->
    <div class="container-box">
      <h3>Itinerary</h3>
      <div v-for="(stop, idx) in form.itinerary" :key="idx" class="itinerary-row" style="display:flex; gap:0.5em; margin-bottom:0.5em; align-items:center;">
        <input v-model="stop.time24" type="time" placeholder="09:00" :tabindex="100 + idx*4" />
        <select v-model="stop.type" :tabindex="101 + idx*4">
          <option>Leave Red Deer For</option>
          <option>Returned to Red Deer</option>
          <option>Pick Up At</option>
          <option>Drop Off At</option>
        </select>
        <input v-model="stop.directions" type="text" placeholder="Address/Location" :tabindex="102 + idx*4" />
        <button type="button" @click="moveStopUp(idx)" v-if="idx > 0" title="Move up">↑</button>
        <button type="button" @click="moveStopDown(idx)" v-if="idx < form.itinerary.length - 1" title="Move down">↓</button>
        <button type="button" @click="removeStop(idx)" :tabindex="103 + idx*4">Remove</button>
      </div>
      <button type="button" @click="addStop" tabindex="200">+ Add Stop</button>
    </div>

    <!-- Invoice Section -->
    <div class="container-box">
      <h3>Charges</h3>
      <div class="form-row">
        <label>Charter Charge (Base) *</label>
        <input v-model="form.default_hourly_charge" type="number" placeholder="0.00" tabindex="300" />
      </div>
      <div class="form-row">
        <label>Additional Charges</label>
        <input v-model="form.package_rate" type="number" placeholder="0.00" tabindex="301" />
      </div>
      <div class="form-row">
        <label>GST (5%)</label>
        <input v-model="form.gst" type="number" placeholder="0.00" tabindex="302" />
      </div>
      <div class="form-row" style="font-weight:bold; font-size:1.1em;">
        <label>Total *</label>
        <input v-model="form.total" type="number" placeholder="0.00" tabindex="303" />
      </div>
    </div>

    <!-- Notes Section -->
    <div class="container-box">
      <label>Client Notes</label>
      <textarea v-model="form.client_notes" rows="3" placeholder="Notes for client and staff..." tabindex="400"></textarea>
    </div>

    <button type="submit" style="font-size:1.2em; padding:1em; background:#007bff; color:#fff; border:none; border-radius:4px; cursor:pointer;">
      Save Booking / Quote
    </button>
  </form>
</template>

<script setup>
import { ref, computed } from 'vue'
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

const clientNameInput = ref(null)
const showClientDropdown = ref(false)
const clientOptions = ref([])
const filteredClients = ref([])
const selectedClientId = ref(null)
const hoveredClientIdx = ref(-1)
const firstClientItem = ref(null)
let clientSearchTimer = null

// Simple fuzzy match function
function fuzzyMatch(query, text) {
  if (!query || !text) return false
  query = query.toLowerCase()
  text = text.toLowerCase()
  let queryIdx = 0
  for (let i = 0; i < text.length; i++) {
    if (text[i] === query[queryIdx]) queryIdx++
    if (queryIdx === query.length) return true
  }
  return false
}

async function onClientNameInput() {
  const q = (form.value.client_name || '').trim()
  if (clientSearchTimer) clearTimeout(clientSearchTimer)
  
  if (!q) {
    filteredClients.value = []
    selectedClientId.value = null
    return
  }
  
  clientSearchTimer = setTimeout(async () => {
    try {
      const res = await fetch(`/api/clients`)
      if (res.ok) {
        const allClients = await res.json()
        const clients = Array.isArray(allClients) ? allClients : allClients.results || []
        filteredClients.value = clients.filter(c => 
          fuzzyMatch(q, c.client_name || '') || 
          fuzzyMatch(q, c.phone || '')
        ).slice(0, 10)
      }
    } catch (e) {
      console.error('Client search error:', e)
    }
  }, 300)
}

function selectClient(client) {
  form.value.client_name = client.client_name || ''
  form.value.phone = client.phone || ''
  form.value.email = client.email || ''
  selectedClientId.value = client.client_id
  filteredClients.value = []
  showClientDropdown.value = false
  toast.success(`Selected: ${client.client_name}`)
}

function selectClientFromList() {
  if (filteredClients.value.length > 0) {
    selectClient(filteredClients.value[0])
  }
}

function focusFirstClient() {
  if (firstClientItem.value) {
    firstClientItem.value.click?.()
  }
}

function addStop() {
  form.value.itinerary.push({ time24: '', type: 'Leave Red Deer For', directions: '' })
}

function removeStop(idx) {
  form.value.itinerary.splice(idx, 1)
}

function moveStopUp(idx) {
  if (idx > 0) {
    [form.value.itinerary[idx], form.value.itinerary[idx-1]] = 
    [form.value.itinerary[idx-1], form.value.itinerary[idx]]
  }
}

function moveStopDown(idx) {
  if (idx < form.value.itinerary.length - 1) {
    [form.value.itinerary[idx], form.value.itinerary[idx+1]] = 
    [form.value.itinerary[idx+1], form.value.itinerary[idx]]
  }
}

async function submitForm() {
  // Validate required fields
  if (!form.value.date) { toast.error('Charter date required'); return }
  if (!form.value.client_name) { toast.error('Client name required'); return }
  if (!form.value.passenger_load) { toast.error('Passenger load required'); return }
  if (!form.value.total) { toast.error('Total amount required'); return }
  
  // Map UI form fields to booking create endpoint
  const payload = {
    client_name: form.value.client_name,
    phone: form.value.phone || null,
    email: form.value.email || null,
    charter_date: form.value.date,
    pickup_time: form.value.itinerary && form.value.itinerary[0] ? form.value.itinerary[0].time24 : '09:00',
    passenger_load: parseInt(form.value.passenger_load) || 0,
    vehicle_type_requested: form.value.vehicle_type_requested || null,
    vehicle_booked_id: form.value.vehicle_booked_id || null,
    driver_name: form.value.driver_name || null,
    pickup_address: form.value.itinerary && form.value.itinerary[0] ? form.value.itinerary[0].directions : null,
    dropoff_address: form.value.itinerary && form.value.itinerary.length > 1 ? form.value.itinerary[form.value.itinerary.length - 1].directions : null,
    total_amount_due: parseFloat(form.value.total) || 0,
    base_charge: parseFloat(form.value.default_hourly_charge) || 0,
    itinerary: form.value.itinerary || [],
    status: 'quote'
  }
  
  console.log('Submitting payload:', payload)
  
  try {
    const res = await fetch('/api/bookings/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    const data = await res.json().catch(() => ({}))
    if (res.ok) {
      toast.success(`✅ Charter saved! Reserve #${data.reserve_number}`)
      console.log('Response data:', data)
      // Reset form on success
      form.value = {
        date: '', client_name: '', phone: '', email: '', vehicle_type_requested: '',
        vehicle_booked_id: '', driver_name: '', passenger_load: '', itinerary: [],
        default_hourly_charge: '', package_rate: '', gst: '', total: '', client_notes: ''
      }
      selectedClientId.value = null
    } else {
      toast.error(`❌ Save failed: ${data.error || data.detail || res.statusText}`)
      console.error('Error response:', data)
    }
  } catch (e) {
    toast.error(`❌ Save failed: ${e}`)
    console.error('Exception:', e)
  }
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
.dropdown-list { list-style: none; }
</style>
