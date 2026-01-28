<template>
  <form @submit.prevent="submitForm" class="booking-form-container">
    <h2>📋 Charter Booking Form (from LMS Views)</h2>
    
    <!-- SECTION 1: DUPLICATE FROM EXISTING -->
    <div class="form-section">
      <h3>📑 Duplicate From Existing Charter</h3>
      <p class="section-help">Search for a similar past charter and copy its details to speed up data entry.</p>
      
      <div class="form-row">
        <input 
          v-model="dupQuery" 
          @input="searchExisting" 
          type="text"
          placeholder="Search by reserve #, client name, or date (YYYY-MM-DD)" 
          class="search-input"
        />
        <button type="button" @click="showDupModal = true" class="btn-secondary">Browse All…</button>
      </div>
      
      <ul v-if="dupResults.length" class="search-results">
        <li v-for="r in dupResults" :key="r.charter_id" @click="applyDuplicate(r)" class="result-item">
          <strong>#{{ r.reserve_number || r.charter_id }}</strong>
          <span class="text-muted">{{ r.client_name }}</span>
          <span class="text-muted">{{ formatDate(r.charter_date) }}</span>
          <span class="status-badge" :class="`status-${r.status}`">{{ r.status }}</span>
        </li>
      </ul>
      <p v-else-if="dupQuery" class="text-muted">No matches found.</p>
    </div>

    <!-- SECTION 2: CUSTOMER DETAILS -->
    <div class="form-section">
      <h3>👤 Customer Details</h3>
      <p class="section-help">New or existing customer information. Search to populate from database.</p>
      
      <div class="form-row">
        <label>Customer Name *</label>
        <div style="flex: 1; position: relative;">
          <input 
            v-model="form.client_name" 
            type="text" 
            @input="onClientInput" 
            @focus="clientDropdownOpen=true"
            placeholder="Enter customer name (or search)"
            class="input-field"
            autocomplete="off"
          />
          <ul v-if="clientDropdownOpen && clientOptions.length" class="autocomplete-dropdown">
            <li v-for="c in clientOptions" :key="c.client_id" @click="selectClient(c)" class="dropdown-item">
              <strong>{{ c.client_name }}</strong>
              <small v-if="c.phone">{{ c.phone }}</small>
              <small v-if="c.email">{{ c.email }}</small>
            </li>
          </ul>
        </div>
      </div>

      <div class="form-row">
        <label>Phone</label>
        <input v-model="form.phone" type="tel" placeholder="(XXX) XXX-XXXX" class="input-field" />
      </div>

      <div class="form-row">
        <label>Email</label>
        <input v-model="form.email" type="email" placeholder="customer@example.com" class="input-field" />
      </div>

      <div class="form-row">
        <label>Billing Address</label>
        <input v-model="form.billing_address" type="text" placeholder="Street address" class="input-field" />
      </div>

      <div class="form-row">
        <label>City / Province</label>
        <input v-model="form.city" type="text" placeholder="City" class="input-field" />
        <input v-model="form.province" type="text" placeholder="AB" class="input-field short-field" />
      </div>

      <div class="form-row">
        <label>Postal Code</label>
        <input v-model="form.postal_code" type="text" placeholder="T4N 1A1" class="input-field short-field" />
      </div>
    </div>

    <!-- SECTION 3: CHARTER DETAILS -->
    <div class="form-section">
      <h3>🚗 Charter Details</h3>
      <p class="section-help">Date, time, and vehicle requirements for the booking.</p>

      <div class="form-row">
        <label>Charter Date *</label>
        <input v-model="form.charter_date" type="date" class="input-field" />
      </div>

      <div class="form-row">
        <label>Pickup Time *</label>
        <input v-model="form.pickup_time" type="time" class="input-field" />
      </div>

      <div class="form-row">
        <label>Passenger Load *</label>
        <input v-model.number="form.passenger_load" type="number" min="1" max="50" placeholder="Number of passengers" class="input-field short-field" />
      </div>

      <div class="form-row">
        <label>Vehicle Type Requested</label>
        <select v-model="form.vehicle_type_requested" class="input-field">
          <option value="">-- Select Vehicle Type --</option>
          <option value="sedan">Sedan (4 pass)</option>
          <option value="suv">SUV (6-8 pass)</option>
          <option value="stretch">Stretch Limo (6-8 pass)</option>
          <option value="party_bus">Party Bus (20 pass)</option>
          <option value="shuttle">Shuttle (12-15 pass)</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div class="form-row">
        <label>Vehicle Booked</label>
        <select v-model="form.vehicle_booked_id" class="input-field">
          <option value="">-- Not Yet Assigned --</option>
          <option v-for="v in vehicles" :key="v.vehicle_id" :value="v.vehicle_id">
            {{ v.vehicle_number }} — {{ v.make }} {{ v.model }} ({{ v.passenger_capacity }} pass)
          </option>
        </select>
      </div>

      <div class="form-row">
        <label>Assigned Driver</label>
        <select v-model="form.assigned_driver_id" class="input-field">
          <option value="">-- Not Yet Assigned --</option>
          <option v-for="d in drivers" :key="d.employee_id" :value="d.employee_id">
            {{ d.first_name }} {{ d.last_name }}
          </option>
        </select>
      </div>
    </div>

    <!-- SECTION 4: ITINERARY / ROUTES -->
    <div class="form-section">
      <h3>📍 Itinerary / Routes</h3>
      <p class="section-help">All stops in order: pickup, intermediate stops, dropoff. Times are optional but recommended.</p>

      <div v-for="(stop, idx) in form.itinerary" :key="`stop-${idx}`" class="itinerary-row">
        <div class="itinerary-number">{{ idx + 1 }}</div>
        
        <div class="itinerary-input">
          <label class="small-label">Stop Type *</label>
          <select v-model="stop.type" class="input-field">
            <option value="pickup">Pick Up At</option>
            <option value="dropoff">Drop Off At</option>
            <option value="stop">Stop At</option>
            <option value="depart">Leave Red Deer For</option>
            <option value="return">Returned to Red Deer</option>
          </select>
        </div>

        <div class="itinerary-input">
          <label class="small-label">Address *</label>
          <input 
            v-model="stop.address" 
            type="text" 
            placeholder="Full address or landmark"
            class="input-field"
          />
        </div>

        <div class="itinerary-input short">
          <label class="small-label">Time</label>
          <input v-model="stop.time24" type="time" class="input-field" />
        </div>

        <button type="button" @click="removeStop(idx)" class="btn-danger btn-small">×</button>
      </div>

      <button type="button" @click="addStop" class="btn-secondary" style="margin-top: 0.5rem;">+ Add Stop</button>
    </div>

    <!-- SECTION 5: SPECIAL REQUESTS & NOTES -->
    <div class="form-section">
      <h3>📝 Special Requests & Notes</h3>
      <p class="section-help">Any special instructions for driver or staff.</p>

      <div class="form-row">
        <label>Customer Notes</label>
        <textarea 
          v-model="form.customer_notes" 
          rows="3" 
          placeholder="e.g., 'Client needs wheelchair accessible vehicle', 'Please depart promptly', etc."
          class="input-field"
        ></textarea>
      </div>

      <div class="form-row">
        <label>Dispatcher/Driver Notes</label>
        <textarea 
          v-model="form.dispatcher_notes" 
          rows="3" 
          placeholder="Internal notes for dispatch team and driver."
          class="input-field"
        ></textarea>
      </div>

      <div class="form-row">
        <label>Special Requests (e.g., Beverages, AV, Extra Stops)</label>
        <textarea 
          v-model="form.special_requests" 
          rows="2" 
          placeholder="Alcohol, music system, extra time, etc. (include pricing if applicable)"
          class="input-field"
        ></textarea>
      </div>
    </div>

    <!-- SECTION 6: PRICING & CHARGES -->
    <div class="form-section">
      <h3>💰 Pricing & Charges</h3>
      <p class="section-help">Base rate, add-ons, GST calculation. GST is tax-included (5% Alberta).</p>

      <div class="pricing-grid">
        <div class="pricing-row">
          <label>Base Charge / Hourly Rate</label>
          <input v-model.number="form.base_charge" type="number" step="0.01" placeholder="0.00" class="input-field" />
        </div>

        <div class="pricing-row">
          <label>Airport/Special Fee</label>
          <input v-model.number="form.airport_fee" type="number" step="0.01" placeholder="0.00" class="input-field" />
        </div>

        <div class="pricing-row">
          <label>Additional Charges (describe)</label>
          <input v-model="form.additional_charges_desc" type="text" placeholder="e.g., 'Overtime', 'Tolls'" class="input-field" />
          <input v-model.number="form.additional_charges_amount" type="number" step="0.01" placeholder="0.00" class="input-field short-field" />
        </div>

        <div class="pricing-row">
          <label>Subtotal (before GST)</label>
          <input v-model.number="form.subtotal" type="number" step="0.01" placeholder="0.00" class="input-field" disabled style="background:#f0f0f0;" />
        </div>

        <div class="pricing-row highlight">
          <label>GST (5% tax-included)</label>
          <input v-model.number="form.gst_amount" type="number" step="0.01" placeholder="0.00" class="input-field" disabled style="background:#fffacd;" />
        </div>

        <div class="pricing-row highlight">
          <label style="font-weight: bold;">Total Amount Due *</label>
          <input v-model.number="form.total_amount_due" type="number" step="0.01" placeholder="0.00" class="input-field" style="font-weight: bold; font-size: 1.1rem;" />
        </div>

        <div class="pricing-row">
          <label>Deposit Paid</label>
          <input v-model.number="form.deposit_paid" type="number" step="0.01" placeholder="0.00" class="input-field" />
        </div>

        <div class="pricing-row highlight">
          <label>Balance Outstanding</label>
          <input v-model.number="form.balance_outstanding" type="number" step="0.01" placeholder="0.00" class="input-field" disabled style="background:#f0f0f0;" />
        </div>
      </div>
    </div>

    <!-- SECTION 7: BOOKING STATUS -->
    <div class="form-section">
      <h3>📌 Booking Status & Notes</h3>
      
      <div class="form-row">
        <label>Status *</label>
        <select v-model="form.status" class="input-field">
          <option value="Quote">Quote (awaiting confirmation)</option>
          <option value="Confirmed">Confirmed (customer accepted)</option>
          <option value="Assigned">Assigned (vehicle/driver assigned)</option>
          <option value="In Progress">In Progress (charter active)</option>
          <option value="Completed">Completed (charter finished)</option>
          <option value="Cancelled">Cancelled</option>
        </select>
      </div>

      <div class="form-row">
        <label>Cancellation Reason</label>
        <input v-model="form.cancellation_reason" type="text" placeholder="Only if status = Cancelled" class="input-field" />
      </div>

      <div class="form-row">
        <label>Reference Number (PO, etc.)</label>
        <input v-model="form.reference_number" type="text" placeholder="Customer PO number or internal reference" class="input-field" />
      </div>
    </div>

    <!-- SUBMISSION -->
    <div class="form-actions">
      <button type="submit" class="btn-primary" :disabled="isSubmitting">
        {{ isSubmitting ? 'Saving…' : '💾 Save Charter Booking' }}
      </button>
      <button type="button" @click="resetForm" class="btn-secondary">Clear Form</button>
    </div>

    <!-- ERROR/SUCCESS DISPLAY -->
    <div v-if="statusMessage" :class="['status-message', statusType]">
      {{ statusMessage }}
    </div>
  </form>
