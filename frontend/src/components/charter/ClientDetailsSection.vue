<template>
  <div class="client-details-section">
    <h2>👤 Client Details</h2>
    
    <div class="form-grid">
      <!-- Customer Search -->
      <div class="form-field full-width">
        <label>Customer</label>
        <input 
          type="text" 
          :value="customerSearch"
          @input="$emit('update:customerSearch', $event.target.value)"
          placeholder="Search customer..."
          list="customer-list"
        />
        <datalist id="customer-list">
          <option v-for="c in customers" :key="c.client_id" :value="`${c.first_name} ${c.last_name || ''} - ${c.company_name || ''}`">
        </datalist>
      </div>

      <!-- Charter Date -->
      <div class="form-field">
        <label>Charter Date</label>
        <input 
          type="date"
          :value="charterDate"
          @input="$emit('update:charterDate', $event.target.value)"
        />
      </div>

      <!-- Pickup Time -->
      <div class="form-field">
        <label>Pickup Time</label>
        <input 
          type="time"
          :value="pickupTime"
          @input="$emit('update:pickupTime', $event.target.value)"
        />
      </div>

      <!-- Dropoff Time -->
      <div class="form-field">
        <label>Dropoff Time (Billing Stops)</label>
        <input 
          type="time"
          :value="dropoffTime"
          @input="$emit('update:dropoffTime', $event.target.value)"
        />
      </div>

      <!-- Dispatch Notes (inline) -->
      <div class="form-field">
        <label>Dispatch Notes</label>
        <input 
          type="text"
          :value="dispatchNotes"
          @input="$emit('update:dispatchNotes', $event.target.value)"
          placeholder="Flight #, special instructions..."
        />
      </div>

      <!-- Quick Time Helpers -->
      <div class="form-field full-width">
        <label>Quick Time Extend (handles midnight crossing)</label>
        <div class="quick-time-buttons">
          <button @click="$emit('extend-time', 1)" type="button">+1h</button>
          <button @click="$emit('extend-time', 1.5)" type="button">+1.5h</button>
          <button @click="$emit('extend-time', 2)" type="button">+2h</button>
          <button @click="$emit('extend-time', 2.25)" type="button">+2h 15m</button>
          <button @click="$emit('extend-time', 3)" type="button">+3h</button>
          <button @click="$emit('extend-time', 8.5)" type="button">+8.5h</button>
        </div>
      </div>

      <!-- Passenger Count -->
      <div class="form-field">
        <label>Passenger Count</label>
        <input 
          type="number"
          :value="passengerCount"
          @input="$emit('update:passengerCount', parseInt($event.target.value) || 0)"
          min="1"
          max="60"
        />
      </div>

      <!-- Vehicle Type -->
      <div class="form-field">
        <label>Vehicle Type</label>
        <select 
          :value="vehicleType"
          @change="$emit('update:vehicleType', $event.target.value); $emit('vehicle-type-changed')"
        >
          <option value="">-- Select Vehicle Type --</option>
          <option v-for="vt in vehicleTypes" :key="vt.vehicle_type" :value="vt.vehicle_type">
            {{ vt.vehicle_type }}
          </option>
        </select>
      </div>

      <!-- Run Type -->
      <div class="form-field">
        <label>Run Type</label>
        <select 
          :value="runType"
          @change="$emit('update:runType', $event.target.value); $emit('run-type-changed')"
        >
          <option value="">-- Select Run Type --</option>
          <option v-for="rt in runTypes" :key="rt.id" :value="rt.name">
            {{ rt.name }}
          </option>
        </select>
      </div>

      <!-- Airport Location (if airport run) -->
      <div v-if="runType === 'airport' || (runType && runType.toLowerCase().includes('airport'))" class="form-field">
        <label>Airport Location</label>
        <select 
          :value="airportLocation"
          @change="$emit('update:airportLocation', $event.target.value); $emit('airport-changed')"
        >
          <option value="">-- Select Airport --</option>
          <option v-for="ap in airports" :key="ap.value" :value="ap.value">
            {{ ap.label }}
          </option>
        </select>
      </div>

      <!-- Out of Town -->
      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="outOfTown"
            @change="$emit('update:outOfTown', $event.target.checked)"
          />
          Out of Town (auto-insert routes)
        </label>
      </div>

      <!-- Client Notes -->
      <div class="form-field full-width">
        <label>Client Notes</label>
        <textarea
          :value="clientNotes"
          @input="$emit('update:clientNotes', $event.target.value)"
          rows="3"
          placeholder="Customer requests, special requirements, VIP notes..."
        ></textarea>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { authFetch } from '@/utils/authFetch'

defineProps({
  customerSearch: String,
  charterDate: String,
  pickupTime: String,
  dropoffTime: String,
  dispatchNotes: String,
  passengerCount: Number,
  vehicleType: String,
  runType: String,
  airportLocation: String,
  outOfTown: Boolean,
  clientNotes: String
})

defineEmits([
  'update:customerSearch',
  'update:charterDate',
  'update:pickupTime',
  'update:dropoffTime',
  'update:dispatchNotes',
  'update:passengerCount',
  'update:vehicleType',
  'update:runType',
  'update:airportLocation',
  'update:outOfTown',
  'update:clientNotes',
  'extend-time',
  'vehicle-type-changed',
  'run-type-changed',
  'airport-changed'
])

const customers = ref([])
const vehicleTypes = ref([])
const runTypes = ref([])
const airports = ref([
  { value: 'edmonton', label: 'Edmonton International ($45 pickup fee)', fee: 45 },
  { value: 'calgary', label: 'Calgary International ($65 pickup fee)', fee: 65 },
  { value: 'red_deer', label: 'Red Deer Regional (no pickup fee)', fee: 0 },
])

const loadCustomers = async () => {
  try {
    const response = await authFetch('/api/clients')
    customers.value = await response.json()
  } catch (error) {
    console.warn('Failed to load customers:', error)
    customers.value = []
  }
}

const loadReferenceData = async () => {
  try {
    const [vtRes, rtRes, apRes] = await Promise.all([
      authFetch('/api/lookup/vehicle-types'),
      authFetch('/api/lookup/run-types'),
      authFetch('/api/lookup/airport-fees'),
    ])
    if (vtRes.ok) vehicleTypes.value = await vtRes.json()
    if (rtRes.ok) runTypes.value = await rtRes.json()
    if (apRes.ok) {
      const apData = await apRes.json()
      if (apData.airports && apData.airports.length) airports.value = apData.airports
    }
  } catch (e) {
    console.warn('Could not load reference data from API, dropdowns may be limited:', e)
  }
}

onMounted(() => {
  loadCustomers()
  loadReferenceData()
})
</script>

<style scoped>
.client-details-section {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #667eea;
}

.client-details-section h2 {
  margin: 0 0 0.75rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.form-field.full-width {
  grid-column: 1 / -1;
}

.form-field label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.form-field input,
.form-field select {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-field input:focus,
.form-field select:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.quick-time-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.quick-time-buttons button {
  padding: 0.4rem 0.75rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.quick-time-buttons button:hover {
  background: #5a67d8;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
  cursor: pointer;
}

textarea {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
  font-family: inherit;
  resize: vertical;
}

textarea:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}
</style>