</template>

<script setup>
import { ref, computed } from 'vue'

// Form state
const form = ref({
  // Customer
  client_name: '',
  phone: '',
  email: '',
  billing_address: '',
  city: '',
  province: 'AB',
  postal_code: '',
  
  // Charter
  charter_date: '',
  pickup_time: '',
  passenger_load: 1,
  vehicle_type_requested: '',
  vehicle_booked_id: null,
  assigned_driver_id: null,
  
  // Itinerary
  itinerary: [
    { type: 'pickup', address: '', time24: '' }
  ],
  
  // Notes
  customer_notes: '',
  dispatcher_notes: '',
  special_requests: '',
  
  // Pricing
  base_charge: 0,
  airport_fee: 0,
  additional_charges_desc: '',
  additional_charges_amount: 0,
  subtotal: 0,
  gst_amount: 0,
  total_amount_due: 0,
  deposit_paid: 0,
  balance_outstanding: 0,
  
  // Status
  status: 'Quote',
  cancellation_reason: '',
  reference_number: ''
})

// UI state
const dupQuery = ref('')
const dupResults = ref([])
const clientOptions = ref([])
const clientDropdownOpen = ref(false)
const selectedClientId = ref(null)
const vehicles = ref([])
const drivers = ref([])
const isSubmitting = ref(false)
const statusMessage = ref('')
const statusType = ref('')

// Computed
const subtotal = computed(() => {
  const base = form.value.base_charge || 0
  const airport = form.value.airport_fee || 0
  const additional = form.value.additional_charges_amount || 0
  return base + airport + additional
})

const gstAmount = computed(() => {
  // GST is INCLUDED in total (5% of gross for AB)
  // formula: gst = total * 0.05 / 1.05
  const total = form.value.total_amount_due || 0
  return Math.round(total * 0.05 / 1.05 * 100) / 100
})

const balanceOutstanding = computed(() => {
  const total = form.value.total_amount_due || 0
  const paid = form.value.deposit_paid || 0
  return Math.max(0, total - paid)
})

// Watchers to sync computed values
function updatePricing() {
  form.value.subtotal = subtotal.value
  form.value.gst_amount = gstAmount.value
  form.value.balance_outstanding = balanceOutstanding.value
}

// Methods
function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-CA')
  } catch {
    return dateStr
  }
}

async function searchExisting() {
  const q = dupQuery.value.trim()
  if (!q) { dupResults.value = []; return }
  
  try {
    const res = await fetch(`/api/charters/search?q=${encodeURIComponent(q)}&limit=10`)
    if (res.ok) {
      const data = await res.json()
      dupResults.value = data.results || []
    }
  } catch (e) {
    console.error('Search failed:', e)
  }
}

async function applyDuplicate(charter) {
  // Copy relevant fields from existing charter
  form.value.client_name = charter.client_name || ''
  form.value.phone = charter.phone || ''
  form.value.email = charter.email || ''
  form.value.billing_address = charter.billing_address || ''
  form.value.city = charter.city || ''
  form.value.province = charter.province || 'AB'
  form.value.postal_code = charter.postal_code || ''
  
  form.value.vehicle_type_requested = charter.vehicle_type_requested || ''
  form.value.passenger_load = charter.passenger_load || 1
  
  form.value.customer_notes = charter.customer_notes || ''
  form.value.dispatcher_notes = charter.dispatcher_notes || ''
  form.value.special_requests = charter.special_requests || ''
  
  // Clear itinerary and pricing for safety
  form.value.itinerary = [{ type: 'pickup', address: '', time24: '' }]
  form.value.base_charge = 0
  form.value.airport_fee = 0
  form.value.total_amount_due = 0
  form.value.deposit_paid = 0
  
  selectedClientId.value = charter.client_id
  dupResults.value = []
  dupQuery.value = ''
}

function addStop() {
  form.value.itinerary.push({ type: 'stop', address: '', time24: '' })
}

function removeStop(idx) {
  form.value.itinerary.splice(idx, 1)
}

async function onClientInput() {
  selectedClientId.value = null
  const q = (form.value.client_name || '').trim()
  if (!q) { clientOptions.value = []; return }
  
  try {
    const res = await fetch(`/api/customers/search?q=${encodeURIComponent(q)}&limit=10`)
    if (res.ok) {
      const data = await res.json()
      clientOptions.value = data.results || []
      clientDropdownOpen.value = true
    }
  } catch (_) { clientOptions.value = [] }
}

function selectClient(c) {
  form.value.client_name = c.client_name || c.name
  form.value.phone = c.phone || ''
  form.value.email = c.email || ''
  selectedClientId.value = c.client_id || c.id
  clientDropdownOpen.value = false
}

async function loadVehiclesAndDrivers() {
  try {
    const [vRes, dRes] = await Promise.all([
      fetch('/api/vehicles/'),
      fetch('/api/employees/drivers')
    ])
    if (vRes.ok) vehicles.value = await vRes.json()
    if (dRes.ok) drivers.value = await dRes.json()
  } catch (e) {
    console.error('Failed to load vehicles/drivers:', e)
  }
}

async function submitForm() {
  isSubmitting.value = true
  statusMessage.value = ''
  statusType.value = ''
  
  try {
    // Validate required fields
    if (!form.value.client_name) throw new Error('Customer name is required')
    if (!form.value.charter_date) throw new Error('Charter date is required')
    if (!form.value.pickup_time) throw new Error('Pickup time is required')
    if (!form.value.passenger_load) throw new Error('Passenger load is required')
    if (!form.value.total_amount_due) throw new Error('Total amount is required')
    
    updatePricing()
    
    // Build payload matching PostgreSQL charters table
    const payload = {
      client_id: selectedClientId.value,
      client_name: form.value.client_name,
      phone: form.value.phone,
      email: form.value.email,
      billing_address: form.value.billing_address,
      city: form.value.city,
      province: form.value.province,
      postal_code: form.value.postal_code,
      
      charter_date: form.value.charter_date,
      pickup_time: form.value.pickup_time,
      passenger_load: form.value.passenger_load,
      vehicle_type_requested: form.value.vehicle_type_requested,
      vehicle_booked_id: form.value.vehicle_booked_id || null,
      assigned_driver_id: form.value.assigned_driver_id || null,
      
      // Routes will be saved separately via charter_routes table
      itinerary: form.value.itinerary,
      
      customer_notes: form.value.customer_notes,
      dispatcher_notes: form.value.dispatcher_notes,
      vehicle_notes: form.value.special_requests, // maps to vehicle_notes column
      notes: form.value.dispatcher_notes,
      
      base_charge: form.value.base_charge,
      airport_fee: form.value.airport_fee,
      additional_charges: form.value.additional_charges_amount,
      total_amount_due: form.value.total_amount_due,
      deposit_paid: form.value.deposit_paid,
      gst_amount: form.value.gst_amount,
      
      status: form.value.status,
      cancellation_reason: form.value.cancellation_reason,
      reference_number: form.value.reference_number
    }
    
    const res = await fetch('/api/bookings/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    
    const data = await res.json().catch(() => ({}))
    
    if (res.ok) {
      statusMessage.value = `✅ Charter saved successfully! Reserve #: ${data.reserve_number || data.charter_id}`
      statusType.value = 'success'
      resetForm()
    } else {
      statusMessage.value = `❌ Save failed: ${data.error || data.detail || res.statusText}`
      statusType.value = 'error'
    }
  } catch (e) {
    statusMessage.value = `❌ Error: ${e.message}`
    statusType.value = 'error'
  } finally {
    isSubmitting.value = false
  }
}

function resetForm() {
  form.value = {
    client_name: '', phone: '', email: '', billing_address: '', city: '', province: 'AB', postal_code: '',
    charter_date: '', pickup_time: '', passenger_load: 1, vehicle_type_requested: '', vehicle_booked_id: null, assigned_driver_id: null,
    itinerary: [{ type: 'pickup', address: '', time24: '' }],
    customer_notes: '', dispatcher_notes: '', special_requests: '',
    base_charge: 0, airport_fee: 0, additional_charges_desc: '', additional_charges_amount: 0,
    subtotal: 0, gst_amount: 0, total_amount_due: 0, deposit_paid: 0, balance_outstanding: 0,
    status: 'Quote', cancellation_reason: '', reference_number: ''
  }
  selectedClientId.value = null
  dupQuery.value = ''
  dupResults.value = []
}

// Load data on mount
onMounted(() => {
  loadVehiclesAndDrivers()
})

// Lifecycle
import { onMounted } from 'vue'
</script>

<style scoped>
.booking-form-container {
  max-width: 1200px;
  margin: 2rem auto;
  background: white;
  border-radius: 10px;
  padding: 2rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

h2 {
  color: #1976d2;
  margin-bottom: 1.5rem;
  font-size: 1.8rem;
  border-bottom: 3px solid #667eea;
  padding-bottom: 0.5rem;
}

.form-section {
  background: #f9f9f9;
  border-left: 4px solid #667eea;
  padding: 1.5rem;
  margin-bottom: 2rem;
  border-radius: 6px;
}

.form-section h3 {
  color: #333;
  margin: 0 0 0.5rem 0;
  font-size: 1.2rem;
}

.section-help {
  font-size: 0.9rem;
  color: #666;
  margin: 0.3rem 0 1rem 0;
  font-style: italic;
}

.form-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: flex-start;
}

label {
  font-weight: 500;
  min-width: 150px;
  color: #333;
  padding-top: 0.4rem;
}

.small-label {
  font-size: 0.85rem;
  display: block;
  margin-bottom: 0.3rem;
}

.input-field {
  padding: 0.6rem;
  border: 1px solid #ddd;
  border-radius: 5px;
  font-size: 1rem;
  flex: 1;
  transition: border-color 0.3s;
}

.input-field:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.short-field {
  flex: 0 0 120px;
}

.search-results {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0 0;
  border: 1px solid #ddd;
  border-radius: 5px;
  background: white;
  max-height: 250px;
  overflow-y: auto;
  z-index: 100;
}

.result-item {
  padding: 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid #eee;
  display: flex;
  gap: 1rem;
  align-items: center;
  transition: background 0.2s;
}

.result-item:hover {
  background: #f0f7ff;
}

.text-muted {
  color: #666;
  font-size: 0.9rem;
}

.status-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-weight: 600;
}

.status-Quote { background: #e3f2fd; color: #1976d2; }
.status-Confirmed { background: #c8e6c9; color: #2e7d32; }
.status-Assigned { background: #fff9c4; color: #f57f17; }
.status-In { background: #ffccbc; color: #d84315; }
.status-Completed { background: #e0f2f1; color: #00695c; }
.status-Cancelled { background: #ffebee; color: #c62828; }

.autocomplete-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  list-style: none;
  padding: 0;
  margin: 0.25rem 0 0 0;
  background: white;
  border: 1px solid #ddd;
  border-radius: 5px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  max-height: 200px;
  overflow-y: auto;
  z-index: 101;
}

.dropdown-item {
  padding: 0.75rem;
  cursor: pointer;
  border-bottom: 1px solid #eee;
  transition: background 0.2s;
}

.dropdown-item:hover {
  background: #f0f7ff;
}

.dropdown-item strong {
  display: block;
  margin-bottom: 0.25rem;
}

.dropdown-item small {
  display: block;
  color: #666;
  font-size: 0.85rem;
}

.itinerary-row {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
  align-items: flex-end;
  background: white;
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 6px;
}

.itinerary-number {
  background: #667eea;
  color: white;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.itinerary-input {
  flex: 1;
  min-width: 200px;
}

.itinerary-input.short {
  flex: 0 0 140px;
}

.pricing-grid {
  background: white;
  padding: 1rem;
  border-radius: 6px;
  border: 1px solid #ddd;
}

.pricing-row {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.75rem;
  align-items: center;
}

.pricing-row label {
  min-width: 200px;
}

.pricing-row input {
  flex: 1;
  max-width: 200px;
}

.pricing-row.highlight {
  background: #fffacd;
  padding: 0.75rem;
  border-radius: 4px;
  margin-left: -1rem;
  margin-right: -1rem;
  padding-left: 1rem;
  padding-right: 1rem;
}

.btn-primary, .btn-secondary, .btn-danger, .btn-small {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover {
  background: #4f46e5;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.btn-primary:disabled {
  background: #999;
  cursor: not-allowed;
}

.btn-secondary {
  background: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
}

.btn-secondary:hover {
  background: #e8e8e8;
}

.btn-danger {
  background: #ff6b6b;
  color: white;
  padding: 0.4rem 0.6rem;
  font-size: 1.2rem;
  min-width: 40px;
  text-align: center;
}

.btn-danger:hover {
  background: #ff5252;
}

.btn-small {
  padding: 0.4rem 0.8rem;
  font-size: 0.9rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid #ddd;
}

.status-message {
  padding: 1rem;
  border-radius: 6px;
  margin-top: 1rem;
  font-weight: 500;
}

.status-message.success {
  background: #c8e6c9;
  color: #2e7d32;
  border: 1px solid #81c784;
}

.status-message.error {
  background: #ffcdd2;
  color: #c62828;
  border: 1px solid #ef5350;
}
</style>
